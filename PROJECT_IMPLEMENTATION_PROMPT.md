# Nigerian LLC Tax Tracker - FastAPI + Jinja2 Application

Build a complete tax tracking application for Nigerian LLCs using FastAPI and Jinja2 templates.

## Tech Stack
- **Backend**: FastAPI
- **Frontend**: Jinja2 templates with Tailwind CSS (CDN)
- **Storage**: JSON files for now (design with future Tortoise ORM migration in mind)
- **Additional**: Google Drive API integration for document upload

## Core Features

### 1. Multi-Company Management
- Company switcher dropdown in header
- "Add New Company" button
- Each company stores:
  - Company name
  - TIN (Tax Identification Number)
  - Registration date
  - Separate transactions list
  - Separate tax calculations
  - Separate monthly filing checklists

### 2. Transaction Management
- Upload CSV bank statements (parse and import)
- Manual transaction entry
- Transaction fields:
  - Date
  - Description
  - Amount (positive for income, negative for expenses)
  - Vendor/Client (autocomplete from previous entries)
  - Category (Income, Direct Expenses, Operating Expenses, Capital Expenses, Non-Deductible)
  - Has Receipt? (checkbox)
  - Notes
  - Actions (Edit/Delete)

### 3. Tax Calculation Engine
Apply Nigerian LLC tax rules:

**Company Income Tax (CIT):**
- Small Companies (revenue ≤ ₦50,000,000): 0% CIT
- Medium Companies (₦50,000,001 - ₦100,000,000): 20% CIT
- Large Companies (revenue > ₦100,000,000): 30% CIT

**VAT:**
- Required when annual revenue > ₦25,000,000
- Rate: 7.5% on revenue
- Calculate: Output VAT (collected) - Input VAT (paid) = VAT Payable

**Dividends:**
- 10% Withholding Tax (final tax)

**Calculations:**
- Total Revenue (all Income category transactions)
- Deductible Expenses (Direct + Operating + Capital)
- Non-Deductible Expenses (separate tracking)
- Taxable Profit = Revenue - Deductible Expenses
- CIT Amount = Taxable Profit × CIT Rate
- Net Profit = Taxable Profit - CIT Amount

### 4. Dashboard & Reports

**Tax Summary Cards:**
- Total Revenue (with company size indicator)
- Deductible Expenses
- Taxable Profit
- CIT Tax Owed (highlighted)
- VAT Status (Required/Not Required)
- Net Profit After Tax

**Expense Breakdown:**
- Direct Expenses total
- Operating Expenses total
- Capital Expenses total
- Non-Deductible total

**Vendor/Client Insights:**
- Top 5 Vendors This Month (by total amount paid)
- Top 5 Clients This Month (by total amount received)

**Threshold Alerts:**
- Progress toward ₦25m VAT threshold
- Progress toward ₦50m Small Company limit

### 5. Monthly Filing Checklist
Per company, per month:
- [ ] VAT Return Filed (even if ₦0)
- [ ] PAYE Remitted (if applicable)
- [ ] WHT Remitted (if applicable)
- Save completion status per month

### 6. Salary + Dividend Calculator
Tool to help optimize tax:
- Input: Desired monthly take-home
- Output:
  - Recommended salary amount
  - Recommended dividend amount
  - Total tax with this strategy
  - Total tax if taking all as salary
  - Tax savings amount

### 7. Google Drive Integration
**"Approve & Upload" Feature:**
- Generate Balance Sheet PDF with:
  - Company name
  - TIN
  - Month/Year
  - Revenue breakdown
  - Expense breakdown by category
  - Tax calculations
  - Filing checklist status
- Auto-name: `[Company Name] - Balance Sheet - [Month-Year].pdf`
- Upload to user's Google Drive
- Return Google Drive link

### 8. Export Options
- Balance Sheet PDF (download locally)
- VAT Summary CSV
- Annual CIT Summary CSV
- Full transaction export CSV

## File Structure
```
nigerian-tax-tracker/
├── main.py                 # FastAPI app entry point
├── models.py               # Data models (Company, Transaction, etc.) - Tortoise-ready structure
├── utils/
│   ├── tax_calculator.py   # Tax calculation logic
│   ├── pdf_generator.py    # PDF creation
│   ├── csv_parser.py       # CSV statement parser
│   └── gdrive.py           # Google Drive integration
├── routes/
│   ├── companies.py        # Company CRUD endpoints
│   ├── transactions.py     # Transaction CRUD endpoints
│   └── reports.py          # Report generation endpoints
├── static/
│   └── style.css           # Any custom CSS
├── templates/
│   ├── base.html           # Base template with header
│   ├── dashboard.html      # Main dashboard
│   ├── transactions.html   # Transaction list/edit
│   └── calculator.html     # Salary/dividend calculator
├── data/
│   ├── companies.json      # Company data storage
│   └── transactions.json   # Transaction data storage
└── requirements.txt
```

## UI Design Guidelines
- Clean, professional look
- Use Tailwind CSS for styling
- Mobile-responsive
- Color scheme: Green/Blue gradient background, white cards
- Icons from Lucide or Heroicons
- Keep it simple and functional, not over-designed

## API Endpoints Needed

**Companies:**
- GET /companies - List all companies
- POST /companies - Create new company
- GET /companies/{id} - Get company details
- PUT /companies/{id} - Update company
- DELETE /companies/{id} - Delete company

**Transactions:**
- GET /transactions?company_id={id}&month={YYYY-MM} - List transactions
- POST /transactions - Create transaction
- POST /transactions/upload - Upload CSV
- PUT /transactions/{id} - Update transaction
- DELETE /transactions/{id} - Delete transaction

**Reports:**
- GET /reports/dashboard?company_id={id}&month={YYYY-MM} - Dashboard data
- GET /reports/tax-summary?company_id={id}&month={YYYY-MM} - Tax calculations
- POST /reports/approve-upload?company_id={id}&month={YYYY-MM} - Generate & upload to Drive
- GET /reports/export-pdf?company_id={id}&month={YYYY-MM} - Download PDF
- GET /reports/export-csv?company_id={id}&month={YYYY-MM} - Download CSV

**Utilities:**
- GET /vendors?company_id={id} - Get vendor list (for autocomplete)
- GET /clients?company_id={id} - Get client list (for autocomplete)
- POST /calculator/dividend - Calculate optimal salary/dividend split

## Important Implementation Notes

1. **Data Storage**: Use JSON files initially, but structure models.py with Pydantic BaseModels that can easily be converted to Tortoise ORM models later. Keep the model structure compatible with Tortoise field types (CharField, DecimalField, DateField, BooleanField, etc.)

2. **CSV Parsing**: Support common Nigerian bank CSV formats (date, description, debit, credit, balance)

3. **Period Filtering**: Support both monthly view and year-to-date view

4. **Google Drive**: Use OAuth 2.0, store credentials securely, handle token refresh

5. **PDF Generation**: Use ReportLab or WeasyPrint for professional-looking balance sheets

6. **Receipt Tracking**: Show audit readiness score (% of transactions with receipts)

7. **Vendor/Client Autocomplete**: Suggest as user types based on previous entries

## Sample Data Models (Tortoise-Ready Structure)
```python
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from decimal import Decimal

# Current implementation with Pydantic
# Can be easily migrated to Tortoise ORM later

class Company(BaseModel):
    id: str
    name: str  # CharField in Tortoise
    tin: str  # CharField in Tortoise
    registration_date: date  # DateField in Tortoise
    created_at: datetime  # DatetimeField in Tortoise

class Transaction(BaseModel):
    id: str
    company_id: str  # ForeignKeyField to Company in Tortoise
    date: date  # DateField in Tortoise
    description: str  # CharField/TextField in Tortoise
    amount: Decimal  # DecimalField in Tortoise (max_digits=15, decimal_places=2)
    vendor_client: Optional[str]  # CharField in Tortoise, null=True
    category: str  # CharField with choices in Tortoise
    has_receipt: bool  # BooleanField in Tortoise
    notes: Optional[str]  # TextField in Tortoise, null=True

class FilingChecklist(BaseModel):
    id: str
    company_id: str  # ForeignKeyField to Company in Tortoise
    month: str  # CharField in Tortoise (YYYY-MM format)
    vat_filed: bool  # BooleanField in Tortoise
    paye_remitted: bool  # BooleanField in Tortoise
    wht_remitted: bool  # BooleanField in Tortoise

# Future Tortoise ORM migration example:
"""
from tortoise import fields
from tortoise.models import Model

class Company(Model):
    id = fields.UUIDField(pk=True)
    name = fields.CharField(max_length=255)
    tin = fields.CharField(max_length=50)
    registration_date = fields.DateField()
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "companies"

class Transaction(Model):
    id = fields.UUIDField(pk=True)
    company = fields.ForeignKeyField('models.Company', related_name='transactions')
    date = fields.DateField()
    description = fields.CharField(max_length=500)
    amount = fields.DecimalField(max_digits=15, decimal_places=2)
    vendor_client = fields.CharField(max_length=255, null=True)
    category = fields.CharEnumField(CategoryEnum)
    has_receipt = fields.BooleanField(default=False)
    notes = fields.TextField(null=True)
    
    class Meta:
        table = "transactions"
"""
```

## Priority Order
1. Core FastAPI setup with Jinja2
2. Company management (add/list/switch)
3. Transaction management (add/upload/categorize)
4. Tax calculation engine
5. Dashboard with tax summary
6. Monthly filing checklist
7. Vendor/Client tagging & insights
8. PDF generation
9. Google Drive integration
10. Salary/dividend calculator

## Migration Path to Tortoise ORM
When ready to add database support:
1. Install `tortoise-orm` and `aerich` (for migrations)
2. Convert Pydantic models to Tortoise models (structure already compatible)
3. Initialize Tortoise in main.py
4. Create migration scripts with aerich
5. Migrate existing JSON data to database
6. Update CRUD operations to use async Tortoise queries

Build this as a professional, production-ready application with clean code, proper error handling, and user-friendly interface. Ensure all decimal/money calculations use Python's Decimal type for accuracy.
