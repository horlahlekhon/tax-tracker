from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from routes import companies, transactions, reports, gdrive, pdf_converter
from utils.storage import get_companies, get_company, get_transactions, get_transactions_ytd
from utils.tax_calculator import calculate_tax_summary

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Nigerian LLC Tax Tracker",
    description="Tax tracking application for Nigerian Limited Liability Companies",
    version="0.1.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Include routers
app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(gdrive.router, prefix="/gdrive", tags=["gdrive"])
app.include_router(pdf_converter.router, prefix="/pdf-converter", tags=["pdf-converter"])


@app.get("/")
async def home(
    request: Request,
    company_id: Optional[str] = None,
    month: Optional[str] = None,
    period: str = "month",
):
    """Dashboard home page."""
    all_companies = get_companies()

    # Get selected company
    company = None
    if company_id:
        company = get_company(company_id)
    elif all_companies:
        # Default to first company if none selected
        company = all_companies[0]

    # Get current month if not specified
    if not month:
        month = datetime.now().strftime("%Y-%m")

    # Calculate tax summary
    summary = None
    if company:
        # Get transactions for the selected period
        if period == "ytd":
            year = int(month.split("-")[0])
            txns = get_transactions_ytd(company.id, year)
        else:
            txns = get_transactions(company_id=company.id, month=month)

        # For threshold calculations, use YTD revenue
        year = int(month.split("-")[0])
        ytd_txns = get_transactions_ytd(company.id, year)
        ytd_summary = calculate_tax_summary(ytd_txns, period_type="ytd")
        annual_revenue = ytd_summary.total_revenue

        # Calculate summary for selected period
        summary = calculate_tax_summary(
            txns,
            period_type=period,
            annual_revenue_override=annual_revenue,
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "company": company,
            "companies": all_companies,
            "summary": summary,
            "selected_month": month,
            "selected_period": period,
        },
    )


@app.get("/calculator")
async def calculator(
    request: Request,
    company_id: Optional[str] = None,
    month: Optional[str] = None,
):
    """Salary/Dividend Calculator page."""
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

    # Calculate tax summary if company exists
    summary = None
    if company:
        year = int(month.split("-")[0])
        ytd_txns = get_transactions_ytd(company.id, year)
        summary = calculate_tax_summary(ytd_txns, period_type="ytd")

    return templates.TemplateResponse(
        "calculator.html",
        {
            "request": request,
            "company": company,
            "companies": all_companies,
            "summary": summary,
            "selected_month": month,
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
