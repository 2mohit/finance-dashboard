"""
Orchestrates a full sync: fetch emails → parse → classify → save.

Cost-optimisation framework:
  - Level 1  parse_cache.json  — skip Gmail attachment download + PDF parse for known emails
  - Level 2  transactions.json — skip Claude classification for already-classified transactions

A cold run (empty cache) processes everything.
Subsequent runs only touch genuinely new statement emails.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", encoding="utf-8-sig", override=True)

from .email_reader import fetch_statement_emails
from .parser import parse_pdf, parse_html
from .classifier import classify_transactions, generate_monthly_insights
from .cache import SyncCache

DATA_DIR = Path(__file__).parent.parent / "data"
TRANSACTIONS_FILE = DATA_DIR / "transactions.json"
INSIGHTS_FILE = DATA_DIR / "insights.json"
PDF_DIR = DATA_DIR / "pdfs"


def _load_json(path: Path) -> list | dict:
    if path.exists() and path.stat().st_size > 2:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return [] if "transactions" in path.name else {}


def _save_json(path: Path, data):
    DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run_sync(statement_type: str = "all") -> dict:
    """
    Full pipeline with two-level caching:

      1. Load cache state — know which emails are already parsed
      2. Fetch only NEW emails from Gmail (skip_msg_ids avoids attachment downloads)
      3. For each new email: parse PDF → save to parse_cache immediately
         (so a mid-run crash doesn't waste the download on next run)
      4. Merge all parsed transactions (new + from cache for recovery)
      5. Diff against transactions.json — find truly new, unclassified transactions
      6. Classify ONLY those with Claude (Haiku)
      7. Regenerate insights only for affected months
      8. Persist everything + update cache stats
    """
    cache = SyncCache()

    # ── Step 1: fetch only emails not in parse cache ──────────────────────────
    print(f"[sync] Starting sync (cache has {len(cache.processed_ids)} processed emails)")
    emails = fetch_statement_emails(statement_type, skip_msg_ids=cache.processed_ids)
    emails_fetched = len(emails)
    emails_skipped = len(cache.processed_ids)   # already-cached count

    # ── Step 2: parse new emails + write to parse cache immediately ───────────
    raw_transactions: list[dict] = []

    for email in emails:
        msg_id = email["id"]
        source = email["source_type"]   # clean bank name: "SBI" / "ICICI" / "HSBC" / "HDFC"

        # Try PDF attachments first — save each PDF to disk and tag transactions
        pdf_txns: list[dict] = []
        for attachment in email.get("attachments", []):
            att_txns = parse_pdf(attachment["data"], source=source)
            if att_txns:
                # Derive statement month from first transaction date
                first_date = (att_txns[0].get("date") or "")[:7] or "unknown"
                pdf_filename = f"{source}_{first_date}_{msg_id[:8]}.pdf"
                pdf_path = PDF_DIR / pdf_filename
                if not pdf_path.exists():
                    PDF_DIR.mkdir(parents=True, exist_ok=True)
                    pdf_path.write_bytes(attachment["data"])
                    print(f"[sync] Saved PDF → {pdf_filename}")
                for t in att_txns:
                    t["pdf_file"] = pdf_filename
            pdf_txns.extend(att_txns)

        if pdf_txns:
            txns = pdf_txns
        elif email.get("html_body"):
            print(f"[sync] Falling back to HTML for: {email['subject'][:60]}")
            txns = parse_html(email["html_body"], source=source)
        else:
            txns = []

        # ── Save to parse cache immediately — even if empty ───────────────────
        # This means a second run won't re-download this email, regardless of
        # whether parsing found transactions.
        cache.save_parsed(msg_id, txns)
        raw_transactions.extend(txns)

    # ── Step 3: load existing classified transactions ─────────────────────────
    existing: list[dict] = _load_json(TRANSACTIONS_FILE)

    # ── Recovery path ─────────────────────────────────────────────────────────
    # If transactions.json is empty but parse_cache has data (e.g. previous run
    # crashed during classification), reload all cached parsed transactions so
    # they get classified now without re-downloading anything.
    if not existing and not raw_transactions and cache.processed_ids:
        print("[sync] transactions.json empty but parse cache has data — recovering…")
        for msg_id in cache.processed_ids:
            cached = cache.get_parsed(msg_id)
            if cached:
                raw_transactions.extend(cached)
        print(f"[sync] Recovered {len(raw_transactions)} transactions from parse cache")
    existing_keys = {
        (t.get("date"), (t.get("description") or "")[:40], t.get("amount"))
        for t in existing
    }

    # ── Step 4: find genuinely new transactions ───────────────────────────────
    new_txns = [
        t for t in raw_transactions
        if (t.get("date"), (t.get("description") or "")[:40], t.get("amount"))
        not in existing_keys
    ]
    print(f"[sync] {len(raw_transactions)} parsed  |  {len(new_txns)} new (unclassified)")

    # ── Backfill pdf_file on existing transactions that are missing it ────────
    # Runs automatically when a cache-reset re-fetches PDFs that were saved
    # before the pdf_file tagging was introduced.
    if raw_transactions:
        pdf_lookup = {
            (t.get("date"), (t.get("description") or "")[:40], t.get("amount")): t.get("pdf_file")
            for t in raw_transactions
            if t.get("pdf_file")
        }
        backfilled = sum(
            1 for t in existing
            if not t.get("pdf_file")
            and (t.get("date"), (t.get("description") or "")[:40], t.get("amount")) in pdf_lookup
        )
        if backfilled:
            for t in existing:
                if not t.get("pdf_file"):
                    key = (t.get("date"), (t.get("description") or "")[:40], t.get("amount"))
                    if key in pdf_lookup:
                        t["pdf_file"] = pdf_lookup[key]
            _save_json(TRANSACTIONS_FILE, existing)
            print(f"[sync] Backfilled pdf_file for {backfilled} existing transactions")

    # ── Step 5: classify ONLY new transactions (Claude cost) ─────────────────
    if new_txns:
        classified = classify_transactions(new_txns)
        all_transactions = existing + classified
        _save_json(TRANSACTIONS_FILE, all_transactions)
    else:
        all_transactions = existing
        classified = []
        print("[sync] No new transactions — skipping Claude classification")

    # ── Step 6: generate insights for months that need them ───────────────────
    # Covers: (a) months with new transactions, (b) months missing from insights.json
    insights = _load_json(INSIGHTS_FILE)
    all_months = {(t.get("date") or "")[:7] for t in all_transactions if (t.get("date") or "")[:7]}
    new_months = {(t.get("date") or "")[:7] for t in classified if t.get("date")}
    missing_months = all_months - set(insights.keys())
    needs_insights = sorted(new_months | missing_months)

    if needs_insights:
        for month in needs_insights:
            month_txns = [
                t for t in all_transactions
                if (t.get("date") or "").startswith(month)
            ]
            print(f"[sync] Generating insights for {month} ({len(month_txns)} transactions)…")
            insights[month] = generate_monthly_insights(month_txns, month)
            insights[month]["generated_at"] = datetime.now().isoformat()
        _save_json(INSIGHTS_FILE, insights)
    else:
        print("[sync] All month insights up to date — skipping Sonnet call")

    # ── Step 6: persist cache stats ───────────────────────────────────────────
    cache.finish_sync(
        emails_fetched=emails_fetched,
        emails_skipped=emails_skipped,
        new_classified=len(new_txns),
        total_transactions=len(all_transactions),
    )

    result = {
        "emails_fetched": emails_fetched,
        "emails_skipped_from_cache": emails_skipped,
        "transactions_parsed": len(raw_transactions),
        "new_transactions": len(new_txns),
        "total_transactions": len(all_transactions),
        "cache": cache.summary(),
    }
    print(f"[sync] Done: {result}")
    return result
