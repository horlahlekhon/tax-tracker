from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from models import Transaction, TransactionCreate, TransactionUpdate, TransactionCategory, BankName
from utils.storage import (
    get_transactions,
    get_transaction,
    create_transaction,
    create_transactions_bulk,
    update_transaction,
    delete_transaction,
    get_companies,
    get_company,
    get_vendors,
    get_clients,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def transactions_page(
    request: Request,
    company_id: Optional[str] = None,
    month: Optional[str] = None,
):
    """Render the transactions page."""
    all_companies = get_companies()

    # Get selected company
    company = None
    if company_id:
        company = get_company(company_id)
    elif all_companies:
        company = all_companies[0]

    # Get current month if not specified
    if not month:
        month = datetime.now().strftime("%Y-%m")

    # Get transactions for the selected company and month
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
            "companies": all_companies,
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
    """Create a new transaction."""
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
    return create_transaction(transaction)


@router.get("/api/{transaction_id}", response_model=Transaction)
async def get_transaction_by_id(transaction_id: str):
    """Get a transaction by ID."""
    transaction = get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.put("/api/{transaction_id}", response_model=Transaction)
async def update_transaction_by_id(transaction_id: str, transaction_data: TransactionUpdate):
    """Update a transaction by ID."""
    updates = transaction_data.model_dump(exclude_unset=True)
    transaction = update_transaction(transaction_id, updates)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.delete("/api/{transaction_id}")
async def delete_transaction_by_id(transaction_id: str):
    """Delete a transaction by ID."""
    if not delete_transaction(transaction_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted successfully"}


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    company_id: str = Form(...),
    bank: Optional[str] = Form(default=None),
):
    """Upload and parse a CSV bank statement."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    # Import here to avoid circular imports
    from utils.csv_parser import parse_bank_statement

    # Parse the bank enum
    bank_enum = None
    if bank:
        try:
            bank_enum = BankName(bank)
        except ValueError:
            pass  # Invalid bank name, ignore

    try:
        content = await file.read()
        content_str = content.decode('utf-8')

        transactions = parse_bank_statement(content_str, company_id, bank_enum)

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
