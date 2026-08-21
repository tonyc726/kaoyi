from __future__ import annotations

import json
from datetime import date
from typing import Any, NamedTuple

import httpx
from selectolax.parser import HTMLParser

from kaoyi.models import Snapshot, Vendor, empty_snapshot

USER_AGENT = "kaoyi-fetch/0.1 (+https://github.com/tonyc726/kaoyi)"
TIMEOUT = 20.0


class JsonLdOffer(NamedTuple):
    name: str
    price: float | None
    currency: str | None


def today() -> str:
    return date.today().isoformat()


def get_html(url: str) -> tuple[bool, str]:
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            follow_redirects=True,
            timeout=TIMEOUT,
        )
        if response.status_code >= 400:
            return False, ""
        return True, response.text
    except httpx.HTTPError:
        return False, ""


def text_of(html: str) -> str:
    tree = HTMLParser(html)
    return tree.text(separator="\n", strip=True)


def stub(vendor: Vendor, *, fetched_ok: bool = False, notes: str | None = None) -> Snapshot:
    snapshot = empty_snapshot(vendor, today())
    snapshot.fetched_ok = fetched_ok
    snapshot.parse_ok = False
    if notes:
        snapshot.notes = notes
    return snapshot


def parse_ld_json_offers(html: str) -> list[JsonLdOffer]:
    """Collect schema.org Offer name/price/priceCurrency from application/ld+json."""
    found: list[JsonLdOffer] = []
    seen: set[tuple[str, float | None, str | None]] = set()
    for payload in _iter_ld_json(html):
        for offer in _walk_ld_offers(payload):
            key = (offer.name, offer.price, offer.currency)
            if key in seen:
                continue
            seen.add(key)
            found.append(offer)
    return found


def _iter_ld_json(html: str) -> list[Any]:
    payloads: list[Any] = []
    tree = HTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        text = (node.text() or "").strip()
        if not text:
            continue
        try:
            payloads.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return payloads


def _walk_ld_offers(node: Any, *, in_offers: bool = False) -> list[JsonLdOffer]:
    if isinstance(node, list):
        offers: list[JsonLdOffer] = []
        for item in node:
            offers.extend(_walk_ld_offers(item, in_offers=in_offers))
        return offers
    if not isinstance(node, dict):
        return []

    offers = []
    types = _schema_types(node)
    name = node.get("name")
    has_price = "price" in node
    has_currency = node.get("priceCurrency") is not None
    looks_like_offer = isinstance(name, str) and bool(name.strip()) and has_price and has_currency
    if "Offer" in types or (in_offers and isinstance(name, str) and has_price) or looks_like_offer:
        if isinstance(name, str) and name.strip():
            offers.append(
                JsonLdOffer(
                    name=name.strip(),
                    price=_parse_offer_price(node.get("price")),
                    currency=_parse_offer_currency(node.get("priceCurrency")),
                )
            )

    if "offers" in node:
        offers.extend(_walk_ld_offers(node["offers"], in_offers=True))
    if "@graph" in node:
        offers.extend(_walk_ld_offers(node["@graph"], in_offers=False))
    for key, value in node.items():
        if key in {"offers", "@graph", "@type", "@context"}:
            continue
        if isinstance(value, dict | list):
            offers.extend(_walk_ld_offers(value, in_offers=False))
    return offers


def _schema_types(node: dict[str, Any]) -> set[str]:
    raw = node.get("@type")
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = [item for item in raw if isinstance(item, str)]
    else:
        return set()
    return {item.rsplit("/", 1)[-1] for item in items}


def _parse_offer_price(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", ""))
        except ValueError:
            return None
    return None


def _parse_offer_currency(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
