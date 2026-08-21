from __future__ import annotations

import re

from adapters.base import get_html, stub, today
from kaoyi.models import Plan, PriceCell, Snapshot, Vendor

SOURCE_URL = "https://cursor.com/pricing"
VENDOR_ID = "cursor"

VENDOR = Vendor(
    id=VENDOR_ID,
    name="Cursor",
    name_en="Cursor",
    kind="plan",
    status="OPEN",
    region="GLOBAL",
    currency="USD",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url=SOURCE_URL,
    adapter="cursor",
    short="Individual / Teams",
    slots={"entry": "hobby", "mid": "individual", "high": "teams"},
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")

    individual = re.search(r"\$20\s*/\s*mo", html, flags=re.I)
    teams = re.search(r"\$40\s*/\s*user\s*/\s*mo", html, flags=re.I)
    if not individual or not teams:
        return stub(VENDOR, fetched_ok=True, notes="Expected $20 / $40 not both visible.")

    as_of = today()
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=True,
        status="OPEN",
        billing_unit="月订阅 / 席",
        notes="Parsed visible list prices only. Pro+ / Ultra not filled.",
        plans=[
            Plan(
                id="hobby",
                name="Hobby",
                tier="entry",
                price=_usd("0", as_of, note="Free"),
                quota="Limited Agent requests",
            ),
            Plan(
                id="individual",
                name="Individual",
                tier="mid",
                price=_usd("20", as_of),
            ),
            Plan(
                id="teams",
                name="Teams",
                tier="high",
                price=_usd("40", as_of, period="user-month", note="per user / month"),
            ),
        ],
    )


def _usd(amount: str, as_of: str, *, period: str = "month", note: str | None = None) -> PriceCell:
    return PriceCell(
        display=f"${amount}",
        amount=float(amount),
        currency="USD",
        period=period,
        source_url=SOURCE_URL,
        as_of=as_of,
        note=note,
    )
