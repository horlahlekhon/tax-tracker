"""Nigerian LLC Tax Calculator.

Implements Nigerian tax rules for:
- Company Income Tax (CIT) with tiered rates
- Value Added Tax (VAT) at 7.5%
- Withholding Tax (WHT) on dividends at 10%
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from models import (
    Transaction,
    TransactionCategory,
    TaxSummary,
    CompanySize,
)

# Nigerian Tax Thresholds (in Naira)
VAT_THRESHOLD = Decimal("25000000")  # ₦25 million
SMALL_COMPANY_REVENUE_THRESHOLD = Decimal("25000000")  # ₦25 million
SMALL_COMPANY_ASSET_THRESHOLD = Decimal("250000000")  # ₦250 million
MEDIUM_COMPANY_THRESHOLD = Decimal("100000000")  # ₦100 million

# Tax Rates
CIT_RATE_SMALL = Decimal("0")  # 0% for small companies
CIT_RATE_MEDIUM = Decimal("0.20")  # 20% for medium companies
CIT_RATE_LARGE = Decimal("0.30")  # 30% for large companies

VAT_RATE = Decimal("0.075")  # 7.5%
DIVIDEND_WHT_RATE = Decimal("0.10")  # 10%


def round_naira(amount: Decimal) -> Decimal:
    """Round to 2 decimal places (kobo)."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def determine_company_size(
    annual_revenue: Decimal,
    total_assets: Decimal = Decimal("0"),
) -> CompanySize:
    """Determine company size based on annual revenue AND total assets.

    Nigerian CIT tiers (Updated):
    - Small: Revenue ≤ ₦25,000,000 AND Assets ≤ ₦250,000,000 (0% CIT)
    - Medium: Revenue ₦25,000,001 - ₦100,000,000 or exceeds asset threshold (20% CIT)
    - Large: Revenue > ₦100,000,000 (30% CIT)
    """
    # Small company requires BOTH conditions to be met
    if (annual_revenue <= SMALL_COMPANY_REVENUE_THRESHOLD and
            total_assets <= SMALL_COMPANY_ASSET_THRESHOLD):
        return CompanySize.SMALL
    elif annual_revenue <= MEDIUM_COMPANY_THRESHOLD:
        return CompanySize.MEDIUM
    else:
        return CompanySize.LARGE


def get_cit_rate(company_size: CompanySize) -> Decimal:
    """Get Company Income Tax rate based on company size."""
    if company_size == CompanySize.SMALL:
        return CIT_RATE_SMALL
    elif company_size == CompanySize.MEDIUM:
        return CIT_RATE_MEDIUM
    else:
        return CIT_RATE_LARGE


def calculate_cit(taxable_profit: Decimal, company_size: CompanySize) -> Decimal:
    """Calculate Company Income Tax.

    Args:
        taxable_profit: Profit after deducting allowable expenses
        company_size: Size classification of the company

    Returns:
        CIT amount owed
    """
    if taxable_profit <= 0:
        return Decimal("0")

    rate = get_cit_rate(company_size)
    return round_naira(taxable_profit * rate)


def calculate_vat(revenue: Decimal, input_vat: Decimal = Decimal("0")) -> tuple[bool, Decimal]:
    """Calculate VAT liability.

    VAT is required when annual revenue exceeds ₦25 million.
    VAT Rate: 7.5%
    VAT Payable = Output VAT (collected) - Input VAT (paid)

    Args:
        revenue: Total revenue for the period
        input_vat: VAT paid on purchases (claimable)

    Returns:
        Tuple of (is_vat_required, vat_payable)
    """
    is_required = revenue > VAT_THRESHOLD

    if not is_required:
        return False, Decimal("0")

    output_vat = round_naira(revenue * VAT_RATE)
    vat_payable = round_naira(output_vat - input_vat)

    # VAT payable cannot be negative (would be a refund situation)
    if vat_payable < 0:
        vat_payable = Decimal("0")

    return True, vat_payable


def calculate_dividend_wht(dividend_amount: Decimal) -> Decimal:
    """Calculate Withholding Tax on dividends.

    Dividend WHT is 10% and is a final tax.

    Args:
        dividend_amount: Gross dividend amount

    Returns:
        WHT amount to be withheld
    """
    if dividend_amount <= 0:
        return Decimal("0")

    return round_naira(dividend_amount * DIVIDEND_WHT_RATE)


def categorize_transactions(transactions: list[Transaction]) -> dict[str, Decimal]:
    """Categorize transactions and sum by category.

    Args:
        transactions: List of transactions to categorize

    Returns:
        Dictionary with totals for each category
    """
    totals = {
        "income": Decimal("0"),
        "direct_expenses": Decimal("0"),
        "operating_expenses": Decimal("0"),
        "capital_expenses": Decimal("0"),
        "non_deductible": Decimal("0"),
    }

    for txn in transactions:
        amount = abs(txn.amount)

        if txn.category == TransactionCategory.INCOME:
            totals["income"] += amount
        elif txn.category == TransactionCategory.DIRECT_EXPENSES:
            totals["direct_expenses"] += amount
        elif txn.category == TransactionCategory.OPERATING_EXPENSES:
            totals["operating_expenses"] += amount
        elif txn.category == TransactionCategory.CAPITAL_EXPENSES:
            totals["capital_expenses"] += amount
        elif txn.category == TransactionCategory.NON_DEDUCTIBLE:
            totals["non_deductible"] += amount

    return totals


def calculate_tax_summary(
    transactions: list[Transaction],
    period_type: str = "month",
    annual_revenue_override: Optional[Decimal] = None,
    total_assets: Decimal = Decimal("0"),
) -> TaxSummary:
    """Calculate complete tax summary from transactions.

    Args:
        transactions: List of transactions for the period
        period_type: "month" or "ytd" (year-to-date)
        annual_revenue_override: Override for annual revenue (for threshold calculations)
        total_assets: Total asset value for company size determination

    Returns:
        TaxSummary with all calculations
    """
    # Categorize transactions
    totals = categorize_transactions(transactions)

    total_revenue = totals["income"]
    direct_expenses = totals["direct_expenses"]
    operating_expenses = totals["operating_expenses"]
    capital_expenses = totals["capital_expenses"]
    non_deductible = totals["non_deductible"]

    # Deductible expenses (excludes non-deductible)
    deductible_expenses = direct_expenses + operating_expenses + capital_expenses

    # Taxable profit
    taxable_profit = total_revenue - deductible_expenses
    if taxable_profit < 0:
        taxable_profit = Decimal("0")

    # Use annual revenue for threshold calculations
    # If monthly, we might need to annualize or use override
    revenue_for_thresholds = annual_revenue_override or total_revenue

    # Determine company size based on revenue AND assets
    company_size = determine_company_size(revenue_for_thresholds, total_assets)

    # Calculate CIT
    cit_rate = get_cit_rate(company_size)
    cit_amount = calculate_cit(taxable_profit, company_size)

    # Calculate VAT
    vat_required, vat_amount = calculate_vat(revenue_for_thresholds)

    # Net profit after CIT
    net_profit = taxable_profit - cit_amount

    # Receipt percentage (audit readiness)
    total_txns = len(transactions)
    txns_with_receipt = sum(1 for t in transactions if t.has_receipt)
    receipt_percentage = int((txns_with_receipt / total_txns * 100) if total_txns > 0 else 0)

    # Threshold progress percentages
    vat_threshold_percent = int(min((revenue_for_thresholds / VAT_THRESHOLD * 100), 100))
    small_company_threshold_percent = int(min((revenue_for_thresholds / SMALL_COMPANY_REVENUE_THRESHOLD * 100), 100))
    asset_threshold_percent = int(min((total_assets / SMALL_COMPANY_ASSET_THRESHOLD * 100), 100))

    return TaxSummary(
        total_revenue=round_naira(total_revenue),
        direct_expenses=round_naira(direct_expenses),
        operating_expenses=round_naira(operating_expenses),
        capital_expenses=round_naira(capital_expenses),
        non_deductible_expenses=round_naira(non_deductible),
        deductible_expenses=round_naira(deductible_expenses),
        taxable_profit=round_naira(taxable_profit),
        company_size=company_size,
        cit_rate=int(cit_rate * 100),
        cit_amount=round_naira(cit_amount),
        vat_required=vat_required,
        vat_amount=round_naira(vat_amount),
        net_profit=round_naira(net_profit),
        receipt_percentage=receipt_percentage,
        vat_threshold_percent=vat_threshold_percent,
        small_company_threshold_percent=small_company_threshold_percent,
        total_assets=total_assets,
        asset_threshold_percent=asset_threshold_percent,
    )


def calculate_salary_dividend_split(
    desired_take_home: Decimal,
    taxable_profit: Decimal,
) -> dict:
    """Calculate optimal salary/dividend split for tax optimization.

    This helps determine the best way to take money out of the company
    to minimize overall tax burden.

    Args:
        desired_take_home: How much the owner wants to receive
        taxable_profit: Company's taxable profit available

    Returns:
        Dictionary with recommended split and tax comparison
    """
    # Simplified calculation - in reality, PAYE has graduated rates
    # For now, assume a flat effective rate for salary

    # Nigerian PAYE rates (simplified - actual is graduated)
    # First ₦300,000: 7%
    # Next ₦300,000: 11%
    # Next ₦500,000: 15%
    # Next ₦500,000: 19%
    # Next ₦1,600,000: 21%
    # Above ₦3,200,000: 24%

    # For simplicity, use an effective rate estimate
    EFFECTIVE_PAYE_RATE = Decimal("0.18")  # ~18% effective rate assumption

    # Scenario 1: All as salary
    all_salary_tax = round_naira(desired_take_home * EFFECTIVE_PAYE_RATE / (1 - EFFECTIVE_PAYE_RATE))
    all_salary_gross = desired_take_home + all_salary_tax

    # Scenario 2: Optimal split (minimize tax)
    # Strategy: Take minimum salary, rest as dividend
    # Dividends have 10% WHT (final tax)

    # Optimal: Take some as salary (up to lower tax brackets), rest as dividend
    optimal_salary = min(desired_take_home * Decimal("0.4"), Decimal("3200000"))  # 40% as salary, max ₦3.2M
    remaining_for_dividend = desired_take_home - optimal_salary

    # Tax on salary portion
    salary_tax = round_naira(optimal_salary * EFFECTIVE_PAYE_RATE)

    # Dividend needs to be grossed up for WHT
    # Net dividend = Gross dividend * (1 - 0.10)
    # Gross dividend = Net dividend / 0.90
    gross_dividend = round_naira(remaining_for_dividend / (1 - DIVIDEND_WHT_RATE))
    dividend_wht = calculate_dividend_wht(gross_dividend)

    total_tax_optimal = salary_tax + dividend_wht

    # Tax savings
    tax_savings = all_salary_tax - total_tax_optimal
    if tax_savings < 0:
        tax_savings = Decimal("0")
        # If all salary is better, recommend that
        optimal_salary = desired_take_home + all_salary_tax
        gross_dividend = Decimal("0")
        dividend_wht = Decimal("0")
        total_tax_optimal = all_salary_tax

    return {
        "desired_take_home": round_naira(desired_take_home),
        "recommended_salary": round_naira(optimal_salary),
        "recommended_dividend": round_naira(gross_dividend),
        "salary_tax": round_naira(salary_tax),
        "dividend_wht": round_naira(dividend_wht),
        "total_tax_optimal": round_naira(total_tax_optimal),
        "all_salary_gross": round_naira(all_salary_gross),
        "all_salary_tax": round_naira(all_salary_tax),
        "tax_savings": round_naira(tax_savings),
    }
