# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nigerian LLC Tax Tracker - A FastAPI + Jinja2 web application for tracking taxes for Nigerian Limited Liability Companies. The application handles multi-company management, transaction tracking, tax calculations based on Nigerian tax law, and report generation.

## Tech Stack

- **Backend**: FastAPI with Jinja2 templates
- **Frontend**: Tailwind CSS (CDN)
- **Storage**: JSON files (structured for future Tortoise ORM migration)
- **PDF Generation**: ReportLab or WeasyPrint
- **External Integration**: Google Drive API for document upload

## Common Commands

```bash
# Install dependencies
poetry install

# Install with dev dependencies
poetry install --with dev

# Activate virtual environment
poetry shell

# Run development server
uvicorn main:app --reload

# Run tests
pytest

# Run linter
ruff check .
```

## Architecture

### Data Flow
1. FastAPI routes receive requests and render Jinja2 templates
2. Business logic in `utils/` modules handles tax calculations, CSV parsing, PDF generation
3. Data persisted to JSON files in `data/` directory
4. Models in `models.py` use Pydantic BaseModels (designed for future Tortoise ORM migration)

### Key Modules
- `utils/tax_calculator.py` - Nigerian tax rules engine (CIT tiers, VAT, WHT)
- `utils/csv_parser.py` - Bank statement CSV import with auto-categorization
- `utils/pdf_statement_parser.py` - PDF bank statement to CSV converter (multi-bank support)
- `utils/pdf_generator.py` - Balance sheet PDF creation
- `utils/storage.py` - JSON file CRUD operations
- `utils/gdrive.py` - Google Drive OAuth and upload

### Key Routes
- `routes/transactions.py` - Transaction CRUD, CSV upload with bank tracking
- `routes/pdf_converter.py` - PDF to CSV converter page and API
- `routes/companies.py` - Company management
- `routes/reports.py` - Report generation and dashboard

### Tax Calculation Rules
- **CIT Rates**: 0% (≤₦50M), 20% (₦50M-₦100M), 30% (>₦100M)
- **VAT**: 7.5% when annual revenue >₦25M
- **Dividend WHT**: 10%

### Transaction Categories (TransactionCategory enum)
- Income, Direct Expenses, Operating Expenses, Capital Expenses, Non-Deductible

### Supported Banks (BankName enum)
- Zenith Bank, GTBank, Access Bank, UBA, First Bank, FCMB, Fidelity Bank, Sterling Bank, Wema Bank, Stanbic IBTC, Other

### PDF Statement Parser
The `utils/pdf_statement_parser.py` module handles converting bank PDF statements to CSV:
- **Zenith Bank**: 6-column format (DATE, DESCRIPTION, DEBIT, CREDIT, VALUE DATE, BALANCE), date format DD/MM/YYYY
- **GTBank**: 8-column format (Trans. Date, Value Date, Reference, Debits, Credits, Balance, Originating Branch, Remarks), date format DD-MMM-YYYY, supports password-protected PDFs

To add a new bank parser:
1. Add bank to `SupportedBank` enum in `pdf_statement_parser.py`
2. Create `is_valid_date_<bank>()` function if date format differs
3. Create `parse_<bank>_statement()` function following existing patterns
4. Update `parse_pdf_bank_statement()` to route to new parser
5. Add bank to `SUPPORTED_BANKS` list in `routes/pdf_converter.py`

### Data Storage
JSON files in `data/` directory:
- `companies.json` - Company records
- `transactions.json` - Transaction records (includes `bank` field)
- `checklists.json` - Filing checklists

### Important Notes
- Use Python's `Decimal` type for all monetary calculations
- Transactions track the originating bank via the `bank` field (optional)
- CSV imports can specify a bank to apply to all imported transactions
- PDF converter supports password-protected PDFs (GTBank)
