"""CSV parser for Nigerian bank statements."""

import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from models import Transaction, TransactionCategory, BankName


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date from various formats used by Nigerian banks."""
    date_formats = [
        "%d/%m/%Y",      # 31/12/2024
        "%d-%m-%Y",      # 31-12-2024
        "%Y-%m-%d",      # 2024-12-31
        "%d %b %Y",      # 31 Dec 2024
        "%d %B %Y",      # 31 December 2024
        "%d/%m/%y",      # 31/12/24
        "%d-%m-%y",      # 31-12-24
    ]

    date_str = date_str.strip()

    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def parse_amount(amount_str: str) -> Optional[Decimal]:
    """Parse amount from string, handling Nigerian bank formats."""
    if not amount_str:
        return None

    # Remove currency symbols, commas, and whitespace
    cleaned = amount_str.strip()
    cleaned = re.sub(r'[₦NGN,\s]', '', cleaned, flags=re.IGNORECASE)

    # Handle parentheses for negative numbers
    if cleaned.startswith('(') and cleaned.endswith(')'):
        cleaned = '-' + cleaned[1:-1]

    # Handle DR/CR suffixes
    is_debit = False
    if cleaned.upper().endswith('DR'):
        is_debit = True
        cleaned = cleaned[:-2]
    elif cleaned.upper().endswith('CR'):
        cleaned = cleaned[:-2]

    try:
        amount = Decimal(cleaned)
        if is_debit and amount > 0:
            amount = -amount
        return amount
    except (InvalidOperation, ValueError):
        return None


def detect_csv_format(headers: list[str]) -> dict:
    """Detect the CSV format based on headers."""
    headers_lower = [h.lower().strip() for h in headers]

    # Common column name mappings
    date_columns = ['date', 'transaction date', 'trans date', 'value date', 'posting date']
    description_columns = ['description', 'narration', 'particulars', 'remarks', 'details', 'transaction details']
    debit_columns = ['debit', 'dr', 'withdrawal', 'withdrawals', 'debit amount']
    credit_columns = ['credit', 'cr', 'deposit', 'deposits', 'credit amount', 'lodgement']
    amount_columns = ['amount', 'transaction amount', 'value']
    balance_columns = ['balance', 'running balance', 'available balance']

    mapping = {
        'date': None,
        'description': None,
        'debit': None,
        'credit': None,
        'amount': None,
        'balance': None,
    }

    for i, header in enumerate(headers_lower):
        if mapping['date'] is None and any(col in header for col in date_columns):
            mapping['date'] = i
        elif mapping['description'] is None and any(col in header for col in description_columns):
            mapping['description'] = i
        elif mapping['debit'] is None and any(col in header for col in debit_columns):
            mapping['debit'] = i
        elif mapping['credit'] is None and any(col in header for col in credit_columns):
            mapping['credit'] = i
        elif mapping['amount'] is None and any(col in header for col in amount_columns):
            mapping['amount'] = i
        elif mapping['balance'] is None and any(col in header for col in balance_columns):
            mapping['balance'] = i

    return mapping


def categorize_transaction(description: str, amount: Decimal) -> TransactionCategory:
    """Auto-categorize transaction based on description and amount."""
    description_lower = description.lower()

    # Income indicators
    income_keywords = [
        'salary', 'payment received', 'deposit', 'transfer from', 'credit',
        'received', 'inward', 'lodgement', 'refund', 'revenue', 'sales',
        'invoice payment', 'client payment'
    ]

    # Operating expense indicators
    operating_keywords = [
        'electricity', 'utility', 'internet', 'phone', 'rent', 'office',
        'stationery', 'maintenance', 'cleaning', 'security', 'insurance',
        'subscription', 'software', 'cloud', 'hosting', 'airtime'
    ]

    # Direct expense indicators
    direct_keywords = [
        'inventory', 'stock', 'goods', 'materials', 'supplies',
        'shipping', 'freight', 'logistics', 'delivery'
    ]

    # Capital expense indicators
    capital_keywords = [
        'equipment', 'machinery', 'vehicle', 'furniture', 'computer',
        'laptop', 'phone purchase', 'asset', 'renovation'
    ]

    # Non-deductible indicators
    non_deductible_keywords = [
        'fine', 'penalty', 'personal', 'donation', 'gift', 'entertainment'
    ]

    # Check for income (positive amounts or income keywords)
    if amount > 0:
        return TransactionCategory.INCOME

    # For expenses (negative amounts), categorize based on keywords
    for keyword in non_deductible_keywords:
        if keyword in description_lower:
            return TransactionCategory.NON_DEDUCTIBLE

    for keyword in capital_keywords:
        if keyword in description_lower:
            return TransactionCategory.CAPITAL_EXPENSES

    for keyword in direct_keywords:
        if keyword in description_lower:
            return TransactionCategory.DIRECT_EXPENSES

    for keyword in operating_keywords:
        if keyword in description_lower:
            return TransactionCategory.OPERATING_EXPENSES

    # Default to operating expenses for uncategorized expenses
    return TransactionCategory.OPERATING_EXPENSES


def parse_bank_statement(
    csv_content: str,
    company_id: str,
    bank: Optional[BankName] = None
) -> list[Transaction]:
    """Parse a bank statement CSV and return list of Transaction objects.

    Args:
        csv_content: The CSV content as a string
        company_id: The company ID to associate transactions with
        bank: Optional bank name to associate with all transactions
    """
    transactions = []

    # Try to detect delimiter
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(csv_content[:2048])
    except csv.Error:
        dialect = csv.excel  # Default to comma-separated

    reader = csv.reader(io.StringIO(csv_content), dialect)

    # Read all rows
    rows = list(reader)

    if len(rows) < 2:
        raise ValueError("CSV file must contain at least a header row and one data row")

    # Find header row (skip any blank rows at the start)
    header_idx = 0
    for i, row in enumerate(rows):
        if any(cell.strip() for cell in row):
            # Check if this looks like a header row
            row_str = ' '.join(row).lower()
            if 'date' in row_str or 'description' in row_str or 'amount' in row_str:
                header_idx = i
                break

    headers = rows[header_idx]
    data_rows = rows[header_idx + 1:]

    # Detect column mapping
    mapping = detect_csv_format(headers)

    if mapping['date'] is None:
        raise ValueError("Could not find date column in CSV")
    if mapping['description'] is None:
        raise ValueError("Could not find description column in CSV")
    if mapping['debit'] is None and mapping['credit'] is None and mapping['amount'] is None:
        raise ValueError("Could not find amount/debit/credit columns in CSV")

    for row in data_rows:
        # Skip empty rows
        if not any(cell.strip() for cell in row):
            continue

        # Skip rows that don't have enough columns
        if len(row) <= max(filter(None, mapping.values())):
            continue

        try:
            # Parse date
            date_str = row[mapping['date']].strip()
            parsed_date = parse_date(date_str)
            if not parsed_date:
                continue  # Skip rows with invalid dates

            # Parse description
            description = row[mapping['description']].strip()
            if not description:
                continue  # Skip rows without description

            # Parse amount
            amount = None
            if mapping['amount'] is not None:
                amount = parse_amount(row[mapping['amount']])
            elif mapping['debit'] is not None or mapping['credit'] is not None:
                debit = Decimal('0')
                credit = Decimal('0')

                if mapping['debit'] is not None and row[mapping['debit']].strip():
                    debit = parse_amount(row[mapping['debit']]) or Decimal('0')
                    if debit > 0:
                        debit = -debit  # Make debits negative

                if mapping['credit'] is not None and row[mapping['credit']].strip():
                    credit = parse_amount(row[mapping['credit']]) or Decimal('0')
                    if credit < 0:
                        credit = -credit  # Make credits positive

                amount = credit + debit  # debit is negative, credit is positive

            if amount is None or amount == 0:
                continue  # Skip rows without valid amount

            # Auto-categorize
            category = categorize_transaction(description, amount)

            # Create transaction
            transaction = Transaction(
                company_id=company_id,
                date=parsed_date.date(),
                description=description,
                amount=amount,
                category=category,
                bank=bank,
                has_receipt=False,
                vendor_client=None,
                notes="Imported from CSV",
            )
            transactions.append(transaction)

        except (IndexError, ValueError) as e:
            # Skip rows that can't be parsed
            continue

    return transactions
