"""Extract raw transactions from PDF attachments or HTML email bodies."""

import re
import io
from datetime import datetime
from typing import Optional

import os
import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect
from pdfminer.pdfparser import PDFException as PdfminerException
from bs4 import BeautifulSoup


# ── shared helpers ────────────────────────────────────────────────────────────

def _clean_amount(raw: str) -> Optional[float]:
    """Turn '₹ 1,234.56' or '-1234.56' into a float, or None if unparseable."""
    raw = re.sub(r"[^\d.\-]", "", raw.replace(",", ""))
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[str]:
    """Try common date formats; return ISO string or None."""
    formats = [
        "%d %b %Y", "%d-%b-%Y", "%d/%m/%Y", "%m/%d/%Y",
        "%d %B %Y", "%Y-%m-%d", "%d-%m-%Y", "%b %d, %Y",
        "%d %b %y",   # SBI: "06 Apr 26"
        "%d-%b-%y",   # "06-Apr-26"
        "%d/%m/%y",   # "06/04/26"
    ]
    raw = raw.strip()
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _clean_amount_with_dc(raw: str) -> tuple[Optional[float], Optional[str]]:
    """
    Handle amounts with D/C suffix (SBI style: '1,893.37 D').
    Returns (amount, 'debit'|'credit'|None).
    """
    raw = raw.strip()
    dc = None
    if raw.endswith(" D") or raw.endswith("\nD"):
        dc = "debit"
        raw = raw[:-1].strip()
    elif raw.endswith(" C") or raw.endswith("\nC"):
        dc = "credit"
        raw = raw[:-1].strip()
    return _clean_amount(raw), dc


# ── PDF parser ────────────────────────────────────────────────────────────────

_DATE_RE = re.compile(
    r"\b(\d{1,2}[\s\-/][A-Za-z]{3}[\s\-/]\d{2,4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})\b"
)
# HSBC-style: 21APR (no separator, no year)
_HSBC_DATE_RE = re.compile(r"\b(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b")
_AMOUNT_RE = re.compile(r"[₹$£€`]?\s*[\d,]+\.\d{2}")

# HDFC: description on line above, then DD/MM/YYYY| HH:MM +/- C AMOUNT
# e.g. "BPPY CC PAYMENT\n26/03/2026| 19:52 + C 4.00"
_HDFC_TXN_RE = re.compile(
    r"([A-Z][^\n]+)\n(\d{2}/\d{2}/\d{4})\|\s*\d{2}:\d{2}\s*([+\-])\s*[C`₹]\s*([\d,]+\.\d{2})",
    re.MULTILINE
)

# ICICI: DD/MM/YYYY  11-digit-serial  DESCRIPTION  reward-points  AMOUNT [CR]
_ICICI_TXN_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s+\d{11}\s+(.+?)\s+\d+\s+([\d,]+\.\d{2})\s*(CR)?(?=\s|$)",
    re.MULTILINE
)

# HSBC transaction line: DDMMM DESCRIPTION AMOUNT [CR]
_HSBC_TXN_RE = re.compile(
    r"^(\d{2}(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC))"
    r"\s+(.+?)\s+"
    r"([\d,]+\.\d{2})\s*(CR)?$",
    re.MULTILINE
)


def get_bank_passwords(bank: str) -> list[str]:
    """
    Return passwords to try for a specific bank.

    Reads  {BANK}_PDF_PASSWORD  env var first (e.g. SBI_PDF_PASSWORD).
    Falls back to the legacy PDF_PASSWORDS comma-list for any bank not
    individually configured.  The empty string is always tried first so
    un-protected PDFs open without an explicit password entry.
    """
    bank_key = bank.upper().replace(" ", "_").replace("-", "_")
    specific = os.getenv(f"{bank_key}_PDF_PASSWORD", "").strip()
    if specific:
        return ["", specific]

    # Legacy flat-list fallback
    raw = os.getenv("PDF_PASSWORDS", "")
    return [""] + [p.strip() for p in raw.split(",") if p.strip()]


def parse_pdf(pdf_bytes: bytes, source: str = "unknown") -> list[dict]:
    """
    Extract transactions from a PDF statement.
    Tries configured passwords for password-protected PDFs.
    Skips non-statement attachments (tariff docs > 5 pages with no transactions).
    Returns a list of raw transaction dicts (not yet classified).
    """
    passwords_to_try = get_bank_passwords(source)

    pdf = None
    for pwd in passwords_to_try:
        try:
            pdf = pdfplumber.open(io.BytesIO(pdf_bytes), password=pwd)
            break
        except (PDFPasswordIncorrect, PdfminerException):
            continue

    if pdf is None:
        print(f"[parser] Skipping password-protected PDF (no matching password): {source}")
        return []

    transactions = []
    with pdf:
        # Skip obvious tariff/MITC docs (> 5 pages, no transaction content on page 1)
        if len(pdf.pages) > 5:
            page1_text_lower = (pdf.pages[0].extract_text() or "").lower()
            statement_keywords = ["opening balance", "transaction", "statement date",
                                  "amount due", "payment due", "total amount"]
            if not any(kw in page1_text_lower for kw in statement_keywords):
                return []

        page1_text = pdf.pages[0].extract_text() or ""

        # Detect HDFC format: description\nDD/MM/YYYY| HH:MM +/- C AMOUNT
        if _HDFC_TXN_RE.search(page1_text):
            all_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            return filter_non_transactions(_parse_hdfc_text(all_text, source))

        # Detect ICICI format: DD/MM/YYYY + 11-digit serial + description + amount
        if _ICICI_TXN_RE.search(page1_text):
            return filter_non_transactions(_parse_icici_text(page1_text, source))

        # Detect HSBC format: DDMMM transaction lines
        if _HSBC_TXN_RE.search(page1_text):
            return filter_non_transactions(_parse_hsbc_text(page1_text, source))

        for page in pdf.pages:
            # Try table extraction first
            tables = page.extract_tables()
            for table in tables:
                transactions.extend(_rows_to_transactions(table, source))

            # Fallback: line-by-line text heuristic
            if not tables:
                text = page.extract_text() or ""
                transactions.extend(_text_to_transactions(text, source))

    return filter_non_transactions(_deduplicate(transactions))


def _split_newline_row(header: list[str], row: list, source: str) -> list[dict]:
    """
    Handle SBI-style tables where all transactions are packed into one row
    with newline-separated values per cell.
    e.g. dates cell = '06 Apr 26\n09 Apr 26\n', amounts = '23,442.96 C\n1,893.37 D'
    """
    date_col = _find_col(header, ["date", "txn date", "transaction date", "value date"])
    desc_col = _find_col(header, ["description", "particulars", "narration", "transaction details", "details", "merchant"])
    amount_col = _find_col(header, ["amount"])

    if date_col is None or desc_col is None or amount_col is None:
        return []

    def split_cell(idx):
        val = row[idx] if idx < len(row) and row[idx] else ""
        return [v.strip() for v in str(val).split("\n") if v.strip()]

    dates = split_cell(date_col)
    descs = split_cell(desc_col)
    amounts = split_cell(amount_col)

    results = []
    for i in range(min(len(dates), len(descs), len(amounts))):
        date_str = _parse_date(dates[i])
        if not date_str:
            continue
        amount, txn_type = _clean_amount_with_dc(amounts[i])
        if amount is None:
            continue
        credit = amount if txn_type == "credit" else None
        debit = amount if txn_type != "credit" else None
        results.append({
            "date": date_str,
            "description": descs[i],
            "amount": debit,
            "credit": credit,
            "source": source,
            "raw": f"{dates[i]} | {descs[i]} | {amounts[i]}",
        })
    return results


def _rows_to_transactions(table: list[list], source: str) -> list[dict]:
    """Convert a pdfplumber table (list of rows) into transaction dicts."""
    if not table or len(table) < 2:
        return []

    # Detect header row
    header = [str(c).lower().strip().replace("\n", " ") if c else "" for c in table[0]]

    # SBI packs all transactions into a single row with \n-separated values per cell
    # Detect: only 1 data row but cells contain multiple \n-separated lines
    if len(table) == 2:
        data_row = table[1]
        cells_with_newlines = sum(1 for c in data_row if c and "\n" in str(c))
        if cells_with_newlines >= 2:
            return _split_newline_row(header, data_row, source)


    date_col = _find_col(header, ["date", "txn date", "transaction date", "value date", "tran date"])
    desc_col = _find_col(header, ["description", "particulars", "narration", "details", "merchant", "transaction details", "tran particulars"])
    debit_col = _find_col(header, ["debit", "withdrawal", "dr"])
    credit_col = _find_col(header, ["credit", "deposit", "cr"])
    amount_col = _find_col(header, ["amount"])

    results = []
    for row in table[1:]:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue

        def cell(idx):
            if idx is None or idx >= len(row):
                return ""
            return str(row[idx]).strip() if row[idx] else ""

        date_str = _parse_date(cell(date_col)) if date_col is not None else None
        description = cell(desc_col) if desc_col is not None else ""

        amount = None
        credit = None
        txn_type = None  # "debit" or "credit"

        if debit_col is not None and cell(debit_col):
            amount = _clean_amount(cell(debit_col))
        elif amount_col is not None and cell(amount_col):
            # SBI style: amount + D/C in same cell
            amount, txn_type = _clean_amount_with_dc(cell(amount_col))
            if txn_type == "credit":
                credit = amount
                amount = None

        if credit_col is not None and cell(credit_col):
            credit = _clean_amount(cell(credit_col))

        if not date_str or not description or (amount is None and credit is None):
            continue

        results.append({
            "date": date_str,
            "description": description,
            "amount": amount,
            "credit": credit,
            "source": source,
            "raw": " | ".join(str(c) for c in row if c),
        })

    return results


def _parse_hdfc_text(text: str, source: str) -> list[dict]:
    """
    Parse HDFC statement text.
    Format: DESCRIPTION on line above, then DD/MM/YYYY| HH:MM +/- C AMOUNT
    Example:
        BPPY CC PAYMENT BD016085...
        26/03/2026| 19:52 + C 4.00
    """
    results = []
    for m in _HDFC_TXN_RE.finditer(text):
        description, date_raw, sign, amount_raw = m.groups()
        try:
            date_str = datetime.strptime(date_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        amount = _clean_amount(amount_raw)
        if amount is None:
            continue
        is_credit = sign == "+"
        # Skip very small round-number payments (reward adjustments < 10)
        results.append({
            "date": date_str,
            "description": description.strip(),
            "amount": None if is_credit else amount,
            "credit": amount if is_credit else None,
            "source": source,
            "raw": m.group(0),
        })
    return results


def _parse_icici_text(text: str, source: str) -> list[dict]:
    """
    Parse ICICI statement text.
    Format: DD/MM/YYYY  13-digit-serial  DESCRIPTION  reward-points  AMOUNT [CR]
    Example: 29/03/2026 13142187906 HALDIRAM MARKETING PV GURGAON IN 18 783.64
    """
    results = []
    for m in _ICICI_TXN_RE.finditer(text):
        date_raw, description, amount_raw, cr_flag = m.groups()
        try:
            date_str = datetime.strptime(date_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        amount = _clean_amount(amount_raw)
        if amount is None:
            continue
        is_credit = cr_flag is not None
        results.append({
            "date": date_str,
            "description": description.strip(),
            "amount": None if is_credit else amount,
            "credit": amount if is_credit else None,
            "source": source,
            "raw": m.group(0),
        })
    return results


def _parse_hsbc_text(text: str, source: str) -> list[dict]:
    """
    Parse HSBC statement plain text.
    Transaction format: 21APR RSP*DISTRICT MOVIE TI GURUGRAM HAR 2,092.50 [CR]
    Year is derived from the statement period line.
    """
    # Extract year from statement period e.g. "03 APR 2026 To 02 MAY 2026"
    year_match = re.search(r"\d{2} [A-Z]{3} (\d{4}) To", text)
    year = int(year_match.group(1)) if year_match else datetime.now().year

    results = []
    for m in _HSBC_TXN_RE.finditer(text):
        date_raw, description, amount_raw, cr_flag = m.groups()
        # Parse DDMMM + year
        try:
            date_str = datetime.strptime(f"{date_raw}{year}", "%d%b%Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        amount = _clean_amount(amount_raw)
        if amount is None:
            continue
        is_credit = cr_flag is not None
        results.append({
            "date": date_str,
            "description": description.strip(),
            "amount": None if is_credit else amount,
            "credit": amount if is_credit else None,
            "source": source,
            "raw": m.group(0),
        })
    return results


def _text_to_transactions(text: str, source: str) -> list[dict]:
    """Heuristic line scanner for unstructured PDF text."""
    results = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 10:
            continue
        date_match = _DATE_RE.search(line)
        amount_matches = _AMOUNT_RE.findall(line)
        if date_match and amount_matches:
            date_str = _parse_date(date_match.group())
            amount = _clean_amount(amount_matches[-1])
            description = line[: date_match.start()].strip() or line[date_match.end():].strip()
            if date_str and amount is not None:
                results.append({
                    "date": date_str,
                    "description": description,
                    "amount": abs(amount),
                    "credit": None,
                    "source": source,
                    "raw": line,
                })
    return results


def _find_col(header: list[str], candidates: list[str]) -> Optional[int]:
    for i, h in enumerate(header):
        for c in candidates:
            if c in h:
                return i
    return None


# ── HTML parser ───────────────────────────────────────────────────────────────

def parse_html(html_bytes: bytes, source: str = "unknown") -> list[dict]:
    """
    Extract transactions from an HTML email body.
    Looks for <table> elements that look like transaction tables.
    """
    soup = BeautifulSoup(html_bytes, "lxml")
    transactions = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        raw_table = []
        for row in rows:
            cells = [td.get_text(separator=" ", strip=True) for td in row.find_all(["td", "th"])]
            raw_table.append(cells)

        txns = _rows_to_transactions(raw_table, source)
        transactions.extend(txns)

    return filter_non_transactions(_deduplicate(transactions))


# ── deduplication ─────────────────────────────────────────────────────────────

def _deduplicate(transactions: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for t in transactions:
        # Use raw amount + credit fields for dedup key (before normalisation)
        raw_amt = t.get("amount") or t.get("credit")
        key = (t.get("date"), t.get("description", "")[:40], raw_amt)
        if key not in seen:
            seen.add(key)
            result.append(t)
    return result


# ── non-transaction filter ────────────────────────────────────────────────────

# Patterns that match PDF summary/header rows (not real transactions)
_JUNK_DESC_RE = re.compile(
    r"net outstanding balance|transactions for [a-z]|total amount due|"
    r"opening balance|closing balance|minimum amount due|credit limit|"
    r"available credit|reward points",
    re.IGNORECASE,
)

# Patterns for credit card bill payments and BBPS payments (user chose to exclude)
_PAYMENT_DESC_RE = re.compile(
    r"bbps pay|bbps pmt|payment received|cc payment|credit card payment|"
    r"bppy cc|auto debit payment|neft payment|imps payment received",
    re.IGNORECASE,
)


def filter_non_transactions(transactions: list[dict]) -> list[dict]:
    """
    Remove junk rows (PDF headers/summaries) and credit card bill payments.
    Normalises each surviving transaction to a single signed `amount`:
      - Debit (spending)  → negative  e.g. -3250.72
      - Credit (refund)   → positive  e.g.  +650.45
    Called after parsing, before classification.
    """
    result = []
    for t in transactions:
        desc = t.get("description", "")
        if _JUNK_DESC_RE.search(desc):
            continue
        # Exclude credit-card bill payments (they are credits, not real spend)
        if _PAYMENT_DESC_RE.search(desc) and t.get("credit") is not None:
            continue

        enriched = dict(t)
        debit = t.get("amount")   # positive float for a purchase
        credit = t.get("credit")  # positive float for a refund/income

        if credit is not None:
            enriched["amount"] = -abs(credit)    # refund → negative (reduces spend)
            enriched["is_credit"] = True
        elif debit is not None:
            enriched["amount"] = abs(debit)      # spending → positive
            enriched["is_credit"] = False
        else:
            enriched["amount"] = None
            enriched["is_credit"] = False

        # Keep raw credit field for backward compat but normalised amount is canonical
        result.append(enriched)
    return result
