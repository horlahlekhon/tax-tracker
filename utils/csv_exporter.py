"""CSV Export Utilities for Tax Tracker.

Generates CSV exports for transactions, VAT summaries, and CIT reports.
"""

import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import List

from models import Transaction, TaxSummary


def format_currency(amount: Decimal) -> str:
    """Format amount as plain number for CSV."""
    return f"{float(amount):.2f}"


def generate_transactions_csv(
    transactions: List[Transaction],
    company_name: str,
) -> str:
    """Generate CSV export of all transactions.

    Args:
        transactions: List of transactions to export
        company_name: Name of the company

    Returns:
        CSV content as string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Date",
        "Description",
        "Category",
        "Amount (₦)",
        "Type",
        "Vendor/Client",
        "Has Receipt",
        "Notes",
    ])

    # Data rows
    for txn in sorted(transactions, key=lambda x: x.date):
        txn_type = "Income" if txn.amount >= 0 else "Expense"
        writer.writerow([
            txn.date,
            txn.description,
            txn.category.value if txn.category else "",
            format_currency(abs(txn.amount)),
            txn_type,
            txn.vendor_client or "",
            "Yes" if txn.has_receipt else "No",
            txn.notes or "",
        ])

    return output.getvalue()


def generate_vat_summary_csv(
    transactions: List[Transaction],
    company_name: str,
    year: int,
) -> str:
    """Generate monthly VAT summary CSV for the year.

    Args:
        transactions: List of transactions for the year
        company_name: Name of the company
        year: Year for the report

    Returns:
        CSV content as string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Group transactions by month
    monthly_data: dict[str, dict] = {}

    for txn in transactions:
        month = txn.date[:7]  # YYYY-MM
        if month not in monthly_data:
            monthly_data[month] = {
                "revenue": Decimal("0"),
                "vat_payable": Decimal("0"),
            }

        if txn.amount > 0:
            monthly_data[month]["revenue"] += txn.amount

    # Calculate VAT for each month (7.5% on revenue)
    VAT_RATE = Decimal("0.075")
    for month in monthly_data:
        monthly_data[month]["vat_payable"] = monthly_data[month]["revenue"] * VAT_RATE

    # Header
    writer.writerow([f"VAT Summary Report - {company_name} - {year}"])
    writer.writerow([])
    writer.writerow([
        "Month",
        "Revenue (₦)",
        "VAT Rate",
        "VAT Payable (₦)",
    ])

    # Data rows - sorted by month
    total_revenue = Decimal("0")
    total_vat = Decimal("0")

    for month in sorted(monthly_data.keys()):
        data = monthly_data[month]
        # Format month for display
        try:
            month_display = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        except ValueError:
            month_display = month

        writer.writerow([
            month_display,
            format_currency(data["revenue"]),
            "7.5%",
            format_currency(data["vat_payable"]),
        ])
        total_revenue += data["revenue"]
        total_vat += data["vat_payable"]

    # Totals row
    writer.writerow([])
    writer.writerow([
        "TOTAL",
        format_currency(total_revenue),
        "",
        format_currency(total_vat),
    ])

    # VAT threshold note
    VAT_THRESHOLD = Decimal("25000000")
    writer.writerow([])
    if total_revenue >= VAT_THRESHOLD:
        writer.writerow(["Note: Annual revenue exceeds ₦25,000,000 VAT threshold - VAT registration required"])
    else:
        remaining = VAT_THRESHOLD - total_revenue
        writer.writerow([f"Note: ₦{float(remaining):,.2f} below VAT threshold (₦25,000,000)"])

    return output.getvalue()


def generate_cit_summary_csv(
    transactions: List[Transaction],
    summary: TaxSummary,
    company_name: str,
    year: int,
) -> str:
    """Generate annual CIT summary CSV.

    Args:
        transactions: List of transactions for the year
        summary: Tax summary for the year
        company_name: Name of the company
        year: Year for the report

    Returns:
        CSV content as string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([f"Company Income Tax (CIT) Summary - {company_name} - {year}"])
    writer.writerow([])

    # Company Classification
    writer.writerow(["COMPANY CLASSIFICATION"])
    writer.writerow(["Company Size", summary.company_size.value])
    writer.writerow(["CIT Rate", f"{summary.cit_rate}%"])
    writer.writerow([])

    # Revenue Section
    writer.writerow(["REVENUE"])
    writer.writerow(["Total Revenue", format_currency(summary.total_revenue)])
    writer.writerow([])

    # Expenses Section
    writer.writerow(["EXPENSES"])
    writer.writerow(["Direct Expenses", format_currency(summary.direct_expenses)])
    writer.writerow(["Operating Expenses", format_currency(summary.operating_expenses)])
    writer.writerow(["Capital Expenses", format_currency(summary.capital_expenses)])
    writer.writerow(["Total Deductible Expenses", format_currency(summary.deductible_expenses)])
    writer.writerow([])
    writer.writerow(["Non-Deductible Expenses", format_currency(summary.non_deductible_expenses)])
    writer.writerow([])

    # Tax Calculations
    writer.writerow(["TAX CALCULATIONS"])
    writer.writerow(["Taxable Profit", format_currency(summary.taxable_profit)])
    writer.writerow([f"CIT ({summary.cit_rate}%)", format_currency(summary.cit_amount)])

    if summary.vat_required:
        writer.writerow(["VAT Payable (7.5%)", format_currency(summary.vat_amount)])

    writer.writerow([])
    writer.writerow(["Net Profit After Tax", format_currency(summary.net_profit)])
    writer.writerow([])

    # CIT Rate Explanation
    writer.writerow(["CIT RATE TIERS"])
    writer.writerow(["Small Company (≤ ₦50M revenue)", "0%"])
    writer.writerow(["Medium Company (₦50M - ₦100M revenue)", "20%"])
    writer.writerow(["Large Company (> ₦100M revenue)", "30%"])
    writer.writerow([])

    # Threshold Progress
    writer.writerow(["THRESHOLD STATUS"])
    writer.writerow(["VAT Threshold Progress", f"{summary.vat_threshold_percent}%"])
    writer.writerow(["Small Company Threshold Progress", f"{summary.small_company_threshold_percent}%"])
    writer.writerow([])

    # Generation timestamp
    writer.writerow([f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}"])

    return output.getvalue()


def get_export_filename(
    company_name: str,
    export_type: str,
    year: int | None = None,
    month: str | None = None,
) -> str:
    """Generate standardized export filename.

    Args:
        company_name: Name of the company
        export_type: Type of export (transactions, vat-summary, cit-summary)
        year: Optional year for annual reports
        month: Optional month for monthly reports

    Returns:
        Filename like "Company Name - Transactions - December 2024.csv"
    """
    # Clean company name for filename
    clean_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).strip()

    if month:
        try:
            date = datetime.strptime(month, "%Y-%m")
            period = date.strftime("%B %Y")
        except ValueError:
            period = month
    elif year:
        period = str(year)
    else:
        period = datetime.now().strftime("%Y")

    type_labels = {
        "transactions": "Transactions",
        "vat-summary": "VAT Summary",
        "cit-summary": "CIT Summary",
    }

    label = type_labels.get(export_type, export_type.title())

    return f"{clean_name} - {label} - {period}.csv"
