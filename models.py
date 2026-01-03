import datetime
import hashlib
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def generate_id() -> str:
    """Generate a unique ID for models."""
    return str(uuid4())


def compute_file_hash(content: bytes) -> str:
    """
    Compute a SHA256 hash of file content for duplicate file detection.
    Used to prevent re-importing the same CSV file.
    """
    return hashlib.sha256(content).hexdigest()[:64]


class TransactionCategory(str, Enum):
    """Transaction category enum for categorizing transactions."""
    INCOME = "Income"
    DIRECT_EXPENSES = "Direct Expenses"
    OPERATING_EXPENSES = "Operating Expenses"
    CAPITAL_EXPENSES = "Capital Expenses"
    NON_DEDUCTIBLE = "Non-Deductible"


class BankName(str, Enum):
    """Supported banks for transactions."""
    ZENITH = "Zenith Bank"
    GTBANK = "GTBank"
    KUDA = "Kuda Bank"
    ACCESS = "Access Bank"
    UBA = "UBA"
    FIRST_BANK = "First Bank"
    FCMB = "FCMB"
    FIDELITY = "Fidelity Bank"
    STERLING = "Sterling Bank"
    WEMA = "Wema Bank"
    STANBIC = "Stanbic IBTC"
    OTHER = "Other"


class CompanySize(str, Enum):
    """Company size classification based on annual revenue AND total assets.

    Nigerian CIT tiers (Updated):
    - Small: Revenue <= 25,000,000 AND Assets <= 250,000,000 (0% CIT)
    - Medium: Revenue 25,000,001 - 100,000,000 or exceeds asset threshold (20% CIT)
    - Large: Revenue > 100,000,000 (30% CIT)
    """
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"


class Company(BaseModel):
    """
    Company model for Nigerian LLC.

    Tortoise ORM migration notes:
    - id: UUIDField(pk=True)
    - name: CharField(max_length=255)
    - tin: CharField(max_length=50)
    - registration_date: DateField()
    - created_at: DatetimeField(auto_now_add=True)
    """
    id: str = Field(default_factory=generate_id)
    name: str = Field(..., min_length=1, max_length=255)
    tin: str = Field(..., min_length=1, max_length=50)
    registration_date: datetime.date
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    class Config:
        json_encoders = {
            datetime.date: lambda v: v.isoformat(),
            datetime.datetime: lambda v: v.isoformat(),
        }


class CompanyCreate(BaseModel):
    """Schema for creating a new company."""
    name: str = Field(..., min_length=1, max_length=255)
    tin: str = Field(..., min_length=1, max_length=50)
    registration_date: datetime.date


class CompanyUpdate(BaseModel):
    """Schema for updating a company."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tin: Optional[str] = Field(None, min_length=1, max_length=50)
    registration_date: Optional[datetime.date] = None


class Transaction(BaseModel):
    """
    Transaction model for income and expenses.

    Tortoise ORM migration notes:
    - id: UUIDField(pk=True)
    - company_id: ForeignKeyField('models.Company', related_name='transactions')
    - date: DateField()
    - description: CharField(max_length=500)
    - amount: DecimalField(max_digits=15, decimal_places=2)
    - vendor_client: CharField(max_length=255, null=True)
    - category: CharEnumField(TransactionCategory)
    - bank: CharEnumField(BankName, null=True)
    - has_receipt: BooleanField(default=False)
    - notes: TextField(null=True)
    - file_hash: CharField(max_length=64, null=True) - Hash of source CSV file
    - created_at: DatetimeField(auto_now_add=True)
    """
    id: str = Field(default_factory=generate_id)
    company_id: str
    date: datetime.date
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., max_digits=15, decimal_places=2)
    vendor_client: Optional[str] = Field(None, max_length=255)
    category: TransactionCategory
    bank: Optional[BankName] = None
    has_receipt: bool = False
    notes: Optional[str] = None
    file_hash: Optional[str] = Field(None, max_length=64)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    class Config:
        json_encoders = {
            datetime.date: lambda v: v.isoformat(),
            datetime.datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }


class TransactionCreate(BaseModel):
    """Schema for creating a new transaction."""
    company_id: str
    date: datetime.date
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., max_digits=15, decimal_places=2)
    vendor_client: Optional[str] = Field(None, max_length=255)
    category: TransactionCategory
    bank: Optional[BankName] = None
    has_receipt: bool = False
    notes: Optional[str] = None
    register_as_asset: bool = False
    asset_name: Optional[str] = Field(None, max_length=255)


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction."""
    date: Optional[datetime.date] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    amount: Optional[Decimal] = Field(None, max_digits=15, decimal_places=2)
    vendor_client: Optional[str] = Field(None, max_length=255)
    category: Optional[TransactionCategory] = None
    bank: Optional[BankName] = None
    has_receipt: Optional[bool] = None
    notes: Optional[str] = None
    register_as_asset: bool = False
    asset_name: Optional[str] = Field(None, max_length=255)


class FilingChecklist(BaseModel):
    """
    Monthly filing checklist for tax compliance tracking.

    Tortoise ORM migration notes:
    - id: UUIDField(pk=True)
    - company_id: ForeignKeyField('models.Company', related_name='checklists')
    - month: CharField(max_length=7) - Format: YYYY-MM
    - vat_filed: BooleanField(default=False)
    - paye_remitted: BooleanField(default=False)
    - wht_remitted: BooleanField(default=False)
    - created_at: DatetimeField(auto_now_add=True)
    - updated_at: DatetimeField(auto_now=True)
    """
    id: str = Field(default_factory=generate_id)
    company_id: str
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")  # YYYY-MM format
    vat_filed: bool = False
    paye_remitted: bool = False
    wht_remitted: bool = False
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    class Config:
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat(),
        }


class FilingChecklistUpdate(BaseModel):
    """Schema for updating a filing checklist."""
    vat_filed: Optional[bool] = None
    paye_remitted: Optional[bool] = None
    wht_remitted: Optional[bool] = None


class TaxSummary(BaseModel):
    """Tax calculation summary for dashboard display."""
    total_revenue: Decimal = Decimal("0")
    direct_expenses: Decimal = Decimal("0")
    operating_expenses: Decimal = Decimal("0")
    capital_expenses: Decimal = Decimal("0")
    non_deductible_expenses: Decimal = Decimal("0")
    deductible_expenses: Decimal = Decimal("0")
    taxable_profit: Decimal = Decimal("0")
    company_size: CompanySize = CompanySize.SMALL
    cit_rate: int = 0
    cit_amount: Decimal = Decimal("0")
    vat_required: bool = False
    vat_amount: Decimal = Decimal("0")
    net_profit: Decimal = Decimal("0")
    receipt_percentage: int = 0
    vat_threshold_percent: int = 0
    small_company_threshold_percent: int = 0
    total_assets: Decimal = Decimal("0")
    asset_threshold_percent: int = 0

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
        }


class Asset(BaseModel):
    """
    Asset model for tracking company assets.

    Tortoise ORM migration notes:
    - id: UUIDField(pk=True)
    - company_id: ForeignKeyField('models.Company', related_name='assets')
    - name: CharField(max_length=255)
    - purchase_date: DateField()
    - purchase_amount: DecimalField(max_digits=15, decimal_places=2)
    - description: TextField(null=True)
    - transaction_id: ForeignKeyField('models.Transaction', null=True, related_name='asset')
    - created_at: DatetimeField(auto_now_add=True)
    """
    id: str = Field(default_factory=generate_id)
    company_id: str
    name: str = Field(..., min_length=1, max_length=255)
    purchase_date: datetime.date
    purchase_amount: Decimal = Field(..., max_digits=15, decimal_places=2)
    description: Optional[str] = None
    transaction_id: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    class Config:
        json_encoders = {
            datetime.date: lambda v: v.isoformat(),
            datetime.datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }


class AssetCreate(BaseModel):
    """Schema for creating a new asset."""
    company_id: str
    name: str = Field(..., min_length=1, max_length=255)
    purchase_date: datetime.date
    purchase_amount: Decimal = Field(..., max_digits=15, decimal_places=2)
    description: Optional[str] = None
    transaction_id: Optional[str] = None


class AssetUpdate(BaseModel):
    """Schema for updating an asset."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    purchase_date: Optional[datetime.date] = None
    purchase_amount: Optional[Decimal] = Field(None, max_digits=15, decimal_places=2)
    description: Optional[str] = None
