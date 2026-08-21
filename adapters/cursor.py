from __future__ import annotations

import re

from adapters.base import get_html, stub, today
from kaoyi.models import Plan, PriceCell, Snapshot, Vendor

SOURCE_URL = "https://cursor.com/pricing"
VENDOR_ID = "cursor"

VENDOR = Vendor(
    id=VENDOR_ID,
    name="Cursor",
    name_en="Cursor",
    kind="plan",
    status="OPEN",
    region="GLOBAL",
    currency="USD",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url=SOURCE_URL,
    adapter="cursor",
    short="Individual / Teams",
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")

    has_pro = re.search(r"\$20\s*/\s*mo", html, flags=re.I)
    has_teams = re.search(r"\$40\s*/\s*user\s*/\s*mo", html, flags=re.I)
    has_names = all(name in html for name in ("Hobby", "Pro+", "Ultra", "Teams", "Enterprise"))
    if not has_pro or not has_teams or not has_names:
        return stub(VENDOR, fetched_ok=True, notes="Official SKU labels not all visible.")

    as_of = today()
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=True,
        status="OPEN",
        billing_unit="月订阅 / 席",
        notes="Individual SKUs: Hobby / Pro / Pro+ / Ultra. Only Hobby and Pro printed a number.",
        plans=[
            Plan(
                id="hobby",
                name="Hobby",
                price=_cell("$0", 0, "month", as_of),
                quota="Limited Agent requests；Composer",
            ),
            Plan(
                id="pro",
                name="Pro",
                price=_cell("$20", 20, "month", as_of),
            ),
            Plan(
                id="pro-plus",
                name="Pro+",
                price=_cell("-", None, "month", as_of, note="官方有这一档，未见单独报价"),
            ),
            Plan(
                id="ultra",
                name="Ultra",
                price=_cell("-", None, "month", as_of, note="官方有这一档，未见单独报价"),
            ),
            Plan(
                id="teams",
                name="Teams",
                price=_cell("$40", 40, "user-month", as_of),
            ),
            Plan(
                id="enterprise",
                name="Enterprise",
                price=_cell("Custom", None, None, as_of),
            ),
        ],
    )


def _cell(
    display: str,
    amount: float | None,
    period: str | None,
    as_of: str,
    *,
    note: str | None = None,
) -> PriceCell:
    return PriceCell(
        display=display,
        amount=amount,
        currency="USD" if display != "Custom" else None,
        period=period,
        source_url=SOURCE_URL,
        as_of=as_of,
        note=note,
    )
