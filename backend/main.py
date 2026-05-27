"""FastAPI backend — serves transaction data and triggers syncs."""

import json
from pathlib import Path
from collections import defaultdict

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", encoding="utf-8-sig", override=True)

from agent.sync import run_sync, _unlock_pdf
from agent.cache import SyncCache, get_usage_stats

app = FastAPI(title="Finance Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"
TRANSACTIONS_FILE = DATA_DIR / "transactions.json"
INSIGHTS_FILE = DATA_DIR / "insights.json"
PDF_DIR = DATA_DIR / "pdfs"


def _read_transactions() -> list[dict]:
    if TRANSACTIONS_FILE.exists():
        return json.loads(TRANSACTIONS_FILE.read_text(encoding="utf-8"))
    return []


def _read_insights() -> dict:
    if INSIGHTS_FILE.exists():
        return json.loads(INSIGHTS_FILE.read_text(encoding="utf-8"))
    return {}


# ── sync endpoints ─────────────────────────────────────────────────────────────

_sync_status = {"running": False, "last_result": None}


@app.post("/api/sync")
async def trigger_sync(background_tasks: BackgroundTasks, type: str = "all"):
    if _sync_status["running"]:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    def _run():
        _sync_status["running"] = True
        try:
            _sync_status["last_result"] = run_sync(type)
        finally:
            _sync_status["running"] = False

    background_tasks.add_task(_run)
    return {"status": "started", "type": type}


@app.get("/api/sync/status")
def sync_status():
    return _sync_status


# ── transaction endpoints ──────────────────────────────────────────────────────

@app.get("/api/transactions")
def get_transactions(month: str | None = None, category: str | None = None):
    txns = _read_transactions()
    if month:
        txns = [t for t in txns if (t.get("date") or "").startswith(month)]
    if category:
        txns = [t for t in txns if t.get("category") == category]
    return txns


@app.get("/api/transactions/summary")
def get_summary():
    """Monthly spend totals per category — used for charts."""
    txns = _read_transactions()
    summary = defaultdict(lambda: defaultdict(float))

    for t in txns:
        month = (t.get("date") or "")[:7]
        if not month:
            continue
        cat = t.get("category", "Other")
        amount = t.get("amount") or 0
        summary[month][cat] += amount

    return {
        month: dict(cats)
        for month, cats in sorted(summary.items())
    }


@app.get("/api/transactions/categories")
def get_categories():
    """Total spend per category across all time."""
    txns = _read_transactions()
    totals = defaultdict(float)
    for t in txns:
        cat = t.get("category", "Other")
        totals[cat] += t.get("amount") or 0
    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))


# ── insights endpoint ──────────────────────────────────────────────────────────

@app.get("/api/insights")
def get_insights(month: str | None = None):
    insights = _read_insights()
    if month:
        return insights.get(month, {})
    return insights


@app.get("/api/insights/latest")
def get_latest_insight():
    insights = _read_insights()
    if not insights:
        return {}
    latest_month = sorted(insights.keys())[-1]
    return {"month": latest_month, **insights[latest_month]}


# ── cache / cost stats ────────────────────────────────────────────────────────

@app.get("/api/cache/stats")
def cache_stats():
    """Return sync cache state — useful for monitoring API cost savings."""
    cache = SyncCache()
    return cache.summary()


@app.post("/api/cache/reset")
def reset_cache():
    """
    Clear the email parse cache so the next sync re-downloads all PDFs.

    Safe: transactions.json is NOT touched — re-parsed transactions are
    diffed against existing ones, so no duplicates and no Claude calls.
    Use this once to backfill pdf_file on transactions synced before
    PDF saving was introduced.
    """
    state_file = DATA_DIR / "sync_state.json"
    parse_file = DATA_DIR / "parse_cache.json"

    if state_file.exists():
        import json as _json
        state = _json.loads(state_file.read_text(encoding="utf-8"))
        state["processed_email_ids"] = []
        state_file.write_text(_json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    if parse_file.exists():
        parse_file.write_text("{}", encoding="utf-8")

    return {
        "status": "cache_reset",
        "message": "Parse cache cleared. Trigger a sync to re-download PDFs and backfill pdf_file.",
    }


# ── PDF endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/pdfs")
def list_pdfs():
    """List all saved statement PDFs with bank, month, transaction count, and unlock status."""
    if not PDF_DIR.exists():
        return []
    txns = _read_transactions()
    unlocked_dir = PDF_DIR / "unlocked"
    result = []
    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        fname = pdf_path.name
        count = sum(1 for t in txns if t.get("pdf_file") == fname)
        result.append({
            "filename": fname,
            "size_kb": round(pdf_path.stat().st_size / 1024, 1),
            "transaction_count": count,
            "unlocked": (unlocked_dir / fname).exists(),
        })
    return result


@app.get("/api/pdfs/{filename}")
def get_pdf(filename: str):
    """
    Serve a single PDF statement.
    Prefers the unlocked (no-password) copy so browsers can render it inline.
    Falls back to the original if no unlocked copy exists.
    Protected against path traversal.
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    # Prefer unlocked version — renders in browser without password prompt
    unlocked_path = PDF_DIR / "unlocked" / filename
    if unlocked_path.exists():
        return FileResponse(str(unlocked_path), media_type="application/pdf")
    pdf_path = PDF_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(str(pdf_path), media_type="application/pdf")


# ── PDF unlock endpoint ───────────────────────────────────────────────────────

@app.post("/api/pdfs/unlock")
def unlock_pdfs():
    """
    Unlock all saved PDFs that don't have an unlocked copy yet.
    Useful to run once after a sync to make PDFs renderable in-browser.
    """
    if not PDF_DIR.exists():
        return {"unlocked": 0, "failed": 0, "already_done": 0}

    unlocked_dir = PDF_DIR / "unlocked"
    unlocked_count = 0
    failed_count = 0
    already_done = 0

    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        dest = unlocked_dir / pdf_path.name
        if dest.exists():
            already_done += 1
            continue
        # Derive bank from filename: "SBI_2026-04_abc.pdf" → "SBI"
        bank = pdf_path.name.split("_")[0]
        pdf_bytes = pdf_path.read_bytes()
        ok = _unlock_pdf(pdf_bytes, dest, bank=bank)
        if ok:
            unlocked_count += 1
        else:
            failed_count += 1

    return {"unlocked": unlocked_count, "failed": failed_count, "already_done": already_done}


# ── PDF audit & repair endpoints ─────────────────────────────────────────────

def _gmail_audit() -> dict:
    """
    Core audit logic — compare what Gmail has against our local state.
    Returns a structured diff used by both GET /api/pdfs/audit and POST /api/pdfs/repair.
    """
    from agent.email_reader import (
        _get_gmail_service, _build_statement_query,
        LOOKBACK_DAYS, _STATEMENT_FILTERS,
    )

    service = _get_gmail_service()
    query = _build_statement_query(LOOKBACK_DAYS)
    response = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
    gmail_messages = response.get("messages", [])

    cache = SyncCache()
    unlocked_dir = PDF_DIR / "unlocked"

    emails = []
    for msg_ref in gmail_messages:
        msg_id = msg_ref["id"]
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="metadata",
            metadataHeaders=["Subject", "Date", "From"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}

        # Detect bank from sender
        sender = headers.get("From", "")
        bank = "unknown"
        for filter_sender, _, bank_name in _STATEMENT_FILTERS:
            if filter_sender.lower() in sender.lower():
                bank = bank_name
                break

        # Check local state
        in_cache = msg_id in cache.processed_ids
        pdf_files = list(PDF_DIR.glob(f"{bank}_*_{msg_id[:8]}.pdf"))
        pdf_saved = len(pdf_files) > 0
        pdf_unlocked = pdf_saved and all((unlocked_dir / p.name).exists() for p in pdf_files)

        # Determine required action
        if not in_cache:
            action = "download"           # never fetched — need full download + parse
        elif not pdf_saved:
            action = "redownload_pdf"     # cached (transactions exist) but PDF file missing
        elif not pdf_unlocked:
            action = "unlock"             # PDF exists but no browser-renderable copy
        else:
            action = "none"

        emails.append({
            "id": msg_id,
            "bank": bank,
            "subject": headers.get("Subject", "")[:80],
            "date": headers.get("Date", ""),
            "in_cache": in_cache,
            "pdf_saved": pdf_saved,
            "pdf_unlocked": pdf_unlocked,
            "pdf_files": [p.name for p in pdf_files],
            "action": action,
        })

    summary = {
        "gmail_total": len(gmail_messages),
        "cached": sum(1 for e in emails if e["in_cache"]),
        "pdf_saved": sum(1 for e in emails if e["pdf_saved"]),
        "pdf_unlocked": sum(1 for e in emails if e["pdf_unlocked"]),
        "needs_download": sum(1 for e in emails if e["action"] == "download"),
        "needs_redownload_pdf": sum(1 for e in emails if e["action"] == "redownload_pdf"),
        "needs_unlock": sum(1 for e in emails if e["action"] == "unlock"),
        "all_good": all(e["action"] == "none" for e in emails),
    }

    return {"emails": emails, "summary": summary}


@app.get("/api/pdfs/audit")
def audit_pdfs():
    """
    Compare Gmail statement emails against local cache + PDF state.
    Returns per-email status and a summary of what actions are needed.
    Fast — uses metadata-only Gmail calls (no attachment downloads).
    """
    return _gmail_audit()


@app.post("/api/pdfs/repair")
async def repair_pdfs(background_tasks: BackgroundTasks):
    """
    Targeted repair based on Gmail audit — only processes what's actually missing:
      - download: email not in cache at all → sync will fetch + parse + save PDF
      - redownload_pdf: email cached but PDF missing → temporarily un-cache so sync re-downloads
      - unlock: PDF exists but no unlocked copy → run unlock only (no Gmail call)
    Never blindly resets the full cache. No unnecessary Claude API calls.
    """
    if _sync_status["running"]:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    def _run():
        _sync_status["running"] = True
        _sync_status["last_result"] = None
        try:
            audit = _gmail_audit()
            emails = audit["emails"]
            summary = audit["summary"]
            print(f"[repair] Audit: {summary}")

            needs_sync = False

            # Case 1: emails not in cache at all → normal sync will handle
            if summary["needs_download"] > 0:
                print(f"[repair] {summary['needs_download']} email(s) not in cache -- will download")
                needs_sync = True

            # Case 2: email in cache but PDF missing → temporarily un-cache so sync re-fetches
            if summary["needs_redownload_pdf"] > 0:
                print(f"[repair] {summary['needs_redownload_pdf']} email(s) missing PDF -- removing from cache to trigger re-download")
                import json as _json
                state_path = DATA_DIR / "sync_state.json"
                parse_path = DATA_DIR / "parse_cache.json"
                redownload_ids = {e["id"] for e in emails if e["action"] == "redownload_pdf"}
                if state_path.exists():
                    state = _json.loads(state_path.read_text(encoding="utf-8"))
                    state["processed_email_ids"] = [
                        mid for mid in state.get("processed_email_ids", [])
                        if mid not in redownload_ids
                    ]
                    state_path.write_text(_json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
                if parse_path.exists():
                    cache_data = _json.loads(parse_path.read_text(encoding="utf-8"))
                    for mid in redownload_ids:
                        cache_data.pop(mid, None)
                    parse_path.write_text(_json.dumps(cache_data, indent=2, ensure_ascii=False), encoding="utf-8")
                needs_sync = True

            # Run sync if anything requires it
            if needs_sync:
                from agent.sync import run_sync
                result = run_sync("all")
                _sync_status["last_result"] = result
            else:
                print("[repair] No sync needed")

            # Case 3: PDFs exist but missing unlocked copy → just unlock
            unlocked_dir = PDF_DIR / "unlocked"
            newly_unlocked = 0
            for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
                dest = unlocked_dir / pdf_path.name
                if not dest.exists():
                    bank = pdf_path.name.split("_")[0]
                    ok = _unlock_pdf(pdf_path.read_bytes(), dest, bank=bank)
                    if ok:
                        newly_unlocked += 1
            if newly_unlocked:
                print(f"[repair] Unlocked {newly_unlocked} PDF(s)")

        finally:
            _sync_status["running"] = False

    background_tasks.add_task(_run)
    return {"status": "started"}


# ── monitor endpoint ──────────────────────────────────────────────────────────

@app.get("/api/monitor")
def monitor():
    """Return cache stats + full API usage log for the Monitor tab."""
    cache = SyncCache()
    return {
        "cache": cache.summary(),
        "api_usage": get_usage_stats(),
    }


# ── health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    txns = _read_transactions()
    cache = SyncCache()
    return {
        "status": "ok",
        "transaction_count": len(txns),
        "cache": cache.summary(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
