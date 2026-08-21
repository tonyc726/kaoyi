from __future__ import annotations

import re

from adapters.base import get_html, stub, today
from kaoyi.models import Plan, PriceCell, Snapshot, Vendor

SOURCE_URL = "https://chatgpt.com/pricing/"
HELP_PLUS = "https://help.openai.com/en/articles/6950777"
HELP_PRO = "https://help.openai.com/en/articles/9793128-about-chatgpt-pro-tiers"
VENDOR_ID = "openai"
GO_NOTE = "美国标价。部分市场本地货币。"

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
    parsed = parse_individual(html, as_of=today())
    if parsed is None:
        return stub(
            VENDOR,
            fetched_ok=True,
            notes="No Individual list prices visible on first HTML. Keep hand snapshot.",
        )
    return parsed


def parse_individual(html: str, *, as_of: str) -> Snapshot | None:
    """Parse Individual SKUs. Missing Go stays '-'. Does not invent Pro $200."""
    if not _has_individual_skus(html):
        return None
    if not _has_any_list_price(html):
        return None

    go_price = (
        _cell("$8", 8, as_of, note=GO_NOTE)
        if _has_dollar_amount(html, 8)
        else _cell("-", None, as_of)
    )
    plus_source = SOURCE_URL if _has_dollar_amount(html, 20) else HELP_PLUS
    plus_price = _cell("$20", 20, as_of, source_url=plus_source)

    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=True,
        status="OPEN",
        billing_unit="月订阅 · 会员",
        notes="这是 ChatGPT/Codex 会员，不是 API 预付。Go 美国标价，部分市场本地货币。",
        plans=[
            Plan(id="free", name="Free", price=_cell("$0", 0, as_of)),
            Plan(id="go", name="Go", price=go_price),
            Plan(
                id="plus",
                name="Plus",
                price=plus_price,
                quota="官方定价页写 Expanded Codex usage；具体次数未在本次抓取中出现",
                notes="会员，不是 API prepaid",
            ),
            Plan(
                id="pro-100",
                name="Pro $100",
                price=_cell(
                    "$100",
                    100,
                    as_of,
                    source_url=HELP_PRO,
                    note="用量约为 Plus 的 5 倍",
                ),
                quota="更高用量；Maximum Codex tasks（定价页文案）",
                notes="会员",
            ),
            Plan(
                id="pro-200",
                name="Pro $200",
                price=_cell(
                    "$200",
                    200,
                    as_of,
                    source_url=HELP_PRO,
                    note="用量约为 Plus 的 20 倍",
                ),
                quota="更高用量；Maximum Codex tasks（定价页文案）",
                notes="会员",
            ),
        ],
    )


def _has_individual_skus(html: str) -> bool:
    return all(name in html for name in ("Free", "Go", "Plus", "Pro"))


def _has_any_list_price(html: str) -> bool:
    return any(_has_dollar_amount(html, amount) for amount in (0, 8, 20, 100))


def _has_dollar_amount(html: str, amount: int) -> bool:
    return bool(re.search(rf"\${amount}(?!\d)", html))


def _cell(
    display: str,
    amount: float | None,
    as_of: str,
    *,
    source_url: str = SOURCE_URL,
    note: str | None = None,
) -> PriceCell:
    return PriceCell(
        display=display,
        amount=amount,
        currency="USD",
        period="month",
        source_url=source_url,
        as_of=as_of,
        note=note,
    )
