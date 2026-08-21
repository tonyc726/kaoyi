from __future__ import annotations

from adapters.base import get_html, stub
from kaoyi.models import Snapshot, Vendor

SOURCE_URL = "https://www.volcengine.com/activity/codingplan"
VENDOR_ID = "volcengine"

VENDOR = Vendor(
    id=VENDOR_ID,
    name="字节·方舟",
    name_en="Volcengine Ark",
    kind="plan",
    status="LIMITED",
    region="CN",
    currency="CNY",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url=SOURCE_URL,
    adapter="volcengine",
    short="Coding Plan",
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed/timeout. Source {SOURCE_URL}")
    # Activity pages are highly dynamic. Never promote promo copy to list price.
    return stub(
        VENDOR,
        fetched_ok=True,
        notes="Parser not ready for activity SPA. Prices stay -. Source recorded.",
    )
