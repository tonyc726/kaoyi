from __future__ import annotations

from adapters.base import JsonLdOffer, get_html, parse_ld_json_offers, stub, today
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

_OFFER_PLANS: tuple[tuple[str, str, str], ...] = (
    ("hobby", "Hobby", "month"),
    ("pro", "Pro", "month"),
    ("pro-plus", "Pro+", "month"),
    ("ultra", "Ultra", "month"),
    ("teams", "Teams", "user-month"),
)

_SNAPSHOT_NOTES = (
    "Prices from official JSON-LD Offers on cursor.com/pricing, "
    "not the default Individual tab. Enterprise is Custom."
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")
    return parse(html)


def parse(html: str, *, as_of: str | None = None) -> Snapshot:
    has_names = all(name in html for name in ("Hobby", "Pro+", "Ultra", "Teams", "Enterprise"))
    offers = {offer.name: offer for offer in parse_ld_json_offers(html)}
    has_offers = any(name in offers for name, _, _ in _OFFER_PLANS)
    if not has_names and not has_offers:
        return stub(VENDOR, fetched_ok=True, notes="Official SKU labels not all visible.")

    as_of = as_of or today()
    plans = [
        Plan(
            id=plan_id,
            name=name,
            price=_price_from_offer(offers.get(name), period, as_of),
            quota="Limited Agent requests；Composer" if plan_id == "hobby" else "-",
        )
        for plan_id, name, period in _OFFER_PLANS
    ]
    plans.append(
        Plan(
            id="enterprise",
            name="Enterprise",
            price=_cell("Custom", None, None, as_of),
        )
    )
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=True,
        status="OPEN",
        billing_unit="月订阅 / 席",
        notes=_SNAPSHOT_NOTES,
        plans=plans,
    )


def _price_from_offer(offer: JsonLdOffer | None, period: str, as_of: str) -> PriceCell:
    if offer is None or offer.price is None:
        return _cell("-", None, period, as_of, note="官方有这一档，未见单独报价")
    currency = (offer.currency or "").upper()
    if currency and currency != "USD":
        return _cell("-", None, period, as_of, note="官方有这一档，未见单独报价")
    amount = int(offer.price) if offer.price == int(offer.price) else offer.price
    return _cell(_usd_display(offer.price), amount, period, as_of)


def _usd_display(amount: float) -> str:
    if amount == int(amount):
        return f"${int(amount)}"
    return f"${amount}"


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
