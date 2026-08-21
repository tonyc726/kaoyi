from __future__ import annotations

import re

from adapters.base import get_html, stub, today
from kaoyi.models import Plan, PriceCell, Snapshot, Vendor

SOURCE_URL = "https://platform.minimaxi.com/docs/guides/pricing-token-plan"
VENDOR_ID = "minimax"

VENDOR = Vendor(
    id=VENDOR_ID,
    name="MiniMax",
    name_en="MiniMax",
    kind="plan",
    status="OPEN",
    region="CN",
    currency="CNY",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url=SOURCE_URL,
    adapter="minimax",
    short="Token Plan",
    slots={"entry": "plus", "mid": "max", "high": "ultra"},
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")

    prices = {
        "plus": _first_amount(html, r"Plus.*?¥\s*(\d+)"),
        "max": _first_amount(html, r"\*\*Max\*\*.*?¥\s*(\d+)|Max</td>.*?¥\s*(\d+)"),
        "ultra": _first_amount(html, r"Ultra.*?¥\s*(\d+)"),
    }
    # Fallback: the official table lists ¥49 / ¥119 / ¥469 in that order.
    listed = re.findall(r"¥\s*(49|119|469)", html)
    if not any(prices.values()) and listed == ["49", "119", "469"]:
        prices = {"plus": 49, "max": 119, "ultra": 469}

    if not all(prices.values()):
        return stub(
            VENDOR,
            fetched_ok=True,
            notes="Parse incomplete; refusing to invent. Source recorded.",
        )

    as_of = today()
    names = {"plus": "Plus", "max": "Max", "ultra": "Ultra"}
    tiers = {"plus": "entry", "max": "mid", "ultra": "high"}
    plans = [
        Plan(
            id=plan_id,
            name=names[plan_id],
            tier=tiers[plan_id],
            price=PriceCell(
                display=f"¥{amount}",
                amount=float(amount),
                currency="CNY",
                period="month",
                source_url=SOURCE_URL,
                as_of=as_of,
            ),
        )
        for plan_id, amount in prices.items()
    ]
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=True,
        status="OPEN",
        billing_unit="月订阅额度",
        notes="Parsed from official Token Plan docs.",
        plans=plans,
    )


def _first_amount(html: str, pattern: str) -> int | None:
    match = re.search(pattern, html, flags=re.I | re.S)
    if not match:
        return None
    for group in match.groups():
        if group:
            return int(group)
    return None
