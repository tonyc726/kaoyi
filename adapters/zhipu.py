from __future__ import annotations

from adapters.base import get_html, stub
from kaoyi.models import Snapshot, Vendor

SOURCE_URL = "https://www.bigmodel.cn/glm-coding"
DOCS_URL = "https://docs.bigmodel.cn/cn/coding-plan/overview"
VENDOR_ID = "zhipu"

VENDOR = Vendor(
    id=VENDOR_ID,
    name="智谱AI",
    name_en="Zhipu GLM",
    kind="plan",
    status="OPEN",
    region="CN",
    currency="CNY",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url=DOCS_URL,
    adapter="zhipu",
    short="GLM Coding Plan",
    slots={"entry": "lite", "mid": "pro", "high": "max"},
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched or not html:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")
    # Landing page is a JS shell; do not guess prices from an empty app root.
    if "¥118" not in html and "118" not in html:
        return stub(
            VENDOR,
            fetched_ok=True,
            notes=f"JS shell only. Keep hand snapshot. Source {SOURCE_URL}",
        )
    return stub(VENDOR, fetched_ok=True, notes="Parser not ready. Source recorded only.")
