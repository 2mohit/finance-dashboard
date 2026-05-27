import os, io
os.environ["PYTHONIOENCODING"] = "utf-8"
import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect
from agent.email_reader import _get_gmail_service, _build_statement_query, _extract_parts, _decode_body
from dotenv import load_dotenv
load_dotenv()

service = _get_gmail_service()
query = _build_statement_query(45)
response = service.users().messages().list(userId="me", q=query, maxResults=10).execute()

for msg_ref in response.get("messages", []):
    msg = service.users().messages().get(userId="me", id=msg_ref["id"], format="full").execute()
    payload = msg.get("payload", {})
    headers_map = {h["name"]: h["value"] for h in payload.get("headers", [])}
    if "HDFC" not in headers_map.get("Subject", ""):
        continue

    _, attachments = _extract_parts(payload)
    raw_passwords = os.getenv("PDF_PASSWORDS", "")
    passwords = [""] + [p.strip() for p in raw_passwords.split(",") if p.strip()]

    for ref in attachments:
        att = service.users().messages().attachments().get(
            userId="me", messageId=msg_ref["id"], id=ref["attachment_id"]
        ).execute()
        pdf_bytes = _decode_body(att.get("data", ""))
        pdf = None
        for pwd in passwords:
            try:
                pdf = pdfplumber.open(io.BytesIO(pdf_bytes), password=pwd)
                break
            except PDFPasswordIncorrect:
                continue
        if pdf is None:
            continue

        with pdf:
            print("=== FULL PAGE 1 TEXT ===")
            print(pdf.pages[0].extract_text())
    break
