from __future__ import annotations

from datetime import date

import httpx
from selectolax.parser import HTMLParser

from kaoyi.models import Snapshot, Vendor, empty_snapshot

USER_AGENT = "kaoyi-fetch/0.1 (+https://github.com/tonyc726/kaoyi)"
TIMEOUT = 20.0


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
