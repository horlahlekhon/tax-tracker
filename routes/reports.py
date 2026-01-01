from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from models import TaxSummary, FilingChecklist, FilingChecklistUpdate
from utils.pdf_generator import generate_balance_sheet_pdf, get_pdf_filename
from utils.csv_exporter import (
    generate_transactions_csv,
    generate_vat_summary_csv,
    generate_cit_summary_csv,
    get_export_filename,
)
from utils.storage import (
    get_company,
    get_transactions,
    get_transactions_ytd,
    get_checklist,
    create_or_update_checklist,
)
from utils.tax_calculator import (
    calculate_tax_summary,
    calculate_salary_dividend_split,
)

router = APIRouter()


class SalaryDividendRequest(BaseModel):
    """Request model for salary/dividend calculator."""
    desired_take_home: Decimal
    taxable_profit: Optional[Decimal] = None


class SalaryDividendResponse(BaseModel):
    """Response model for salary/dividend calculator."""
    desired_take_home: Decimal
    recommended_salary: Decimal
    recommended_dividend: Decimal
    salary_tax: Decimal
    dividend_wht: Decimal
    total_tax_optimal: Decimal
    all_salary_gross: Decimal
    all_salary_tax: Decimal
    tax_savings: Decimal


class TopVendorClient(BaseModel):
    """Model for top vendor/client data."""
    name: str
    total_amount: Decimal
    transaction_count: int


class VendorClientInsights(BaseModel):
    """Response model for vendor/client insights."""
    top_vendors: list[TopVendorClient]
    top_clients: list[TopVendorClient]


@router.get("/dashboard")
async def get_dashboard_data(
    company_id: str,
    month: Optional[str] = None,
    period: str = "month",
) -> TaxSummary:
    """Get dashboard tax summary data for a company."""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get current month if not specified
    if not month:
        month = datetime.now().strftime("%Y-%m")

    # Get transactions for the selected period
    if period == "ytd":
        year = int(month.split("-")[0])
        txns = get_transactions_ytd(company_id, year)
    else:
        txns = get_transactions(company_id=company_id, month=month)

    # For threshold calculations, use YTD revenue
    year = int(month.split("-")[0])
    ytd_txns = get_transactions_ytd(company_id, year)
    ytd_summary = calculate_tax_summary(ytd_txns, period_type="ytd")
    annual_revenue = ytd_summary.total_revenue

    # Calculate summary for selected period
    summary = calculate_tax_summary(
        txns,
        period_type=period,
        annual_revenue_override=annual_revenue,
    )

    return summary


@router.get("/tax-summary")
async def get_tax_summary(
    company_id: str,
    month: Optional[str] = None,
    period: str = Query("month", pattern="^(month|ytd)$"),
) -> TaxSummary:
    """Get detailed tax summary for a company and period."""
    return await get_dashboard_data(company_id, month, period)


@router.get("/insights")
async def get_vendor_client_insights(
    company_id: str,
    month: Optional[str] = None,
    limit: int = 5,
) -> VendorClientInsights:
    """Get top vendors and clients for a company."""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get current month if not specified
    if not month:
        month = datetime.now().strftime("%Y-%m")

    transactions = get_transactions(company_id=company_id, month=month)

    # Aggregate by vendor/client
    vendor_totals: dict[str, dict] = {}
    client_totals: dict[str, dict] = {}

    for txn in transactions:
        if not txn.vendor_client:
            continue

        if txn.amount < 0:  # Expense - vendor
            name = txn.vendor_client
            if name not in vendor_totals:
                vendor_totals[name] = {"total": Decimal("0"), "count": 0}
            vendor_totals[name]["total"] += abs(txn.amount)
            vendor_totals[name]["count"] += 1
        else:  # Income - client
            name = txn.vendor_client
            if name not in client_totals:
                client_totals[name] = {"total": Decimal("0"), "count": 0}
            client_totals[name]["total"] += txn.amount
            client_totals[name]["count"] += 1

    # Sort and get top N
    top_vendors = sorted(
        [
            TopVendorClient(
                name=name,
                total_amount=data["total"],
                transaction_count=data["count"],
            )
            for name, data in vendor_totals.items()
        ],
        key=lambda x: x.total_amount,
        reverse=True,
    )[:limit]

    top_clients = sorted(
        [
            TopVendorClient(
                name=name,
                total_amount=data["total"],
                transaction_count=data["count"],
            )
            for name, data in client_totals.items()
        ],
        key=lambda x: x.total_amount,
        reverse=True,
    )[:limit]

    return VendorClientInsights(
        top_vendors=top_vendors,
        top_clients=top_clients,
    )


@router.post("/calculator/dividend")
async def calculate_dividend_split(
    request: SalaryDividendRequest,
) -> SalaryDividendResponse:
    """Calculate optimal salary/dividend split for tax optimization."""
    result = calculate_salary_dividend_split(
        desired_take_home=request.desired_take_home,
        taxable_profit=request.taxable_profit or Decimal("0"),
    )

    return SalaryDividendResponse(**result)


@router.get("/ytd-summary")
async def get_ytd_summary(
    company_id: str,
    year: Optional[int] = None,
) -> TaxSummary:
    """Get year-to-date tax summary for a company."""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not year:
        year = datetime.now().year

    transactions = get_transactions_ytd(company_id, year)
    summary = calculate_tax_summary(transactions, period_type="ytd")

    return summary


# Filing Checklist Endpoints

class ChecklistResponse(BaseModel):
    """Response model for filing checklist."""
    company_id: str
    month: str
    vat_filed: bool
    paye_remitted: bool
    wht_remitted: bool


@router.get("/checklist")
async def get_filing_checklist(
    company_id: str,
    month: Optional[str] = None,
) -> ChecklistResponse:
    """Get filing checklist for a company and month."""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not month:
        month = datetime.now().strftime("%Y-%m")

    checklist = get_checklist(company_id, month)

    if checklist:
        return ChecklistResponse(
            company_id=company_id,
            month=month,
            vat_filed=checklist.vat_filed,
            paye_remitted=checklist.paye_remitted,
            wht_remitted=checklist.wht_remitted,
        )
    else:
        # Return default empty checklist
        return ChecklistResponse(
            company_id=company_id,
            month=month,
            vat_filed=False,
            paye_remitted=False,
            wht_remitted=False,
        )


@router.put("/checklist")
async def update_filing_checklist(
    company_id: str,
    month: str,
    updates: FilingChecklistUpdate,
) -> ChecklistResponse:
    """Update filing checklist for a company and month."""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    checklist = create_or_update_checklist(
        company_id=company_id,
        month=month,
        updates=updates.model_dump(exclude_unset=True),
    )

    return ChecklistResponse(
        company_id=company_id,
        month=month,
        vat_filed=checklist.vat_filed,
        paye_remitted=checklist.paye_remitted,
        wht_remitted=checklist.wht_remitted,
    )


# PDF Download Endpoint

@router.get("/balance-sheet/pdf")
async def download_balance_sheet_pdf(
    company_id: str,
    month: Optional[str] = None,
) -> Response:
    """Generate and download balance sheet PDF for a company.

    Args:
        company_id: The company ID
        month: Month in YYYY-MM format (defaults to current month)

    Returns:
        PDF file as downloadable response
    """
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not month:
        month = datetime.now().strftime("%Y-%m")

    # Get transactions for the month
    transactions = get_transactions(company_id=company_id, month=month)

    # Get YTD revenue for threshold calculations
    year = int(month.split("-")[0])
    ytd_txns = get_transactions_ytd(company_id, year)
    ytd_summary = calculate_tax_summary(ytd_txns, period_type="ytd")
    annual_revenue = ytd_summary.total_revenue

    # Calculate tax summary for the month
    summary = calculate_tax_summary(
        transactions,
        period_type="month",
        annual_revenue_override=annual_revenue,
    )

    # Get filing checklist
    checklist = get_checklist(company_id, month)

    # Generate PDF
    pdf_bytes = generate_balance_sheet_pdf(
        company=company,
        month=month,
        summary=summary,
        checklist=checklist,
    )

    # Generate filename
    filename = get_pdf_filename(company.name, month)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# CSV Export Endpoints

@router.get("/export/transactions")
async def export_transactions_csv(
    company_id: str,
    month: Optional[str] = None,
    year: Optional[int] = None,
) -> Response:
    """Export transactions as CSV.

    Args:
        company_id: The company ID
        month: Optional month in YYYY-MM format (exports single month)
        year: Optional year (exports full year if no month specified)

    Returns:
        CSV file as downloadable response
    """
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Determine which transactions to export
    if month:
        transactions = get_transactions(company_id=company_id, month=month)
        filename = get_export_filename(company.name, "transactions", month=month)
    elif year:
        transactions = get_transactions_ytd(company_id, year)
        filename = get_export_filename(company.name, "transactions", year=year)
    else:
        # Default to current year
        year = datetime.now().year
        transactions = get_transactions_ytd(company_id, year)
        filename = get_export_filename(company.name, "transactions", year=year)

    csv_content = generate_transactions_csv(transactions, company.name)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/export/vat")
async def export_vat_summary_csv(
    company_id: str,
    year: Optional[int] = None,
) -> Response:
    """Export VAT summary as CSV.

    Args:
        company_id: The company ID
        year: Year for the report (defaults to current year)

    Returns:
        CSV file as downloadable response
    """
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not year:
        year = datetime.now().year

    transactions = get_transactions_ytd(company_id, year)
    csv_content = generate_vat_summary_csv(transactions, company.name, year)
    filename = get_export_filename(company.name, "vat-summary", year=year)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/export/cit")
async def export_cit_summary_csv(
    company_id: str,
    year: Optional[int] = None,
) -> Response:
    """Export annual CIT summary as CSV.

    Args:
        company_id: The company ID
        year: Year for the report (defaults to current year)

    Returns:
        CSV file as downloadable response
    """
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not year:
        year = datetime.now().year

    transactions = get_transactions_ytd(company_id, year)
    summary = calculate_tax_summary(transactions, period_type="ytd")
    csv_content = generate_cit_summary_csv(transactions, summary, company.name, year)
    filename = get_export_filename(company.name, "cit-summary", year=year)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
