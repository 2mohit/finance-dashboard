"""Use Claude to classify transactions and generate monthly insights."""

import os
import json
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", encoding="utf-8-sig", override=True)
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CATEGORIES = [
    "DailyFood",
    "Dining",
    "Groceries",
    "Shopping",
    "BabyShopping",
    "Entertainment",
    "DailyTravel",
    "VacationTravel",
    "BusinessTravel",
    "Health",
    "Bills & Utilities",
    "Income",
    "Other",
]

_CLASSIFY_SYSTEM = """You are a financial transaction classifier for an Indian household.
Given a list of transactions (date, description, amount in INR), classify each into exactly one category.

Categories: {categories}

Rules:
FOOD:
- "DailyFood": small food transactions typically under ₹500 — quick bites, street food, small cafes, chai, fast food
- "Dining": restaurants with bills ≥ ₹500, fine dining, RSP*DISTRICT, hotel restaurants, Swiggy/Zomato orders, Haldiram (restaurant/food chain visits), sweet shops and mithai chains
- "Groceries": supermarkets, Reliance Retail (any amount), BigBasket, Blinkit, Zepto, kirana stores, D-Mart, packaged goods wholesale

SHOPPING:
- "BabyShopping": FirstCry, FIRSTCRY, FIRSTCRYBABY, baby/infant products
- "Shopping": Amazon if amount ≥ ₹800, Flipkart if amount ≥ ₹800, clothing, electronics, Myntra, Nykaa, general retail
- EMI RULE: Any transaction containing "EMI", "Pay in EMI", or "Instalm" in the description MUST be classified as "Shopping" (or "BabyShopping" if it's FirstCry) regardless of amount — EMIs are installments on larger purchases
- STRICT RULE: Any Flipkart or Amazon transaction with amount < ₹800 AND no EMI indicator → classify as "Groceries"

TRAVEL:
- "DailyTravel": Uber, Ola, auto, metro, local cab, Rapido, toll, fuel, parking
- "VacationTravel": flights, hotels, holiday packages, MakeMyTrip, Cleartrip, Yatra, IRCTC (leisure)
- "BusinessTravel": corporate hotel stays, work-related flights, company bookings

HEALTH:
- "Health": hospitals, doctors (including "Aparna Ahuja" who is a paediatrician), pharmacies, labs, Apollo, Medplus, gyms, wellness

REFUNDS / CREDITS:
- When a transaction is a refund (negative amount or CR flag), classify it into the SAME category as the original purchase
  - Amazon refund → Shopping (or Groceries if original was < ₹800)
  - FirstCry refund → BabyShopping
  - Flipkart refund → Shopping or Groceries (by same amount rule)
  - Myntra refund → Shopping
  - Restaurant refund → Dining or DailyFood

OTHERS:
- "Entertainment": movies, OTT (Netflix, Prime, Hotstar), concerts, gaming, RSP*DISTRICT MOVIE, BookMyShow (BIGTREE), mall activity venues (ELAN MIRACLE, DLF, Select Citywalk, Ambience Mall when amount < ₹800 suggesting activity/experience rather than shopping)
- "Bills & Utilities": electricity, phone recharge, internet, rent, insurance, DTH
- "Income": ONLY for actual income — salary deposits, bank interest, employer transfers. NOT for shopping refunds.
- "Other": anything that doesn't fit the above

Return ONLY a JSON array, one object per transaction, in the same order:
[{{"index": 0, "category": "...", "confidence": 0.95}}, ...]""".format(
    categories=", ".join(CATEGORIES)
)


def classify_transactions(transactions: list[dict]) -> list[dict]:
    """
    Add a 'category' field to each transaction using Claude.
    Batches in groups of 50 to stay within context limits.
    """
    if not transactions:
        return []

    classified = []
    batch_size = 50

    for i in range(0, len(transactions), batch_size):
        batch = transactions[i : i + batch_size]
        classified.extend(_classify_batch(batch, i))

    return classified


def _classify_batch(batch: list[dict], offset: int) -> list[dict]:
    items = [
        {
            "index": offset + j,
            "date": t.get("date", ""),
            "description": t.get("description", ""),
            "amount": t.get("amount"),
        }
        for j, t in enumerate(batch)
    ]

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=_CLASSIFY_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Classify these transactions:\n{json.dumps(items, indent=2)}",
            }
        ],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])

    classifications = json.loads(raw)
    cat_map = {c["index"]: c["category"] for c in classifications}

    result = []
    for j, t in enumerate(batch):
        enriched = dict(t)
        enriched["category"] = cat_map.get(offset + j, "Other")
        result.append(enriched)

    return result


def generate_monthly_insights(transactions: list[dict], year_month: str) -> dict:
    """
    Ask Claude to write a plain-English insight summary for a given month.

    Args:
        transactions: all transactions for that month (already classified)
        year_month: "2024-11"

    Returns:
        dict with keys: summary, top_categories, saving_tips, alert
    """
    if not transactions:
        return {}

    # amount convention: positive = spending, negative = refund/credit
    # net spend per category = sum of signed amounts (refunds auto-reduce the total)
    total_spend = sum(t.get("amount") or 0 for t in transactions
                      if t.get("category") != "Income")
    total_income = sum(-(t.get("amount") or 0) for t in transactions
                       if t.get("category") == "Income" and (t.get("amount") or 0) < 0)

    category_totals = {}
    for t in transactions:
        cat = t.get("category", "Other")
        category_totals[cat] = category_totals.get(cat, 0) + (t.get("amount") or 0)

    prompt = f"""Month: {year_month}
Total income: {total_income:.2f}
Total spend: {total_spend:.2f}
Category breakdown: {json.dumps(category_totals, indent=2)}
Top transactions (up to 10): {json.dumps([
    {{"date": t["date"], "description": t["description"], "amount": t.get("amount"), "category": t.get("category")}}
    for t in sorted(transactions, key=lambda x: x.get("amount") or 0, reverse=True)[:10]
], indent=2)}

Write a concise financial insight report as JSON with these keys:
- "summary": 2-3 sentence plain-English overview of the month
- "top_categories": list of top 3 spending categories with amounts
- "saving_tips": list of 2-3 actionable tips based on the data
- "alert": one short warning if any category looks unusually high (null if none)
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])

    return json.loads(raw)
