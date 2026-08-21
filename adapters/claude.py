from __future__ import annotations

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
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")

    has_pro = "$20" in html and "billed monthly" in html.lower()
    has_max_card = "From $100" in html or "From\n$100" in html
    has_max_5x = "Max 5x" in html
    has_max_20x = "Max 20x" in html
    if not (has_pro and has_max_card and has_max_5x and has_max_20x):
        return stub(VENDOR, fetched_ok=True, notes="Official SKU labels not all visible.")

    as_of = today()
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=True,
        status="OPEN",
        billing_unit="月订阅",
        notes="Individual SKUs from claude.com/pricing. API rates ignored.",
        plans=[
            Plan(
                id="free",
                name="Free",
                price=_usd("$0", 0, as_of),
            ),
            Plan(
                id="pro",
                name="Pro",
                price=_usd(
                    "$20",
                    20,
                    as_of,
                    note="月付 $20。年付 $17/月（$200 预付）。",
                ),
            ),
            Plan(
                id="max-5x",
                name="Max 5x",
                price=_usd(
                    "From $100",
                    100,
                    as_of,
                    note="卡片写 From $100 / month。文案：Choose 5x or 20x more usage than Pro。",
                ),
            ),
            Plan(
                id="max-20x",
                name="Max 20x",
                price=PriceCell(
                    display="-",
                    amount=None,
                    currency="USD",
                    period="month",
                    source_url=SOURCE_URL,
                    as_of=as_of,
                    note="对照表有 Max 20x 列，未见独立美元标价。不编造。",
                ),
            ),
        ],
    )


def _usd(display: str, amount: float, as_of: str, *, note: str | None = None) -> PriceCell:
    return PriceCell(
        display=display,
        amount=amount,
        currency="USD",
        period="month",
        source_url=SOURCE_URL,
        as_of=as_of,
        note=note,
    )
