"""Gmail reader — fetches credit card and bank statement emails."""

import os
import base64
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", encoding="utf-8-sig", override=True)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

LOOKBACK_DAYS = int(os.getenv("EMAIL_LOOKBACK_DAYS", "145"))

# Known sender domains for Indian banks
BANK_SENDER_DOMAINS = [
    "hdfcbank.com",
    "icicibank.com",
    "sbi.co.in",
    "hsbc.co.in",
    "hsbc.com",
]


def _get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    creds_path = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
    token_path = os.getenv("GMAIL_TOKEN_PATH", "token.json")

    creds = None
    if Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# (sender_email, subject_contains, bank_name)
_STATEMENT_FILTERS = [
    ("ELITE.card@sbicard.com",                 "Your SBI Card ELITE Monthly Statement",  "SBI"),
    ("credit_cards@icici.bank.in",             "ICICI Bank Credit Card Statement",        "ICICI"),
    ("creditcardstatement@mail.hsbc.co.in",    "Your HSBC Credit Card statement",         "HSBC"),
    ("Emailstatements.cards@hdfcbank.bank.in", "Diners Black Credit Card Statement",      "HDFC"),
]


def _build_statement_query(lookback_days: int) -> str:
    """
    Precise Gmail query: exact sender + subject contains.
    Zero false positives.
    """
    since = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y/%m/%d")

    parts = " OR ".join(
        f'(from:{sender} subject:"{subject}")'
        for sender, subject, _ in _STATEMENT_FILTERS
    )
    return f"({parts}) after:{since}"


def _decode_body(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "==")


def _extract_parts(payload: dict) -> tuple[Optional[bytes], list[dict]]:
    """Return (html_body_bytes, list_of_attachments)."""
    html_body = None
    attachments = []
    mime = payload.get("mimeType", "")

    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html_body = _decode_body(data)

    elif mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            part_mime = part.get("mimeType", "")
            filename = part.get("filename", "")

            if part_mime == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    html_body = _decode_body(data)

            elif part_mime == "application/pdf" or filename.lower().endswith(".pdf"):
                attachment_id = part.get("body", {}).get("attachmentId")
                if attachment_id:
                    attachments.append({"filename": filename, "attachment_id": attachment_id})

            elif part_mime.startswith("multipart/"):
                sub_html, sub_attachments = _extract_parts(part)
                if sub_html:
                    html_body = sub_html
                attachments.extend(sub_attachments)

    return html_body, attachments


def fetch_statement_emails(
    statement_type: str = "all",
    skip_msg_ids: set = None,
) -> list[dict]:
    """
    Fetch monthly credit card statement emails from known bank senders.

    Args:
        statement_type : reserved for future filtering (e.g. "credit_card" only)
        skip_msg_ids   : set of Gmail message IDs to skip — these are already in the
                         parse cache so no need to download their attachments again.
                         Cost saving: zero Gmail attachment API calls for cached emails.

    Returns:
        List of dicts with keys: id, subject, date, source_type, html_body, attachments
        Only returns emails NOT in skip_msg_ids.
    """
    skip_msg_ids = skip_msg_ids or set()
    service = _get_gmail_service()
    results = []

    query = _build_statement_query(LOOKBACK_DAYS)
    print(f"[email] Gmail query: {query}")

    response = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
    messages = response.get("messages", [])

    cached_count = sum(1 for m in messages if m["id"] in skip_msg_ids)
    new_count = len(messages) - cached_count
    print(f"[email] {len(messages)} emails matched — {cached_count} cached (skip), {new_count} new (fetch)")

    seen_ids = set()
    for msg_ref in messages:
        msg_id = msg_ref["id"]
        if msg_id in seen_ids:
            continue
        seen_ids.add(msg_id)

        # ── skip cached emails entirely (no attachment download) ──────────────
        if msg_id in skip_msg_ids:
            continue

        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        payload = msg.get("payload", {})
        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

        subject = headers.get("Subject", "(no subject)")
        date_str = headers.get("Date", "")

        html_body, attachment_refs = _extract_parts(payload)

        # Download attachment bytes only for new emails
        attachments = []
        for ref in attachment_refs:
            att = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=msg_id, id=ref["attachment_id"])
                .execute()
            )
            pdf_bytes = _decode_body(att.get("data", ""))
            attachments.append({"filename": ref["filename"], "data": pdf_bytes})

        # Detect bank name from sender using the same filters as the Gmail query
        sender = headers.get("From", "")
        source_type = "unknown"
        for filter_sender, _, bank_name in _STATEMENT_FILTERS:
            if filter_sender.lower() in sender.lower():
                source_type = bank_name
                break

        print(f"[email] fetched  {source_type} | {subject[:60]}")

        results.append({
            "id": msg_id,
            "subject": subject,
            "date": date_str,
            "source_type": source_type,
            "html_body": html_body,
            "attachments": attachments,
        })

    return results
