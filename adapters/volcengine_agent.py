from __future__ import annotations

from adapters.base import get_html, stub
from kaoyi.models import Snapshot, Vendor

SOURCE_URL = "https://www.volcengine.com/activity/agentplan"
DOCS_URL = "https://docs.volcengine.com/docs/82379/2366394?lang=zh"
VENDOR_ID = "volcengine-agent"

VENDOR = Vendor(
    id=VENDOR_ID,
    name="方舟 Agent Plan",
    name_en="Volcengine Agent Plan",
    kind="plan",
    status="LIMITED",
    region="CN",
    currency="CNY",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url=DOCS_URL,
    adapter="volcengine-agent",
    short="Agent Plan",
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched or not html:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")
    # Activity page is a React SPA. Never promote 活动价 ¥9.90 / ¥49.90 to list price.
    if "¥40" not in html and "40.00" not in html:
        return stub(
            VENDOR,
            fetched_ok=True,
            notes="JS shell only. Keep hand snapshot of 刊例价. Never use 9.90 as display.",
        )
    return stub(VENDOR, fetched_ok=True, notes="Parser not ready. Source recorded only.")
