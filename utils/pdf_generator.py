"""PDF Generator for Balance Sheet Reports.

Uses ReportLab to generate professional balance sheet PDFs.
"""

import io
from datetime import datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from models import Company, TaxSummary, FilingChecklist


def format_currency(amount: Decimal) -> str:
    """Format amount as Nigerian Naira."""
    return f"₦{float(amount):,.2f}"


def format_month(month_str: str) -> str:
    """Format YYYY-MM to readable month name."""
    try:
        date = datetime.strptime(month_str, "%Y-%m")
        return date.strftime("%B %Y")
    except ValueError:
        return month_str


def generate_balance_sheet_pdf(
    company: Company,
    month: str,
    summary: TaxSummary,
    checklist: FilingChecklist | None = None,
) -> bytes:
    """Generate a balance sheet PDF for a company.

    Args:
        company: Company information
        month: Month in YYYY-MM format
        summary: Tax summary data
        checklist: Optional filing checklist

    Returns:
        PDF file as bytes
    """
    buffer = io.BytesIO()

    # Create document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    # Styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=6,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#166534'),
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12,
        alignment=TA_CENTER,
        textColor=colors.gray,
    )

    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor('#1e40af'),
    )

    normal_style = styles['Normal']

    # Build document content
    elements = []

    # Header
    elements.append(Paragraph("BALANCE SHEET", title_style))
    elements.append(Paragraph(f"{company.name}", subtitle_style))
    elements.append(Paragraph(f"TIN: {company.tin}", subtitle_style))
    elements.append(Paragraph(f"Period: {format_month(month)}", subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#166534')))
    elements.append(Spacer(1, 20))

    # Company Size Badge
    size_text = f"Company Classification: {summary.company_size.value} Company"
    if summary.company_size.value == "Small":
        size_note = "(Revenue ≤ ₦50,000,000 - 0% CIT)"
    elif summary.company_size.value == "Medium":
        size_note = "(Revenue ₦50M - ₦100M - 20% CIT)"
    else:
        size_note = "(Revenue > ₦100,000,000 - 30% CIT)"

    elements.append(Paragraph(f"<b>{size_text}</b> {size_note}", normal_style))
    elements.append(Spacer(1, 15))

    # Revenue Section
    elements.append(Paragraph("REVENUE", section_style))

    revenue_data = [
        ["Description", "Amount"],
        ["Total Revenue", format_currency(summary.total_revenue)],
    ]

    revenue_table = Table(revenue_data, colWidths=[4 * inch, 2 * inch])
    revenue_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dcfce7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#166534')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ]))
    elements.append(revenue_table)
    elements.append(Spacer(1, 15))

    # Expenses Section
    elements.append(Paragraph("EXPENSES", section_style))

    expenses_data = [
        ["Category", "Amount", "Deductible"],
        ["Direct Expenses", format_currency(summary.direct_expenses), "Yes"],
        ["Operating Expenses", format_currency(summary.operating_expenses), "Yes"],
        ["Capital Expenses", format_currency(summary.capital_expenses), "Yes"],
        ["Non-Deductible Expenses", format_currency(summary.non_deductible_expenses), "No"],
        ["", "", ""],
        ["Total Deductible Expenses", format_currency(summary.deductible_expenses), ""],
    ]

    expenses_table = Table(expenses_data, colWidths=[3 * inch, 2 * inch, 1 * inch])
    expenses_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fee2e2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#991b1b')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, 4), colors.white),
        ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#fef2f2')),
        ('TEXTCOLOR', (0, 4), (-1, 4), colors.HexColor('#991b1b')),
        ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0, 6), (-1, 6), 'Helvetica-Bold'),
    ]))
    elements.append(expenses_table)
    elements.append(Spacer(1, 15))

    # Tax Calculations Section
    elements.append(Paragraph("TAX CALCULATIONS", section_style))

    tax_data = [
        ["Item", "Amount"],
        ["Taxable Profit (Revenue - Deductible Expenses)", format_currency(summary.taxable_profit)],
        [f"Company Income Tax ({summary.cit_rate}%)", format_currency(summary.cit_amount)],
        ["Net Profit After Tax", format_currency(summary.net_profit)],
    ]

    # Add VAT row if applicable
    if summary.vat_required:
        tax_data.insert(3, ["VAT Payable (7.5%)", format_currency(summary.vat_amount)])

    tax_table = Table(tax_data, colWidths=[4 * inch, 2 * inch])
    tax_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dbeafe')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#dcfce7')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#166534')),
    ]))
    elements.append(tax_table)
    elements.append(Spacer(1, 15))

    # VAT Status
    elements.append(Paragraph("VAT STATUS", section_style))

    vat_status = "Required" if summary.vat_required else "Not Required"
    vat_note = "Annual revenue exceeds ₦25,000,000" if summary.vat_required else "Annual revenue below ₦25,000,000 threshold"

    vat_data = [
        ["Status", "Details"],
        ["VAT Registration", vat_status],
        ["Threshold Progress", f"{summary.vat_threshold_percent}% of ₦25,000,000"],
        ["Note", vat_note],
    ]

    vat_table = Table(vat_data, colWidths=[2 * inch, 4 * inch])
    vat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fef3c7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#92400e')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ]))
    elements.append(vat_table)
    elements.append(Spacer(1, 15))

    # Filing Checklist Section
    elements.append(Paragraph("MONTHLY FILING CHECKLIST", section_style))

    if checklist:
        vat_status = "✓ Filed" if checklist.vat_filed else "✗ Pending"
        paye_status = "✓ Remitted" if checklist.paye_remitted else "✗ Pending"
        wht_status = "✓ Remitted" if checklist.wht_remitted else "✗ Pending"
    else:
        vat_status = "✗ Pending"
        paye_status = "✗ Pending"
        wht_status = "✗ Pending"

    checklist_data = [
        ["Tax Obligation", "Status"],
        ["VAT Return", vat_status],
        ["PAYE (Pay-As-You-Earn)", paye_status],
        ["WHT (Withholding Tax)", wht_status],
    ]

    checklist_table = Table(checklist_data, colWidths=[4 * inch, 2 * inch])
    checklist_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e7ff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#3730a3')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ]))
    elements.append(checklist_table)
    elements.append(Spacer(1, 15))

    # Audit Readiness
    elements.append(Paragraph("AUDIT READINESS", section_style))

    audit_data = [
        ["Metric", "Value"],
        ["Transactions with Receipts", f"{summary.receipt_percentage}%"],
        ["Status", "Good" if summary.receipt_percentage >= 80 else ("Fair" if summary.receipt_percentage >= 50 else "Needs Improvement")],
    ]

    audit_table = Table(audit_data, colWidths=[4 * inch, 2 * inch])
    audit_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3e8ff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#6b21a8')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ]))
    elements.append(audit_table)
    elements.append(Spacer(1, 30))

    # Footer
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
    elements.append(Spacer(1, 10))

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray,
        alignment=TA_CENTER,
    )

    generated_date = datetime.now().strftime("%B %d, %Y at %H:%M")
    elements.append(Paragraph(f"Generated on {generated_date}", footer_style))
    elements.append(Paragraph("Nigerian LLC Tax Tracker", footer_style))

    # Build PDF
    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


def get_pdf_filename(company_name: str, month: str) -> str:
    """Generate standardized PDF filename.

    Args:
        company_name: Name of the company
        month: Month in YYYY-MM format

    Returns:
        Filename like "Company Name - Balance Sheet - December 2024.pdf"
    """
    formatted_month = format_month(month)
    # Clean company name for filename
    clean_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).strip()
    return f"{clean_name} - Balance Sheet - {formatted_month}.pdf"
