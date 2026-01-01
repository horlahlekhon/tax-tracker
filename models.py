from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def generate_id() -> str:
    """Generate a unique ID for models."""
    return str(uuid4())


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
    """Company size classification based on annual revenue."""
    SMALL = "Small"      # Revenue <= 50,000,000
    MEDIUM = "Medium"    # Revenue 50,000,001 - 100,000,000
    LARGE = "Large"      # Revenue > 100,000,000


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
    registration_date: date
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


class CompanyCreate(BaseModel):
    """Schema for creating a new company."""
    name: str = Field(..., min_length=1, max_length=255)
    tin: str = Field(..., min_length=1, max_length=50)
    registration_date: date


class CompanyUpdate(BaseModel):
    """Schema for updating a company."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tin: Optional[str] = Field(None, min_length=1, max_length=50)
    registration_date: Optional[date] = None


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
    - created_at: DatetimeField(auto_now_add=True)
    """
    id: str = Field(default_factory=generate_id)
    company_id: str
    date: date
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., max_digits=15, decimal_places=2)
    vendor_client: Optional[str] = Field(None, max_length=255)
    category: TransactionCategory
    bank: Optional[BankName] = None
    has_receipt: bool = False
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }


class TransactionCreate(BaseModel):
    """Schema for creating a new transaction."""
    company_id: str
    date: date
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., max_digits=15, decimal_places=2)
    vendor_client: Optional[str] = Field(None, max_length=255)
    category: TransactionCategory
    bank: Optional[BankName] = None
    has_receipt: bool = False
    notes: Optional[str] = None


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction."""
    date: Optional[date] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    amount: Optional[Decimal] = Field(None, max_digits=15, decimal_places=2)
    vendor_client: Optional[str] = Field(None, max_length=255)
    category: Optional[TransactionCategory] = None
    bank: Optional[BankName] = None
    has_receipt: Optional[bool] = None
    notes: Optional[str] = None


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
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
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

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
        }
