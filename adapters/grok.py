from __future__ import annotations

import re

from adapters.base import get_html, stub, today
from kaoyi.models import Plan, PriceCell, Snapshot, Vendor

SOURCE_URL = "https://x.ai/pricing"
LITE_SUBSCRIBE_URL = "https://grok.com/supergrok?referrer=pricing&target=supergroklite"
HEAVY_SUBSCRIBE_URL = "https://grok.com/supergrok?referrer=grok-build"
VENDOR_ID = "grok"
SUBSCRIBE_NOTE = "标价来自 grok.com 订阅页（定价页对照表有档名无数字）"
_SUBSCRIBE_MISS = (
    "Parsed SuperGrok / SuperGrok Plus cards. Lite/Heavy subscribe HTML had no $N USD/month."
)

# Subscribe cards print "$10 USD/month". Never infer N from another SKU.
_USD_MONTH = re.compile(r"\$(\d+)\s*USD\s*/\s*month", re.I)
_OFFICIAL_SKUS = (
    "SuperGrok Lite",
    "SuperGrok Plus",
    "SuperGrok Heavy",
    "SuperGrok",
)

VENDOR = Vendor(
    id=VENDOR_ID,
    name="SuperGrok",
    name_en="SuperGrok",
    kind="plan",
    status="OPEN",
    region="GLOBAL",
    currency="USD",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url=SOURCE_URL,
    adapter="grok",
    short="SuperGrok membership",
    notes="",
)


def parse_subscribe_monthly_usd(html: str, sku_name: str) -> int | None:
    """Return N only if `$N USD/month` is printed after sku_name.

    Stop at the next official SKU so a later SuperGrok card cannot
    supply $30 to Lite/Heavy. Missing text stays None. Never multiplies.
    """
    start = 0
    while True:
        idx = html.find(sku_name, start)
        if idx < 0:
            return None
        window = html[idx + len(sku_name) : idx + 500]
        cut = len(window)
        for other in _OFFICIAL_SKUS:
            if other == sku_name:
                continue
            pos = window.find(other)
            if pos >= 0:
                cut = min(cut, pos)
        match = _USD_MONTH.search(window[:cut])
        if match:
            return int(match.group(1))
        start = idx + len(sku_name)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")
    if "$30" not in html or "$100" not in html:
        return stub(VENDOR, fetched_ok=True, notes="$30 / $100 not both visible.")

    as_of = today()
    lite = _subscribe_plan("lite", "SuperGrok Lite", LITE_SUBSCRIBE_URL, as_of)
    heavy = _subscribe_plan("heavy", "SuperGrok Heavy", HEAVY_SUBSCRIBE_URL, as_of)
    have_subscribe = lite.price.amount is not None and heavy.price.amount is not None
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=have_subscribe,
        status="OPEN",
        billing_unit="月订阅",
        notes=SUBSCRIBE_NOTE if have_subscribe else _SUBSCRIBE_MISS,
        plans=[
            _card("free", "Free", "$0", 0, as_of, SOURCE_URL),
            lite,
            _card("supergrok", "SuperGrok", "$30", 30, as_of, SOURCE_URL),
            _card("plus", "SuperGrok Plus", "$100", 100, as_of, SOURCE_URL),
            heavy,
        ],
    )


def _subscribe_plan(plan_id: str, name: str, source_url: str, as_of: str) -> Plan:
    fetched, html = get_html(source_url)
    amount = parse_subscribe_monthly_usd(html, name) if fetched else None
    if amount is None:
        return Plan(
            id=plan_id,
            name=name,
            price=PriceCell(
                display="-",
                amount=None,
                currency="USD",
                period="month",
                source_url=source_url,
                as_of=as_of,
            ),
        )
    return _card(
        plan_id,
        name,
        f"${amount}",
        float(amount),
        as_of,
        source_url,
        note=SUBSCRIBE_NOTE,
    )


def _card(
    plan_id: str,
    name: str,
    display: str,
    amount: float,
    as_of: str,
    source_url: str,
    *,
    note: str | None = None,
) -> Plan:
    return Plan(
        id=plan_id,
        name=name,
        price=PriceCell(
            display=display,
            amount=amount,
            currency="USD",
            period="month",
            source_url=source_url,
            as_of=as_of,
            note=note,
        ),
    )
