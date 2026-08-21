from __future__ import annotations

from adapters.base import get_html, stub
from kaoyi.models import Snapshot, Vendor

SOURCE_URL = "https://openai.com/chatgpt/pricing"
VENDOR_ID = "openai"

VENDOR = Vendor(
    id=VENDOR_ID,
    name="OpenAI ChatGPT/Codex",
    name_en="ChatGPT / Codex",
    kind="plan",
    status="OPEN",
    region="GLOBAL",
    currency="USD",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url="https://help.openai.com/en/articles/6950777",
    adapter="openai",
    short="ChatGPT membership",
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(
            VENDOR,
            notes="Pricing page blocked or timed out. Do not invent ChatGPT dollar amounts.",
        )
    # Cloudflare / JS pages often omit the actual numbers in first HTML.
    if "$20" not in html:
        return stub(
            VENDOR,
            fetched_ok=True,
            notes="No $20 visible on first HTML. Keep hand snapshot from help center.",
        )
    return stub(VENDOR, fetched_ok=True, notes="Parser not ready. Source recorded.")
