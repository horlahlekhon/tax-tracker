# Nigerian LLC Tax Tracker

A web application for tracking taxes for Nigerian Limited Liability Companies. Built with FastAPI and Jinja2 templates.

## Features

- **Multi-Company Management**: Track multiple companies with separate transactions and tax calculations
- **Transaction Management**: Manual entry and CSV bank statement import with bank tracking
- **PDF to CSV Converter**: Convert bank statement PDFs to CSV format (supports Zenith Bank, GTBank with password protection)
- **Bank Tracking**: Track which bank each transaction originated from
- **Tax Calculation Engine**: Automatic calculation of CIT, VAT, and WHT based on Nigerian tax law
- **Dashboard & Reports**: Tax summaries, expense breakdowns, and vendor/client insights
- **Monthly Filing Checklist**: Track VAT returns, PAYE, and WHT remittances
- **Salary + Dividend Calculator**: Optimize tax by splitting income between salary and dividends
- **PDF Reports**: Generate balance sheets for filing
- **Google Drive Integration**: Upload reports directly to Google Drive

## Supported Banks

The application supports importing transactions from the following Nigerian banks:

| Bank | CSV Import | PDF to CSV |
|------|------------|------------|
| Zenith Bank | Yes | Yes |
| GTBank | Yes | Yes (password-protected) |
| Access Bank | Yes | - |
| UBA | Yes | - |
| First Bank | Yes | - |
| FCMB | Yes | - |
| Fidelity Bank | Yes | - |
| Sterling Bank | Yes | - |
| Wema Bank | Yes | - |
| Stanbic IBTC | Yes | - |

## Nigerian Tax Rules

| Tax Type | Threshold/Rate |
|----------|----------------|
| CIT (Small) | 0% for revenue ≤ ₦50,000,000 |
| CIT (Medium) | 20% for revenue ₦50M - ₦100M |
| CIT (Large) | 30% for revenue > ₦100,000,000 |
| VAT | 7.5% when annual revenue > ₦25,000,000 |
| Dividend WHT | 10% (final tax) |

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd tax-tracker

# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Install with dev dependencies
poetry install --with dev
```

## Development

```bash
# Activate virtual environment
poetry shell

# Run development server
uvicorn main:app --reload

# Run tests
pytest

# Run linter
ruff check .

# Format code
ruff format .
```

## Project Structure

```
nigerian-tax-tracker/
├── main.py                      # FastAPI app entry point
├── models.py                    # Pydantic data models
├── utils/
│   ├── tax_calculator.py        # Tax calculation logic
│   ├── pdf_generator.py         # Balance sheet PDF creation
│   ├── pdf_statement_parser.py  # Bank PDF statement to CSV converter
│   ├── csv_parser.py            # CSV statement parser
│   ├── storage.py               # JSON file storage operations
│   └── gdrive.py                # Google Drive integration
├── routes/
│   ├── companies.py             # Company CRUD endpoints
│   ├── transactions.py          # Transaction CRUD endpoints
│   ├── pdf_converter.py         # PDF to CSV converter endpoints
│   └── reports.py               # Report generation endpoints
├── templates/                   # Jinja2 templates
├── static/                      # Static assets
└── data/                        # JSON data storage
```

## Configuration

For Google Drive integration, set up OAuth 2.0 credentials:

1. Create a project in Google Cloud Console
2. Enable the Google Drive API
3. Create OAuth 2.0 credentials
4. Download credentials and save as `credentials.json`

## License

MIT
