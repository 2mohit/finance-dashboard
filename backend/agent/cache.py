"""
Persistent two-level cache — eliminates redundant Gmail API calls and Claude API calls.

Level 1 — email parse cache  (data/parse_cache.json)
  key  : Gmail message ID
  value: list of parsed + filtered transaction dicts (signed amounts, no raw bytes)
  saves: Gmail attachment download + pdfplumber work on every re-sync

Level 2 — sync state          (data/sync_state.json)
  tracks processed email IDs, last sync timestamp, cumulative stats

Lifecycle
  First sync  → fetch all emails → parse PDFs → save to parse_cache → classify new → save to transactions.json
  Next sync   → new emails only fetched (skip_msg_ids passed to email_reader)
               → if a mid-sync crash left some emails in parse_cache but not classified,
                 those are recovered without re-downloading
"""

import json
from pathlib import Path
from datetime import datetime

_DATA_DIR = Path(__file__).parent.parent / "data"
_STATE_FILE = _DATA_DIR / "sync_state.json"
_PARSE_FILE = _DATA_DIR / "parse_cache.json"


# ── helpers ───────────────────────────────────────────────────────────────────

def _load(path: Path, default):
    if path.exists() and path.stat().st_size > 2:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return default


def _save(path: Path, data):
    _DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── main class ────────────────────────────────────────────────────────────────

class SyncCache:
    """
    Usage in sync.py:

        cache = SyncCache()

        # Skip emails we already parsed
        emails = fetch_statement_emails(skip_msg_ids=cache.processed_ids)

        for email in emails:
            txns = cache.get_parsed(email["id"])   # None if not yet cached
            if txns is None:
                txns = parse_pdf(...)
                cache.save_parsed(email["id"], txns)

        # Only classify transactions not already in transactions.json
        new_txns = [t for t in all_parsed if t not in existing]
        classified = classify_transactions(new_txns)   # Claude only called for new ones
        cache.finish_sync(...)
    """

    def __init__(self):
        _DATA_DIR.mkdir(exist_ok=True)
        self._state = _load(_STATE_FILE, {
            "processed_email_ids": [],
            "last_sync": None,
            "stats": {},
        })
        self._parse = _load(_PARSE_FILE, {})
        # set for O(1) lookup
        self.processed_ids: set[str] = set(self._state["processed_email_ids"])

    # ── email-level cache ─────────────────────────────────────────────────────

    def get_parsed(self, msg_id: str) -> list | None:
        """Return cached parsed transactions for this email, or None if not yet parsed."""
        return self._parse.get(msg_id)  # None means: go parse it

    def save_parsed(self, msg_id: str, transactions: list):
        """
        Persist parsed transactions for this email.
        Called immediately after parsing, before classification.
        Even an empty list is saved — marks the email as processed.
        """
        self._parse[msg_id] = transactions
        _save(_PARSE_FILE, self._parse)

        self.processed_ids.add(msg_id)
        if msg_id not in self._state["processed_email_ids"]:
            self._state["processed_email_ids"].append(msg_id)
            _save(_STATE_FILE, self._state)

    # ── sync stats ────────────────────────────────────────────────────────────

    def finish_sync(
        self,
        emails_fetched: int,
        emails_skipped: int,
        new_classified: int,
        total_transactions: int,
    ):
        self._state["last_sync"] = datetime.now().isoformat()
        self._state["stats"] = {
            "last_emails_fetched": emails_fetched,
            "last_emails_skipped_from_cache": emails_skipped,
            "last_new_classified": new_classified,
            "total_emails_ever_processed": len(self.processed_ids),
            "total_transactions": total_transactions,
        }
        _save(_STATE_FILE, self._state)

    def summary(self) -> dict:
        """Human-readable summary of cache state."""
        s = self._state.get("stats", {})
        return {
            "last_sync": self._state.get("last_sync"),
            "total_emails_processed": len(self.processed_ids),
            "parse_cache_entries": len(self._parse),
            **s,
        }
