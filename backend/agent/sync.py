"""Orchestrates a full sync: fetch emails → parse → classify → save."""

import json
from pathlib import Path
from datetime import datetime

from .email_reader import fetch_statement_emails
from .parser import parse_pdf, parse_html
from .classifier import classify_transactions, generate_monthly_insights

DATA_DIR = Path(__file__).parent.parent / "data"
TRANSACTIONS_FILE = DATA_DIR / "transactions.json"
INSIGHTS_FILE = DATA_DIR / "insights.json"


def _load_json(path: Path) -> list | dict:
    if path.exists() and path.stat().st_size > 2:
        return json.loads(path.read_text())
    return [] if "transactions" in path.name else {}


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def run_sync(statement_type: str = "all") -> dict:
    """
    Full pipeline:
      1. Fetch emails from Gmail
      2. Parse each email (PDF attachments first, HTML body fallback)
      3. Classify new transactions with Claude
      4. Merge into transactions.json (skip duplicates)
      5. Regenerate insights for affected months
      6. Return summary stats
    """
    print(f"[sync] Fetching {statement_type} statement emails…")
    emails = fetch_statement_emails(statement_type)
    print(f"[sync] Found {len(emails)} emails")

    raw_transactions = []
    for email in emails:
        # Use clean bank name ("SBI", "ICICI", "HSBC", "HDFC") as source identifier
        source = email["source_type"]

        # Try PDF attachments first
        pdf_txns = []
        for attachment in email.get("attachments", []):
            pdf_txns.extend(parse_pdf(attachment["data"], source=source))

        if pdf_txns:
            raw_transactions.extend(pdf_txns)
        elif email.get("html_body"):
            # PDF was skipped (password-protected) or empty — fall back to HTML
            print(f"[sync] Falling back to HTML for: {email['subject'][:60]}")
            html_txns = parse_html(email["html_body"], source=source)
            raw_transactions.extend(html_txns)

    print(f"[sync] Parsed {len(raw_transactions)} raw transactions")

    # Load existing data, find truly new transactions
    existing = _load_json(TRANSACTIONS_FILE)
    existing_keys = {
        (t.get("date"), t.get("description", "")[:40], t.get("amount"))
        for t in existing
    }
    new_txns = [
        t for t in raw_transactions
        if (t.get("date"), t.get("description", "")[:40], t.get("amount")) not in existing_keys
    ]

    print(f"[sync] {len(new_txns)} new transactions to classify")

    if new_txns:
        classified = classify_transactions(new_txns)
        all_transactions = existing + classified
        _save_json(TRANSACTIONS_FILE, all_transactions)

        # Rebuild insights for months that have new data
        affected_months = {t["date"][:7] for t in classified if t.get("date")}
        insights = _load_json(INSIGHTS_FILE)
        for month in affected_months:
            month_txns = [t for t in all_transactions if (t.get("date") or "").startswith(month)]
            insights[month] = generate_monthly_insights(month_txns, month)
            insights[month]["generated_at"] = datetime.now().isoformat()
        _save_json(INSIGHTS_FILE, insights)
    else:
        all_transactions = existing

    return {
        "emails_fetched": len(emails),
        "transactions_parsed": len(raw_transactions),
        "new_transactions": len(new_txns),
        "total_transactions": len(all_transactions),
    }
