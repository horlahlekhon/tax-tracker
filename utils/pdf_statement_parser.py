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
    KUDA = "kuda"


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


def is_valid_date_kuda(date_str: str) -> bool:
    """Check if string looks like a valid Kuda Bank date DD/MM/YY.

    Args:
        date_str: String to check

    Returns:
        True if valid date format (e.g., 03/01/25)
    """
    if not date_str:
        return False

    # Match DD/MM/YY pattern (Kuda uses 2-digit year)
    pattern = r'^\d{2}/\d{2}/\d{2}$'
    return bool(re.match(pattern, date_str.strip()))


def convert_kuda_date_to_standard(date_str: str) -> str:
    """Convert Kuda date format (DD/MM/YY) to standard format (DD/MM/YYYY).

    Args:
        date_str: Date string in Kuda format (e.g., 03/01/25)

    Returns:
        Date string in DD/MM/YYYY format (e.g., 03/01/2025)
    """
    parts = date_str.strip().split('/')
    if len(parts) != 3:
        return date_str

    day = parts[0]
    month = parts[1]
    year = parts[2]

    # Convert 2-digit year to 4-digit (assume 20xx for years 00-99)
    if len(year) == 2:
        year = '20' + year

    return f"{day}/{month}/{year}"


def clean_kuda_amount(amount_str: str) -> Optional[Decimal]:
    """Parse and clean Kuda amount string to Decimal.

    Kuda amounts have ₦ symbol and commas (e.g., ₦15,000.00)

    Args:
        amount_str: Amount string with ₦ symbol and commas

    Returns:
        Decimal amount or None if invalid/empty
    """
    if not amount_str or amount_str.strip() in ('', '-'):
        return None

    # Remove ₦ symbol, commas, and whitespace
    cleaned = amount_str.strip().replace('₦', '').replace(',', '').strip()

    if not cleaned or cleaned == '':
        return None

    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def is_kuda_skip_row(row: list) -> bool:
    """Check if this Kuda row should be skipped.

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
    if 'date/time' in row_text and 'money in' in row_text and 'money out' in row_text:
        return True

    # Skip summary section headers
    if 'opening balance' in row_text and 'closing balance' in row_text:
        return True
    if 'money in' in row_text and 'money out' in row_text and 'opening balance' in row_text:
        return True

    # Skip account info rows
    if 'spend account' in row_text and len(row_text) < 50:
        return True
    if 'account number' in row_text:
        return True

    # Skip empty rows
    if all(not cell or str(cell).strip() == '' for cell in row):
        return True

    return False


def parse_kuda_statement(pdf_content: bytes) -> list[dict]:
    """Extract transactions from Kuda Bank PDF statement.

    Kuda PDF uses text layout, not tables. Transactions span multiple lines.
    First line has: date, amount, category_start, to_from_start, description_start, balance
    Subsequent lines continue category, to_from, or description.

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

    # Pattern to match transaction start line
    # Example: "03/01/25 ₦15,000.00 outward Adebari Olalekan cash ₦1,639.54"
    # Example: "26/03/25 ₦20,000.00 inward Adebario Olalekan kip:prov/... ₦21,639.54"
    date_pattern = re.compile(r'^(\d{2}/\d{2}/\d{2})\s+')
    amount_pattern = re.compile(r'₦[\d,]+\.?\d*')
    time_pattern = re.compile(r'^\d{2}:\d{2}:\d{2}')

    with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
        all_lines = []

        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = text.split('\n')
                all_lines.extend(lines)

        current_transaction = None
        i = 0

        while i < len(all_lines):
            line = all_lines[i].strip()

            # Skip empty lines and footer/header lines
            if not line:
                i += 1
                continue

            # Skip known header/footer patterns
            lower_line = line.lower()
            if any(skip in lower_line for skip in [
                'all statements', 'kuda mf bank', 'account number', 'page ',
                'summary', 'type opening balance', 'spend account',
                'money in money out opening', 'date/time money in',
                'licensed by', 'lagos. nigeria'
            ]):
                i += 1
                continue

            # Check if this line starts a new transaction (starts with date DD/MM/YY)
            date_match = date_pattern.match(line)

            if date_match:
                # Save previous transaction
                if current_transaction:
                    transactions.append(current_transaction)

                date_str = date_match.group(1)
                rest_of_line = line[date_match.end():].strip()

                # Find all amounts in the line (₦xxx.xx format)
                amounts = amount_pattern.findall(rest_of_line)

                if len(amounts) >= 2:
                    # Last amount is always balance
                    balance_str = amounts[-1]
                    # First amount is either credit or debit
                    amount_str = amounts[0]

                    balance = clean_kuda_amount(balance_str)
                    amount = clean_kuda_amount(amount_str)

                    # Determine if inward (credit) or outward/pos (debit)
                    is_credit = 'inward' in rest_of_line.lower()
                    is_debit = 'outward' in rest_of_line.lower() or 'pos' in rest_of_line.lower()

                    # Extract description - everything between the amounts and category keywords
                    # Remove the amounts from the string for description extraction
                    desc_part = rest_of_line
                    for amt in amounts:
                        desc_part = desc_part.replace(amt, ' ')

                    # Remove category keywords
                    for kw in ['inward transfer', 'outward transfer', 'inward', 'outward', 'pos']:
                        desc_part = re.sub(rf'\b{kw}\b', ' ', desc_part, flags=re.IGNORECASE)

                    description = clean_description(desc_part)

                    current_transaction = {
                        'date': convert_kuda_date_to_standard(date_str),
                        'description': description,
                        'debit': amount if is_debit else None,
                        'credit': amount if is_credit else None,
                        'balance': balance,
                    }
                elif len(amounts) == 1:
                    # Only balance, might be a special row - skip
                    current_transaction = None

            elif current_transaction:
                # This is a continuation line
                # Skip time lines (HH:MM:SS)
                if time_pattern.match(line):
                    # Check if there's content after the time
                    content_after_time = line[8:].strip() if len(line) > 8 else ''
                    if content_after_time:
                        # Remove category keywords
                        for kw in ['transfer', 'inward', 'outward']:
                            content_after_time = re.sub(rf'\b{kw}\b', ' ', content_after_time, flags=re.IGNORECASE)
                        addition = clean_description(content_after_time)
                        if addition:
                            current_transaction['description'] += ' ' + addition
                else:
                    # Regular continuation line - add to description
                    # Skip lines that are just category keywords
                    if line.lower() not in ('transfer', 'inward', 'outward', 'pos'):
                        addition = clean_description(line)
                        if addition:
                            current_transaction['description'] += ' ' + addition

            i += 1

        # Don't forget the last transaction
        if current_transaction:
            transactions.append(current_transaction)

    return transactions


def parse_pdf_bank_statement(
    pdf_content: bytes,
    bank: SupportedBank = SupportedBank.ZENITH,
    password: str = None
) -> list[dict]:
    """Extract transactions from bank PDF statement.

    Args:
        pdf_content: PDF file content as bytes
        bank: The bank type (zenith, gtbank, or kuda)
        password: Optional password for encrypted PDFs

    Returns:
        List of transaction dictionaries
    """
    if bank == SupportedBank.GTBANK:
        return parse_gtbank_statement(pdf_content, password)
    elif bank == SupportedBank.KUDA:
        return parse_kuda_statement(pdf_content)
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
