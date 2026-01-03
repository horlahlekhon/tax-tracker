import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from models import (
    Transaction,
    TransactionCreate,
    TransactionUpdate,
    TransactionCategory,
    BankName,
    Asset,
    compute_file_hash,
)
from routes.auth import get_current_company
from utils.storage import (
    get_transactions,
    get_transaction,
    create_transaction,
    create_transactions_bulk,
    update_transaction,
    delete_transaction,
    get_vendors,
    get_clients,
    create_asset,
    get_asset_by_transaction,
    delete_asset,
    file_hash_exists,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def transactions_page(
    request: Request,
    month: Optional[str] = None,
):
    """Render the transactions page."""
    # Get authenticated company
    company = get_current_company(request)

    # Get current month if not specified
    if not month:
        month = datetime.datetime.now().strftime("%Y-%m")

    # Get transactions for the company and month
    transactions = []
    if company:
        transactions = get_transactions(company_id=company.id, month=month)

    # Get categories for the dropdown
    categories = [cat.value for cat in TransactionCategory]

    # Get banks for the dropdown
    banks = [{"value": bank.value, "name": bank.value} for bank in BankName]

    return templates.TemplateResponse(
        "transactions.html",
        {
            "request": request,
            "company": company,
            "transactions": transactions,
            "categories": categories,
            "banks": banks,
            "selected_month": month,
        },
    )


@router.get("/api", response_model=list[Transaction])
async def list_transactions(
    company_id: Optional[str] = None,
    month: Optional[str] = None,
):
    """Get transactions, optionally filtered by company and month."""
    return get_transactions(company_id=company_id, month=month)


@router.post("/api", response_model=Transaction)
async def create_new_transaction(transaction_data: TransactionCreate):
    """Create a new transaction, optionally registering it as an asset."""
    transaction = Transaction(
        company_id=transaction_data.company_id,
        date=transaction_data.date,
        description=transaction_data.description,
        amount=transaction_data.amount,
        vendor_client=transaction_data.vendor_client,
        category=transaction_data.category,
        bank=transaction_data.bank,
        has_receipt=transaction_data.has_receipt,
        notes=transaction_data.notes,
    )
    created_txn = create_transaction(transaction)

    # If marked as asset, create corresponding asset record
    if transaction_data.register_as_asset and transaction_data.asset_name:
        asset = Asset(
            company_id=transaction_data.company_id,
            name=transaction_data.asset_name,
            purchase_date=transaction_data.date,
            purchase_amount=abs(transaction_data.amount),  # Use absolute value
            description=transaction_data.description,
            transaction_id=created_txn.id,
        )
        create_asset(asset)

    return created_txn


@router.get("/api/{transaction_id}", response_model=Transaction)
async def get_transaction_by_id(transaction_id: str):
    """Get a transaction by ID."""
    transaction = get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.put("/api/{transaction_id}", response_model=Transaction)
async def update_transaction_by_id(transaction_id: str, transaction_data: TransactionUpdate):
    """Update a transaction by ID. Optionally register as asset."""
    # Extract asset registration fields before creating updates dict
    register_as_asset = transaction_data.register_as_asset
    asset_name = transaction_data.asset_name

    # Get updates excluding asset-related fields (they're not part of Transaction model)
    exclude_fields = {'register_as_asset', 'asset_name'}
    updates = transaction_data.model_dump(exclude_unset=True, exclude=exclude_fields)

    # First, get the existing transaction to access its data
    existing_transaction = get_transaction(transaction_id)
    if not existing_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Update the transaction
    transaction = update_transaction(transaction_id, updates)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # If marked as asset and no existing asset linked, create asset record
    if register_as_asset and asset_name:
        existing_asset = get_asset_by_transaction(transaction_id)
        if not existing_asset:
            asset = Asset(
                company_id=transaction.company_id,
                name=asset_name,
                purchase_date=transaction.date,
                purchase_amount=abs(transaction.amount),  # Use absolute value
                description=transaction.description,
                transaction_id=transaction_id,
            )
            create_asset(asset)

    return transaction


@router.get("/api/{transaction_id}/asset")
async def get_transaction_asset(transaction_id: str):
    """Get the asset linked to a transaction, if any."""
    asset = get_asset_by_transaction(transaction_id)
    if not asset:
        return None
    return {"id": asset.id, "name": asset.name, "purchase_amount": str(asset.purchase_amount)}


@router.delete("/api/{transaction_id}")
async def delete_transaction_by_id(transaction_id: str):
    """Delete a transaction by ID. Also deletes linked asset if exists."""
    # Check for linked asset and delete it first
    linked_asset = get_asset_by_transaction(transaction_id)
    if linked_asset:
        delete_asset(linked_asset.id)

    if not delete_transaction(transaction_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted successfully"}


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    company_id: str = Form(...),
    bank: str = Form(...),
):
    """Upload and parse a CSV bank statement."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    if not bank:
        raise HTTPException(status_code=400, detail="Bank selection is required")

    # Import here to avoid circular imports
    from utils.csv_parser import parse_bank_statement

    # Parse the bank enum
    try:
        bank_enum = BankName(bank)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid bank: {bank}")

    try:
        content = await file.read()

        # Compute file hash for deduplication
        file_hash = compute_file_hash(content)

        # Check if this file has already been imported
        if file_hash_exists(file_hash):
            raise HTTPException(
                status_code=400,
                detail="This file has already been imported. Upload a different file."
            )

        content_str = content.decode('utf-8')

        # Parse transactions with file_hash for tracking
        transactions = parse_bank_statement(content_str, company_id, bank_enum, file_hash)

        if not transactions:
            raise HTTPException(status_code=400, detail="No valid transactions found in CSV")

        created = create_transactions_bulk(transactions)

        return {
            "message": f"Successfully imported {len(created)} transactions",
            "count": len(created),
        }
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Could not decode CSV file. Please ensure it's UTF-8 encoded."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/vendors")
async def list_vendors(company_id: str):
    """Get list of vendors for autocomplete."""
    return get_vendors(company_id)


@router.get("/clients")
async def list_clients(company_id: str):
    """Get list of clients for autocomplete."""
    return get_clients(company_id)
