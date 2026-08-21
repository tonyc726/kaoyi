from __future__ import annotations

from adapters.base import get_html, stub, today
from kaoyi.models import Plan, PriceCell, Snapshot, UsageMeta, Vendor

SOURCE_URL = "https://openrouter.ai/pricing"
VENDOR_ID = "openrouter"

VENDOR = Vendor(
    id=VENDOR_ID,
    name="OpenRouter",
    name_en="OpenRouter",
    kind="usage",
    status="OPEN",
    region="GLOBAL",
    currency="USD",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url=SOURCE_URL,
    adapter="openrouter",
    short="聚合按量",
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")
    if "5.5%" not in html:
        return stub(VENDOR, fetched_ok=True, notes="Platform fee 5.5% not visible.")

    as_of = today()
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=True,
        status="OPEN",
        billing_unit="按量 · 模型目录价 + 平台费",
        notes="Platform fee only. Per-model token prices stay -.",
        plans=[
            Plan(
                id="payg",
                name="Pay-as-you-go",
                price=PriceCell(
                    display="5.5% 平台费",
                    amount=None,
                    currency="USD",
                    period="usage",
                    source_url=SOURCE_URL,
                    as_of=as_of,
                ),
                quota="500+ models" if "500+" in html else "-",
            )
        ],
        usage=UsageMeta(
            platform_fee="5.5%",
            min_spend="none",
            token_list_price="-",
            source_url=SOURCE_URL,
            as_of=as_of,
        ),
    )
