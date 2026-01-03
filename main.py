import datetime
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from routes import companies, transactions, reports, gdrive, pdf_converter, assets, auth
from routes.auth import get_current_company, AUTH_COOKIE_NAME
from utils.storage import get_companies, get_company, get_transactions, get_transactions_ytd, get_total_assets_value
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
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(gdrive.router, prefix="/gdrive", tags=["gdrive"])
app.include_router(pdf_converter.router, prefix="/pdf-converter", tags=["pdf-converter"])
app.include_router(assets.router, prefix="/assets", tags=["assets"])


# Public paths that don't require authentication
PUBLIC_PATHS = {"/auth/signin", "/auth/register", "/auth/signout", "/health"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Middleware to check authentication and redirect to sign-in if needed."""
    path = request.url.path

    # Allow public paths and static files
    if path in PUBLIC_PATHS or path.startswith("/static") or path.startswith("/auth"):
        return await call_next(request)

    # Check if user is authenticated
    company_id = request.cookies.get(AUTH_COOKIE_NAME)
    if not company_id:
        return RedirectResponse(url="/auth/signin", status_code=302)

    # Verify the company still exists
    company = get_company(company_id)
    if not company:
        response = RedirectResponse(url="/auth/signin", status_code=302)
        response.delete_cookie(key=AUTH_COOKIE_NAME)
        return response

    return await call_next(request)


@app.get("/")
async def home(
    request: Request,
    month: Optional[str] = None,
    period: str = "month",
):
    """Dashboard home page."""
    # Get authenticated company
    company = get_current_company(request)

    # Get current month if not specified
    if not month:
        month = datetime.datetime.now().strftime("%Y-%m")

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

        # Get total assets for threshold calculation
        total_assets = get_total_assets_value(company.id)

        ytd_summary = calculate_tax_summary(
            ytd_txns, period_type="ytd", total_assets=total_assets
        )
        annual_revenue = ytd_summary.total_revenue

        # Calculate summary for selected period
        summary = calculate_tax_summary(
            txns,
            period_type=period,
            annual_revenue_override=annual_revenue,
            total_assets=total_assets,
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "company": company,
            "summary": summary,
            "selected_month": month,
            "selected_period": period,
        },
    )


@app.get("/calculator")
async def calculator(
    request: Request,
    month: Optional[str] = None,
):
    """Salary/Dividend Calculator page."""
    # Get authenticated company
    company = get_current_company(request)

    # Get current month if not specified
    if not month:
        month = datetime.datetime.now().strftime("%Y-%m")

    # Calculate tax summary if company exists
    summary = None
    if company:
        year = int(month.split("-")[0])
        ytd_txns = get_transactions_ytd(company.id, year)
        total_assets = get_total_assets_value(company.id)
        summary = calculate_tax_summary(
            ytd_txns, period_type="ytd", total_assets=total_assets
        )

    return templates.TemplateResponse(
        "calculator.html",
        {
            "request": request,
            "company": company,
            "summary": summary,
            "selected_month": month,
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
