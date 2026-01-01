"""PDF Bank Statement Parser.

Parses bank PDF statements and converts them to CSV format.
Supports: Zenith Bank, GTBank
"""

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional

import pdfplumber


class SupportedBank(str, Enum):
    """Supported banks for PDF statement parsing."""
    ZENITH = "zenith"
    GTBANK = "gtbank"


def clean_amount(amount_str: str) -> Optional[Decimal]:
    """Parse and clean amount string to Decimal.

    Args:
        amount_str: Amount string potentially with commas

    Returns:
        Decimal amount or None if invalid/empty
    """
    if not amount_str or amount_str.strip() in ('', '0.00', '-'):
        return None

    # Remove commas and whitespace
    cleaned = amount_str.strip().replace(',', '')

    # Handle negative values (already negative in PDF)
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def clean_description(description: str) -> str:
    """Clean and normalize transaction description.

    Args:
        description: Raw description text

    Returns:
        Cleaned description string
    """
    if not description:
        return ""

    # Replace multiple whitespace/newlines with single space
    cleaned = re.sub(r'\s+', ' ', description)

    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    return cleaned


def is_skip_row(row: list) -> bool:
    """Check if this row should be skipped.

    Args:
        row: List of cell values

    Returns:
        True if row should be skipped
    """
    if not row or len(row) == 0:
        return True

    # Join all cells to check content
    row_text = ' '.join(str(cell) if cell else '' for cell in row).lower()

    # Skip header row
    if 'date' in row_text and 'description' in row_text and 'debit' in row_text:
        return True

    # Skip opening balance
    if 'opening balance' in row_text:
        return True

    # Skip totals rows
    if 'totals' in row_text or 'total (cleared' in row_text:
        return True

    # Skip empty rows
    if all(not cell or str(cell).strip() == '' for cell in row):
        return True

    return False


def is_valid_date_zenith(date_str: str) -> bool:
    """Check if string looks like a valid Zenith Bank date DD/MM/YYYY.

    Args:
        date_str: String to check

    Returns:
        True if valid date format
    """
    if not date_str:
        return False

    # Match DD/MM/YYYY pattern
    pattern = r'^\d{2}/\d{2}/\d{4}$'
    return bool(re.match(pattern, date_str.strip()))


def is_valid_date_gtbank(date_str: str) -> bool:
    """Check if string looks like a valid GTBank date DD-MMM-YYYY.

    Args:
        date_str: String to check

    Returns:
        True if valid date format (e.g., 01-Dec-2025)
    """
    if not date_str:
        return False

    # Match DD-MMM-YYYY pattern (e.g., 01-Dec-2025)
    pattern = r'^\d{2}-[A-Za-z]{3}-\d{4}$'
    return bool(re.match(pattern, date_str.strip()))


def convert_gtbank_date_to_standard(date_str: str) -> str:
    """Convert GTBank date format (DD-MMM-YYYY) to standard format (DD/MM/YYYY).

    Args:
        date_str: Date string in GTBank format (e.g., 01-Dec-2025)

    Returns:
        Date string in DD/MM/YYYY format (e.g., 01/12/2025)
    """
    month_map = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }

    parts = date_str.strip().split('-')
    if len(parts) != 3:
        return date_str

    day = parts[0]
    month = month_map.get(parts[1].lower(), '01')
    year = parts[2]

    return f"{day}/{month}/{year}"


def parse_zenith_bank_statement(pdf_content: bytes) -> list[dict]:
    """Extract transactions from Zenith Bank PDF statement.

    Args:
        pdf_content: PDF file content as bytes

    Returns:
        List of transaction dictionaries with keys:
        - date: Transaction date (DD/MM/YYYY)
        - description: Cleaned transaction description
        - debit: Debit amount (Decimal or None)
        - credit: Credit amount (Decimal or None)
        - balance: Running balance (Decimal)
    """
    transactions = []

    with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
        for page in pdf.pages:
            # Extract tables from the page
            tables = page.extract_tables()

            for table in tables:
                if not table:
                    continue

                current_transaction = None

                for row in table:
                    if not row or is_skip_row(row):
                        continue

                    # Zenith Bank format: DATE, DESCRIPTION, DEBIT, CREDIT, VALUE DATE, BALANCE
                    # We need at least 6 columns
                    if len(row) < 6:
                        # This might be a continuation line for description
                        if current_transaction and row[1]:
                            # Append to current description
                            desc_addition = clean_description(str(row[1]))
                            current_transaction['description'] += ' ' + desc_addition
                        continue

                    date_cell = str(row[0]).strip() if row[0] else ''
                    description_cell = str(row[1]).strip() if row[1] else ''
                    debit_cell = str(row[2]).strip() if row[2] else ''
                    credit_cell = str(row[3]).strip() if row[3] else ''
                    # value_date is row[4] - we don't need it
                    balance_cell = str(row[5]).strip() if row[5] else ''

                    # Check if this is a new transaction (has a valid date)
                    if is_valid_date_zenith(date_cell):
                        # Save previous transaction if exists
                        if current_transaction:
                            transactions.append(current_transaction)

                        # Start new transaction
                        debit = clean_amount(debit_cell)
                        credit = clean_amount(credit_cell)
                        balance = clean_amount(balance_cell)

                        # Skip if no valid amounts
                        if debit is None and credit is None:
                            current_transaction = None
                            continue

                        current_transaction = {
                            'date': date_cell,
                            'description': clean_description(description_cell),
                            'debit': debit,
                            'credit': credit,
                            'balance': balance,
                        }
                    elif current_transaction and description_cell:
                        # This is a continuation of the description
                        desc = clean_description(description_cell)
                        current_transaction['description'] += ' ' + desc

                # Don't forget the last transaction
                if current_transaction:
                    transactions.append(current_transaction)
                    current_transaction = None

    return transactions


def is_gtbank_skip_row(row: list) -> bool:
    """Check if this GTBank row should be skipped.

    Args:
        row: List of cell values

    Returns:
        True if row should be skipped
    """
    if not row or len(row) == 0:
        return True

    # Join all cells to check content
    row_text = ' '.join(str(cell) if cell else '' for cell in row).lower()

    # Skip header row
    if 'trans. date' in row_text and 'debits' in row_text and 'credits' in row_text:
        return True

    # Skip opening balance row (typically in header section)
    if 'opening balance' in row_text:
        return True

    # Skip account info rows
    if 'statement period' in row_text or 'branch name' in row_text:
        return True
    if 'account no' in row_text or 'account type' in row_text:
        return True
    if 'internal reference' in row_text or 'currency' in row_text:
        return True

    # Skip empty rows
    if all(not cell or str(cell).strip() == '' for cell in row):
        return True

    return False


def parse_gtbank_statement(pdf_content: bytes, password: str = None) -> list[dict]:
    """Extract transactions from GTBank PDF statement.

    Args:
        pdf_content: PDF file content as bytes
        password: Optional password for encrypted PDFs

    Returns:
        List of transaction dictionaries with keys:
        - date: Transaction date (DD/MM/YYYY)
        - description: Cleaned transaction description
        - debit: Debit amount (Decimal or None)
        - credit: Credit amount (Decimal or None)
        - balance: Running balance (Decimal)
    """
    transactions = []

    open_kwargs = {}
    if password:
        open_kwargs['password'] = password

    with pdfplumber.open(io.BytesIO(pdf_content), **open_kwargs) as pdf:
        for page in pdf.pages:
            # Extract tables from the page
            tables = page.extract_tables()

            for table in tables:
                if not table:
                    continue

                current_transaction = None

                for row in table:
                    if not row or is_gtbank_skip_row(row):
                        continue

                    # GTBank format: Trans. Date, Value Date, Reference, Debits, Credits, Balance, Originating Branch, Remarks
                    # We need at least 8 columns for GTBank
                    if len(row) < 7:
                        # This might be a continuation line for description
                        if current_transaction and len(row) > 0 and row[-1]:
                            # Append to current description (Remarks is last column)
                            desc_addition = clean_description(str(row[-1]))
                            if desc_addition:
                                current_transaction['description'] += ' ' + desc_addition
                        continue

                    date_cell = str(row[0]).strip() if row[0] else ''
                    # value_date is row[1] - we don't need it
                    # reference is row[2] - we don't need it
                    debit_cell = str(row[3]).strip() if row[3] else ''
                    credit_cell = str(row[4]).strip() if row[4] else ''
                    balance_cell = str(row[5]).strip() if row[5] else ''
                    # originating_branch is row[6] - we don't need it
                    remarks_cell = str(row[7]).strip() if len(row) > 7 and row[7] else ''

                    # Check if this is a new transaction (has a valid GTBank date)
                    if is_valid_date_gtbank(date_cell):
                        # Save previous transaction if exists
                        if current_transaction:
                            transactions.append(current_transaction)

                        # Start new transaction
                        debit = clean_amount(debit_cell)
                        credit = clean_amount(credit_cell)
                        balance = clean_amount(balance_cell)

                        # Skip if no valid amounts
                        if debit is None and credit is None:
                            current_transaction = None
                            continue

                        # Convert GTBank date to standard format
                        standard_date = convert_gtbank_date_to_standard(date_cell)

                        current_transaction = {
                            'date': standard_date,
                            'description': clean_description(remarks_cell),
                            'debit': debit,
                            'credit': credit,
                            'balance': balance,
                        }
                    elif current_transaction and remarks_cell:
                        # This is a continuation of the description
                        desc = clean_description(remarks_cell)
                        if desc:
                            current_transaction['description'] += ' ' + desc

                # Don't forget the last transaction
                if current_transaction:
                    transactions.append(current_transaction)
                    current_transaction = None

    return transactions


def parse_pdf_bank_statement(
    pdf_content: bytes,
    bank: SupportedBank = SupportedBank.ZENITH,
    password: str = None
) -> list[dict]:
    """Extract transactions from bank PDF statement.

    Args:
        pdf_content: PDF file content as bytes
        bank: The bank type (zenith or gtbank)
        password: Optional password for encrypted PDFs

    Returns:
        List of transaction dictionaries
    """
    if bank == SupportedBank.GTBANK:
        return parse_gtbank_statement(pdf_content, password)
    else:
        return parse_zenith_bank_statement(pdf_content)


def convert_to_csv(transactions: list[dict]) -> str:
    """Convert transactions to CSV string.

    Args:
        transactions: List of transaction dictionaries

    Returns:
        CSV content as string with columns:
        - Transaction Date
        - Narration
        - Amount (negative for debits, positive for credits)
        - Running Balance
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['Transaction Date', 'Narration', 'Amount', 'Running Balance'])

    for txn in transactions:
        date = txn['date']
        narration = txn['description']

        # Calculate amount: debit is negative (money out), credit is positive (money in)
        if txn['debit'] and txn['debit'] > 0:
            amount = -txn['debit']
        elif txn['credit'] and txn['credit'] > 0:
            amount = txn['credit']
        else:
            # If both are 0 or None, skip or use 0
            amount = Decimal('0')

        balance = txn['balance'] if txn['balance'] else Decimal('0')

        # Format amounts with 2 decimal places, no commas
        amount_str = f"{amount:.2f}"
        balance_str = f"{balance:.2f}"

        writer.writerow([date, narration, amount_str, balance_str])

    return output.getvalue()


def parse_and_convert(
    pdf_content: bytes,
    bank: SupportedBank = SupportedBank.ZENITH,
    password: str = None
) -> str:
    """Parse PDF bank statement and convert to CSV.

    Args:
        pdf_content: PDF file content as bytes
        bank: The bank type (zenith or gtbank)
        password: Optional password for encrypted PDFs

    Returns:
        CSV content as string

    Raises:
        ValueError: If no valid transactions found
    """
    transactions = parse_pdf_bank_statement(pdf_content, bank, password)

    if not transactions:
        raise ValueError("No valid transactions found in PDF")

    return convert_to_csv(transactions)
