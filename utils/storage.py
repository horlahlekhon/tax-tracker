import datetime
import json
from decimal import Decimal
from pathlib import Path
from typing import Optional

from models import Company, Transaction, FilingChecklist, Asset

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for date, datetime, and Decimal types."""

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def ensure_data_dir():
    """Ensure the data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(filename: str) -> list:
    """Read data from a JSON file."""
    ensure_data_dir()
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return []
    with open(filepath, "r") as f:
        return json.load(f)


def _write_json(filename: str, data: list):
    """Write data to a JSON file."""
    ensure_data_dir()
    filepath = DATA_DIR / filename
    with open(filepath, "w") as f:
        json.dump(data, f, cls=JSONEncoder, indent=2)


# Company CRUD operations
def get_companies() -> list[Company]:
    """Get all companies."""
    data = _read_json("companies.json")
    return [Company(**item) for item in data]


def get_company(company_id: str) -> Optional[Company]:
    """Get a company by ID."""
    companies = get_companies()
    for company in companies:
        if company.id == company_id:
            return company
    return None


def get_company_by_tin(tin: str) -> Optional[Company]:
    """Get a company by TIN."""
    companies = get_companies()
    for company in companies:
        if company.tin.lower() == tin.lower():
            return company
    return None


def create_company(company: Company) -> Company:
    """Create a new company."""
    companies = get_companies()
    companies.append(company)
    _write_json("companies.json", [c.model_dump() for c in companies])
    return company


def update_company(company_id: str, updates: dict) -> Optional[Company]:
    """Update a company by ID."""
    companies = get_companies()
    for i, company in enumerate(companies):
        if company.id == company_id:
            updated_data = company.model_dump()
            updated_data.update({k: v for k, v in updates.items() if v is not None})
            companies[i] = Company(**updated_data)
            _write_json("companies.json", [c.model_dump() for c in companies])
            return companies[i]
    return None


def delete_company(company_id: str) -> bool:
    """Delete a company by ID."""
    companies = get_companies()
    initial_count = len(companies)
    companies = [c for c in companies if c.id != company_id]
    if len(companies) < initial_count:
        _write_json("companies.json", [c.model_dump() for c in companies])
        # Also delete related transactions, checklists, and assets
        delete_transactions_by_company(company_id)
        delete_checklists_by_company(company_id)
        delete_assets_by_company(company_id)
        return True
    return False


# Transaction CRUD operations
def get_transactions(
    company_id: Optional[str] = None,
    month: Optional[str] = None,
) -> list[Transaction]:
    """Get transactions, optionally filtered by company and/or month."""
    data = _read_json("transactions.json")
    transactions = [Transaction(**item) for item in data]

    if company_id:
        transactions = [t for t in transactions if t.company_id == company_id]

    if month:  # Format: YYYY-MM
        transactions = [
            t for t in transactions
            if t.date.strftime("%Y-%m") == month
        ]

    return sorted(transactions, key=lambda t: t.date, reverse=True)


def get_transactions_ytd(company_id: str, year: int) -> list[Transaction]:
    """Get year-to-date transactions for a company."""
    data = _read_json("transactions.json")
    transactions = [Transaction(**item) for item in data]
    return [
        t for t in transactions
        if t.company_id == company_id and t.date.year == year
    ]


def get_transaction(transaction_id: str) -> Optional[Transaction]:
    """Get a transaction by ID."""
    data = _read_json("transactions.json")
    for item in data:
        if item["id"] == transaction_id:
            return Transaction(**item)
    return None


def create_transaction(transaction: Transaction) -> Transaction:
    """Create a new transaction."""
    data = _read_json("transactions.json")
    data.append(transaction.model_dump())
    _write_json("transactions.json", data)
    return transaction


def file_hash_exists(file_hash: str) -> bool:
    """Check if a file with the given hash has already been imported.

    Args:
        file_hash: SHA256 hash of the CSV file content

    Returns:
        True if any transaction with this file_hash exists
    """
    data = _read_json("transactions.json")
    return any(item.get("file_hash") == file_hash for item in data)


def create_transactions_bulk(transactions: list[Transaction]) -> list[Transaction]:
    """Create multiple transactions at once (for CSV import).

    Note: File-level deduplication should be done BEFORE calling this function
    using file_hash_exists(). This function simply creates all transactions.

    Args:
        transactions: List of Transaction objects to create

    Returns:
        List of created transactions
    """
    if not transactions:
        return []

    data = _read_json("transactions.json")

    for t in transactions:
        data.append(t.model_dump())

    _write_json("transactions.json", data)

    return transactions


def update_transaction(transaction_id: str, updates: dict) -> Optional[Transaction]:
    """Update a transaction by ID."""
    data = _read_json("transactions.json")
    for i, item in enumerate(data):
        if item["id"] == transaction_id:
            item.update({k: v for k, v in updates.items() if v is not None})
            # Handle special type conversions
            if "amount" in updates and updates["amount"] is not None:
                item["amount"] = str(updates["amount"])
            if "category" in updates and updates["category"] is not None:
                item["category"] = updates["category"].value if hasattr(updates["category"], "value") else updates["category"]
            _write_json("transactions.json", data)
            return Transaction(**item)
    return None


def delete_transaction(transaction_id: str) -> bool:
    """Delete a transaction by ID."""
    data = _read_json("transactions.json")
    initial_count = len(data)
    data = [item for item in data if item["id"] != transaction_id]
    if len(data) < initial_count:
        _write_json("transactions.json", data)
        return True
    return False


def delete_transactions_by_company(company_id: str):
    """Delete all transactions for a company."""
    data = _read_json("transactions.json")
    data = [item for item in data if item["company_id"] != company_id]
    _write_json("transactions.json", data)


# Vendor/Client operations
def get_vendors(company_id: str) -> list[str]:
    """Get unique vendor names for a company (for autocomplete)."""
    transactions = get_transactions(company_id=company_id)
    vendors = set()
    for t in transactions:
        if t.vendor_client and t.amount < 0:  # Expenses go to vendors
            vendors.add(t.vendor_client)
    return sorted(vendors)


def get_clients(company_id: str) -> list[str]:
    """Get unique client names for a company (for autocomplete)."""
    transactions = get_transactions(company_id=company_id)
    clients = set()
    for t in transactions:
        if t.vendor_client and t.amount > 0:  # Income comes from clients
            clients.add(t.vendor_client)
    return sorted(clients)


# Filing Checklist CRUD operations
def get_checklist(company_id: str, month: str) -> Optional[FilingChecklist]:
    """Get filing checklist for a company and month."""
    data = _read_json("checklists.json")
    for item in data:
        if item["company_id"] == company_id and item["month"] == month:
            return FilingChecklist(**item)
    return None


def get_checklists(company_id: str) -> list[FilingChecklist]:
    """Get all filing checklists for a company."""
    data = _read_json("checklists.json")
    return [
        FilingChecklist(**item)
        for item in data
        if item["company_id"] == company_id
    ]


def create_or_update_checklist(
    company_id: str,
    month: str,
    updates: dict,
) -> FilingChecklist:
    """Create or update a filing checklist."""
    data = _read_json("checklists.json")

    for i, item in enumerate(data):
        if item["company_id"] == company_id and item["month"] == month:
            item.update({k: v for k, v in updates.items() if v is not None})
            item["updated_at"] = datetime.datetime.now().isoformat()
            _write_json("checklists.json", data)
            return FilingChecklist(**item)

    # Create new checklist
    checklist = FilingChecklist(
        company_id=company_id,
        month=month,
        **{k: v for k, v in updates.items() if v is not None},
    )
    data.append(checklist.model_dump())
    _write_json("checklists.json", data)
    return checklist


def delete_checklists_by_company(company_id: str):
    """Delete all checklists for a company."""
    data = _read_json("checklists.json")
    data = [item for item in data if item["company_id"] != company_id]
    _write_json("checklists.json", data)


# Asset CRUD operations
def get_assets(company_id: Optional[str] = None) -> list[Asset]:
    """Get assets, optionally filtered by company."""
    data = _read_json("assets.json")
    assets = [Asset(**item) for item in data]

    if company_id:
        assets = [a for a in assets if a.company_id == company_id]

    return sorted(assets, key=lambda a: a.purchase_date, reverse=True)


def get_asset(asset_id: str) -> Optional[Asset]:
    """Get an asset by ID."""
    data = _read_json("assets.json")
    for item in data:
        if item["id"] == asset_id:
            return Asset(**item)
    return None


def get_asset_by_transaction(transaction_id: str) -> Optional[Asset]:
    """Get an asset linked to a specific transaction."""
    data = _read_json("assets.json")
    for item in data:
        if item.get("transaction_id") == transaction_id:
            return Asset(**item)
    return None


def create_asset(asset: Asset) -> Asset:
    """Create a new asset."""
    data = _read_json("assets.json")
    data.append(asset.model_dump())
    _write_json("assets.json", data)
    return asset


def update_asset(asset_id: str, updates: dict) -> Optional[Asset]:
    """Update an asset by ID."""
    data = _read_json("assets.json")
    for i, item in enumerate(data):
        if item["id"] == asset_id:
            item.update({k: v for k, v in updates.items() if v is not None})
            # Handle special type conversions
            if "purchase_amount" in updates and updates["purchase_amount"] is not None:
                item["purchase_amount"] = str(updates["purchase_amount"])
            _write_json("assets.json", data)
            return Asset(**item)
    return None


def delete_asset(asset_id: str) -> bool:
    """Delete an asset by ID."""
    data = _read_json("assets.json")
    initial_count = len(data)
    data = [item for item in data if item["id"] != asset_id]
    if len(data) < initial_count:
        _write_json("assets.json", data)
        return True
    return False


def delete_assets_by_company(company_id: str):
    """Delete all assets for a company."""
    data = _read_json("assets.json")
    data = [item for item in data if item["company_id"] != company_id]
    _write_json("assets.json", data)


def get_total_assets_value(company_id: str) -> Decimal:
    """Calculate total asset value for a company."""
    assets = get_assets(company_id=company_id)
    return sum(a.purchase_amount for a in assets) if assets else Decimal("0")
