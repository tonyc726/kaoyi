from __future__ import annotations

import re

from adapters.base import get_html, stub, text_of, today
from kaoyi.models import Plan, PriceCell, Snapshot, Vendor

SOURCE_URL = "https://claude.com/pricing"
HELP_MAX_URL = "https://support.anthropic.com/en/articles/11049741-what-is-the-max-plan"
VENDOR_ID = "claude"
MAX20_NOTE = "定价页只写 From $100"
_HELP_MISS = (
    "Parsed Free / Pro / Max 5x from claude.com/pricing. "
    "Help Center HTML had no Max 20x $N per month."
)

# Help Center prints "Max 20x: $200 per month" or table "Max 20x $200 monthly".
# Never infer N from Max 5x.
_USD_MONTH = re.compile(r"\$(\d+)\s*(?:per\s+month|monthly|/month)", re.I)
_MAX_SKUS = ("Max 5x", "Max 20x")

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


def parse_help_monthly_usd(html: str, sku_name: str) -> int | None:
    """Return N only if `$N per month` / `$N monthly` is printed after sku_name.

    Stop at the next Max SKU so Max 5x $100 cannot supply Max 20x.
    Missing text stays None. Never multiplies.
    """
    blob = text_of(html) if "<" in html else html
    start = 0
    while True:
        idx = blob.find(sku_name, start)
        if idx < 0:
            return None
        window = blob[idx + len(sku_name) : idx + 500]
        cut = len(window)
        for other in _MAX_SKUS:
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

    has_pro = "$20" in html and "billed monthly" in html.lower()
    has_max_card = "From $100" in html or "From\n$100" in html
    has_max_5x = "Max 5x" in html
    has_max_20x = "Max 20x" in html
    if not (has_pro and has_max_card and has_max_5x and has_max_20x):
        return stub(VENDOR, fetched_ok=True, notes="Official SKU labels not all visible.")

    as_of = today()
    help_ok, help_html = get_html(HELP_MAX_URL)
    max20 = parse_help_monthly_usd(help_html, "Max 20x") if help_ok else None
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=max20 is not None,
        status="OPEN",
        billing_unit="月订阅",
        notes=MAX20_NOTE if max20 is not None else _HELP_MISS,
        plans=[
            Plan(
                id="free",
                name="Free",
                price=_cell("$0", 0, as_of),
            ),
            Plan(
                id="pro",
                name="Pro",
                price=_cell(
                    "$20",
                    20,
                    as_of,
                    note="年付 $17/月（$200 预付）",
                ),
            ),
            Plan(
                id="max-5x",
                name="Max 5x",
                price=_cell("From $100", 100, as_of),
            ),
            Plan(
                id="max-20x",
                name="Max 20x",
                price=_max20_cell(max20, as_of),
            ),
        ],
    )


def _max20_cell(amount: int | None, as_of: str) -> PriceCell:
    if amount is None:
        return _cell("-", None, as_of, source_url=HELP_MAX_URL)
    return _cell(
        f"${amount}",
        float(amount),
        as_of,
        source_url=HELP_MAX_URL,
        note=MAX20_NOTE,
    )


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
