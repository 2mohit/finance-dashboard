"""
Standalone test: verify PDF passwords for all saved statements.

Run from backend/ directory:
    python scripts/test_pdf_passwords.py

Checks each PDF in data/pdfs/ against its bank-specific password and shows
which ones can be unlocked.  Also re-saves unlocked copies to data/pdfs/unlocked/.

Expected .env entries (one per bank):
    SBI_PDF_PASSWORD=<last4_mobile_or_dob>
    HSBC_PDF_PASSWORD=<last4_mobile_or_dob>
    ICICI_PDF_PASSWORD=<last4_mobile_or_dob>
    HDFC_PDF_PASSWORD=<last4_mobile_or_dob>
"""

import sys
from pathlib import Path

# Run from backend/ directory
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", encoding="utf-8-sig")

import fitz  # PyMuPDF
from agent.parser import get_bank_passwords

PDF_DIR = ROOT / "data" / "pdfs"
UNLOCKED_DIR = PDF_DIR / "unlocked"

BANKS = ["SBI", "HSBC", "ICICI", "HDFC"]


def test_bank_password(bank: str) -> None:
    passwords = get_bank_passwords(bank)
    specific = [p for p in passwords if p]
    print(f"\n{'-'*50}")
    print(f"Bank: {bank}")
    print(f"Passwords configured: {len(specific)} specific + '' (empty)")

    pdfs = sorted(PDF_DIR.glob(f"{bank}_*.pdf"))
    if not pdfs:
        print(f"  No PDFs found for {bank} — run a sync first")
        return

    for pdf_path in pdfs:
        print(f"\n  File: {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)")
        doc = fitz.open(str(pdf_path))

        if not doc.is_encrypted:
            print(f"  -> Not encrypted, no password needed")
            doc.close()
            continue

        opened_with = None
        for pwd in passwords:
            result = doc.authenticate(pwd)
            if result:
                opened_with = pwd
                break

        if opened_with is None:
            print(f"  FAIL FAILED — no configured password worked")
            print(f"    Add {bank.upper()}_PDF_PASSWORD=<correct_password> to your .env")
            doc.close()
            continue

        pages = doc.page_count
        page1 = doc.load_page(0).get_text()[:100].replace("\n", " ").strip()
        print(f"  OK Opened  password={repr(opened_with)}  pages={pages}")
        print(f"    Page 1 preview: {repr(page1)}")

        # Save unlocked copy
        dest = UNLOCKED_DIR / pdf_path.name
        if dest.exists():
            print(f"  -> Unlocked copy already exists")
        else:
            UNLOCKED_DIR.mkdir(parents=True, exist_ok=True)
            doc.save(str(dest), encryption=fitz.PDF_ENCRYPT_NONE)
            print(f"  -> Saved unlocked copy to unlocked/{pdf_path.name}")

        doc.close()


def main():
    print("=" * 50)
    print("PDF Password Test")
    print("=" * 50)

    if not PDF_DIR.exists() or not list(PDF_DIR.glob("*.pdf")):
        print("\nNo PDFs in data/pdfs/ yet.")
        print("Run a sync first: POST /api/sync or use the Refresh PDFs button.")
        return

    for bank in BANKS:
        test_bank_password(bank)

    print(f"\n{'-'*50}")
    print("Summary of unlocked copies:")
    if UNLOCKED_DIR.exists():
        for p in sorted(UNLOCKED_DIR.glob("*.pdf")):
            doc = fitz.open(str(p))
            status = "OK (no password)" if not doc.is_encrypted else "still encrypted!"
            print(f"  {p.name}: {status}, pages={doc.page_count}")
            doc.close()
    else:
        print("  None yet")


if __name__ == "__main__":
    main()
