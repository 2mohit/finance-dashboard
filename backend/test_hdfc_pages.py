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
    headers_map = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
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
            print("FAILED to open")
            continue

        with pdf:
            print(f"Opened. Pages: {len(pdf.pages)}")
            for i, page in enumerate(pdf.pages[:3]):
                tables = page.extract_tables()
                text = page.extract_text() or ""
                print(f"\n=== Page {i+1} ({len(tables)} tables) ===")
                for j, table in enumerate(tables):
                    if not table: continue
                    print(f"  Table {j} ({len(table)} rows):")
                    for row in table:
                        cells = [str(c)[:40] if c else "" for c in row]
                        if any(cells):
                            print(f"    {cells}")
                if not tables:
                    print(f"  Text: {text[:500]}")
    break
