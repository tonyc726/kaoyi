from __future__ import annotations

from adapters.base import get_html, stub, today
from kaoyi.models import Plan, PriceCell, Snapshot, Vendor

SOURCE_URL = "https://x.ai/pricing"
VENDOR_ID = "grok"

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


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")
    if "$30" not in html or "$100" not in html:
        return stub(VENDOR, fetched_ok=True, notes="$30 / $100 not both visible.")

    as_of = today()
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=True,
        status="OPEN",
        billing_unit="月订阅",
        notes="Parsed SuperGrok / SuperGrok Plus cards. Lite/Heavy not priced.",
        plans=[
            _plan("free", "Free", "$0", 0, as_of),
            _plan("supergrok", "SuperGrok", "$30", 30, as_of),
            _plan("plus", "SuperGrok Plus", "$100", 100, as_of),
        ],
    )


def _plan(plan_id: str, name: str, display: str, amount: float, as_of: str) -> Plan:
    return Plan(
        id=plan_id,
        name=name,
        price=PriceCell(
            display=display,
            amount=amount,
            currency="USD",
            period="month",
            source_url=SOURCE_URL,
            as_of=as_of,
        ),
    )
