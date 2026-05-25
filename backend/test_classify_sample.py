import os, io, json
os.environ["PYTHONIOENCODING"] = "utf-8"
import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect
from agent.email_reader import _get_gmail_service, _build_statement_query, _extract_parts, _decode_body
from agent.parser import parse_pdf
from agent.classifier import classify_transactions
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()

service = _get_gmail_service()
# 1 statement per bank = last 45 days
query = _build_statement_query(45)
response = service.users().messages().list(userId="me", q=query, maxResults=10).execute()

bank_map = {"sbicard.com":"SBI","icici.bank.in":"ICICI","hsbc.co.in":"HSBC","hdfcbank.bank.in":"HDFC"}
bank_txns = defaultdict(list)

# Parse 1 statement per bank
seen_banks = set()
for msg_ref in response.get("messages", []):
    msg = service.users().messages().get(userId="me", id=msg_ref["id"], format="full").execute()
    payload = msg.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    sender = headers.get("From", "")
    bank = next((v for k,v in bank_map.items() if k in sender), None)
    if not bank or bank in seen_banks:
        continue
    seen_banks.add(bank)

    _, attachments = _extract_parts(payload)
    raw_passwords = os.getenv("PDF_PASSWORDS", "")
    passwords = [""] + [p.strip() for p in raw_passwords.split(",") if p.strip()]

    for ref in attachments:
        att = service.users().messages().attachments().get(
            userId="me", messageId=msg_ref["id"], id=ref["attachment_id"]
        ).execute()
        pdf_bytes = _decode_body(att.get("data", ""))
        txns = parse_pdf(pdf_bytes, source=bank)
        bank_txns[bank].extend(txns)

# Classify all at once
all_txns = []
for bank, txns in bank_txns.items():
    for t in txns:
        all_txns.append({**t, "bank": bank})

print(f"Classifying {len(all_txns)} transactions with Claude Haiku...\n")
classified = classify_transactions(all_txns)

# Print by bank
by_bank = defaultdict(list)
for t in classified:
    by_bank[t.get("bank","?")].append(t)

for bank in sorted(by_bank.keys()):
    print(f"\n{'='*60}")
    print(f"  {bank} ({len(by_bank[bank])} transactions)")
    print(f"{'='*60}")
    print(f"  {'Date':<12} {'Category':<22} {'Amount':>12}  Description")
    print(f"  {'-'*82}")
    for t in sorted(by_bank[bank], key=lambda x: x.get('date', '')):
        amt = t.get('amount') or 0
        # positive = spend, negative = refund
        print(f"  {t.get('date',''):<12} {t.get('category',''):<22} {amt:>+11,.2f}  {str(t.get('description',''))[:45]}")

print(f"\n\nTotal: {len(classified)} transactions classified")
