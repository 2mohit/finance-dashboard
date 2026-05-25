"""FastAPI backend — serves transaction data and triggers syncs."""

import json
from pathlib import Path
from collections import defaultdict

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from agent.sync import run_sync

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


def _read_transactions() -> list[dict]:
    if TRANSACTIONS_FILE.exists():
        return json.loads(TRANSACTIONS_FILE.read_text())
    return []


def _read_insights() -> dict:
    if INSIGHTS_FILE.exists():
        return json.loads(INSIGHTS_FILE.read_text())
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


# ── health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    txns = _read_transactions()
    return {"status": "ok", "transaction_count": len(txns)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
