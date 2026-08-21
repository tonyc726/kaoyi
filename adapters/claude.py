from __future__ import annotations

import re

from adapters.base import get_html, stub, today
from kaoyi.models import Plan, PriceCell, Snapshot, Vendor

SOURCE_URL = "https://claude.com/pricing"
VENDOR_ID = "claude"

VENDOR = Vendor(
    id=VENDOR_ID,
    name="Claude",
    name_en="Claude",
    kind="plan",
    status="OPEN",
    region="GLOBAL",
    currency="USD",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url=SOURCE_URL,
    adapter="claude",
    short="Individual membership",
    slots={"entry": "free", "mid": "pro", "high": "max"},
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")

    has_pro = "$20" in html and re.search(r"billed monthly|if billed monthly", html, flags=re.I)
    has_max = re.search(r"From\s+\$100", html, flags=re.I)
    if not has_pro or not has_max:
        return stub(VENDOR, fetched_ok=True, notes="Pro/Max list text not both visible.")

    as_of = today()
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=True,
        status="OPEN",
        billing_unit="月订阅",
        notes="Parsed official membership cards. API rates ignored on this row.",
        plans=[
            Plan(
                id="free",
                name="Free",
                tier="entry",
                price=PriceCell(
                    display="$0",
                    amount=0,
                    currency="USD",
                    period="month",
                    source_url=SOURCE_URL,
                    as_of=as_of,
                ),
            ),
            Plan(
                id="pro",
                name="Pro",
                tier="mid",
                price=PriceCell(
                    display="$20",
                    amount=20,
                    currency="USD",
                    period="month",
                    source_url=SOURCE_URL,
                    as_of=as_of,
                    note="月付 $20；年付另见官方页",
                ),
            ),
            Plan(
                id="max",
                name="Max",
                tier="high",
                price=PriceCell(
                    display="From $100",
                    amount=100,
                    currency="USD",
                    period="month",
                    source_url=SOURCE_URL,
                    as_of=as_of,
                    note="Only 'From $100' was visible",
                ),
            ),
        ],
    )
