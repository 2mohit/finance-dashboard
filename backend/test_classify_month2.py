"""Classify transactions from SECOND-most-recent statement per bank (Month 2 validation)."""
import os, io
os.environ["PYTHONIOENCODING"] = "utf-8"
import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException
from pdfminer.pdfdocument import PDFPasswordIncorrect
from agent.email_reader import _get_gmail_service, _build_statement_query, _extract_parts, _decode_body
from agent.parser import parse_pdf
from agent.classifier import classify_transactions
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv('.env', encoding='utf-8-sig', override=True)

service = _get_gmail_service()
# Look back 145 days to cover ~5 months of statements
query = _build_statement_query(145)
response = service.users().messages().list(userId="me", q=query, maxResults=30).execute()

bank_map = {
    "sbicard.com": "SBI",
    "icici.bank.in": "ICICI",
    "hsbc.co.in": "HSBC",
    "hdfcbank.bank.in": "HDFC",
}
raw_passwords = os.getenv("PDF_PASSWORDS", "")
passwords = [""] + [p.strip() for p in raw_passwords.split(",") if p.strip()]

# Collect ALL statement emails per bank, skip the first (most recent) → take the second
bank_emails = defaultdict(list)
for msg_ref in response.get("messages", []):
    msg = service.users().messages().get(userId="me", id=msg_ref["id"], format="full").execute()
    payload = msg.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    sender = headers.get("From", "")
    bank = next((v for k, v in bank_map.items() if k in sender), None)
    if bank:
        bank_emails[bank].append((msg_ref["id"], payload))

print("Statement emails found per bank:")
for b, msgs in bank_emails.items():
    print(f"  {b}: {len(msgs)} emails")

bank_txns = defaultdict(list)
for bank, email_list in bank_emails.items():
    # Skip index 0 (most recent) → use index 1 (second most recent = Month 2)
    if len(email_list) < 2:
        print(f"  [{bank}] Only 1 statement found, skipping Month 2")
        continue
    msg_id, payload = email_list[1]
    _, attachments = _extract_parts(payload)
    for ref in attachments:
        att = service.users().messages().attachments().get(
            userId="me", messageId=msg_id, id=ref["attachment_id"]
        ).execute()
        pdf_bytes = _decode_body(att.get("data", ""))
        txns = parse_pdf(pdf_bytes, source=bank)
        bank_txns[bank].extend(txns)
        print(f"  [{bank}] parsed {len(txns)} transactions from second statement")

all_txns = []
for bank, txns in bank_txns.items():
    for t in txns:
        all_txns.append({**t, "bank": bank})

if not all_txns:
    print("\nNo transactions found for Month 2. Check if enough statements exist.")
    exit()

print(f"\nClassifying {len(all_txns)} transactions with Claude Haiku...\n")
classified = classify_transactions(all_txns)

by_bank = defaultdict(list)
for t in classified:
    by_bank[t.get("bank", "?")].append(t)

for bank in sorted(by_bank.keys()):
    txns = by_bank[bank]
    total = sum(t.get("amount") or 0 for t in txns)
    print(f"\n{'='*60}")
    print(f"  {bank} ({len(txns)} transactions)  |  Net spend: {total:+,.2f}")
    print(f"{'='*60}")
    print(f"  {'Date':<12} {'Category':<22} {'Amount':>11}  Description")
    print(f"  {'-'*82}")
    for t in sorted(txns, key=lambda x: x.get("date", "")):
        amt = t.get("amount") or 0
        print(f"  {t.get('date',''):<12} {t.get('category',''):<22} {amt:>+11,.2f}  {str(t.get('description',''))[:45]}")

print(f"\n\nTotal: {len(classified)} transactions classified")
