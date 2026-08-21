from __future__ import annotations

from pathlib import Path

from adapters.grok import (
    HEAVY_SUBSCRIBE_URL,
    LITE_SUBSCRIBE_URL,
    parse_subscribe_monthly_usd,
)
from adapters.grok import fetch as fetch_grok
from kaoyi.load import assemble

ROOT = Path(__file__).resolve().parents[1]


def test_claude_lists_official_max_skus() -> None:
    page = assemble(ROOT).page("claude")
    names = [plan.name for plan in page.snapshot.plans]
    assert names == ["Free", "Pro", "Max 5x", "Max 20x"]
    max20 = next(plan for plan in page.snapshot.plans if plan.name == "Max 20x")
    assert max20.price.display == "-"
    assert "10x" not in max20.name


def test_cursor_lists_individual_official_names() -> None:
    plans = assemble(ROOT).page("cursor").snapshot.plans
    names = [plan.name for plan in plans]
    assert names[:4] == ["Hobby", "Pro", "Pro+", "Ultra"]
    by_name = {plan.name: plan for plan in plans}
    assert by_name["Pro+"].price.display == "$60"
    assert by_name["Pro+"].price.amount == 60
    assert by_name["Pro+"].price.note is None
    assert by_name["Ultra"].price.display == "$200"
    assert by_name["Ultra"].price.amount == 200
    assert by_name["Ultra"].price.note is None
    assert by_name["Enterprise"].price.display == "Custom"


def test_openai_pro_uses_help_center_names_not_5x() -> None:
    names = [plan.name for plan in assemble(ROOT).page("openai").snapshot.plans]
    assert "Go" in names
    assert "Plus" in names
    assert "Pro $100" in names
    assert "Pro $200" in names
    assert "Pro 5x" not in names
    assert "Pro 20x" not in names


def test_grok_snapshot_lists_official_individual_ladder() -> None:
    plans = assemble(ROOT).page("grok").snapshot.plans
    assert [plan.name for plan in plans] == [
        "Free",
        "SuperGrok Lite",
        "SuperGrok",
        "SuperGrok Plus",
        "SuperGrok Heavy",
    ]
    by_name = {plan.name: plan for plan in plans}

    free = by_name["Free"].price
    assert free.display == "$0"
    assert free.amount == 0
    assert free.source_url == "https://x.ai/pricing"

    lite = by_name["SuperGrok Lite"].price
    assert lite.display == "$10"
    assert lite.amount == 10
    assert lite.currency == "USD"
    assert lite.period == "month"
    assert lite.as_of == "2026-08-21"
    assert lite.source_url == LITE_SUBSCRIBE_URL

    assert by_name["SuperGrok"].price.display == "$30"
    assert by_name["SuperGrok"].price.amount == 30
    assert by_name["SuperGrok"].price.source_url == "https://x.ai/pricing"

    assert by_name["SuperGrok Plus"].price.display == "$100"
    assert by_name["SuperGrok Plus"].price.amount == 100
    assert by_name["SuperGrok Plus"].price.source_url == "https://x.ai/pricing"

    heavy = by_name["SuperGrok Heavy"].price
    assert heavy.display == "$300"
    assert heavy.amount == 300
    assert heavy.currency == "USD"
    assert heavy.period == "month"
    assert heavy.as_of == "2026-08-21"
    assert heavy.source_url == HEAVY_SUBSCRIBE_URL


def test_parse_subscribe_reads_printed_usd_month() -> None:
    lite_html = "SuperGrok Lite $10 USD/month SuperGrok $30 USD/month"
    heavy_html = (
        "SuperGrok $30 USD/month SuperGrok Plus $100 USD/month SuperGrok Heavy $300 USD/month"
    )
    assert parse_subscribe_monthly_usd(lite_html, "SuperGrok Lite") == 10
    assert parse_subscribe_monthly_usd(heavy_html, "SuperGrok Heavy") == 300


def test_parse_subscribe_does_not_invent_ten_x_supergrok() -> None:
    html = """
    SuperGrok $30 USD/month
    SuperGrok Plus $100 USD/month
    SuperGrok Lite
    SuperGrok Heavy
    """
    assert parse_subscribe_monthly_usd(html, "SuperGrok Lite") is None
    assert parse_subscribe_monthly_usd(html, "SuperGrok Heavy") is None
    assert parse_subscribe_monthly_usd(html, "SuperGrok") == 30


def test_grok_adapter_missing_subscribe_parse_stays_dash(monkeypatch) -> None:
    def fake_get_html(url: str) -> tuple[bool, str]:
        if url.startswith("https://x.ai/"):
            return True, (
                "Free $0 SuperGrok Lite $10 SuperGrok $30 "
                "SuperGrok Plus $100 SuperGrok Heavy $300"
            )
        if "grok.com" in url:
            return True, "<html>SuperGrok Lite SuperGrok Heavy SuperGrok $30 USD/month</html>"
        return False, ""

    monkeypatch.setattr("adapters.grok.get_html", fake_get_html)
    snapshot = fetch_grok()
    by_name = {plan.name: plan for plan in snapshot.plans}
    assert [plan.name for plan in snapshot.plans] == [
        "Free",
        "SuperGrok Lite",
        "SuperGrok",
        "SuperGrok Plus",
        "SuperGrok Heavy",
    ]
    assert by_name["SuperGrok"].price.amount == 30
    assert by_name["SuperGrok Lite"].price.display == "-"
    assert by_name["SuperGrok Lite"].price.amount is None
    assert by_name["SuperGrok Heavy"].price.display == "-"
    assert by_name["SuperGrok Heavy"].price.amount is None
    assert snapshot.parse_ok is False


def test_grok_adapter_blocked_subscribe_fetch_stays_dash(monkeypatch) -> None:
    def fake_get_html(url: str) -> tuple[bool, str]:
        if url.startswith("https://x.ai/"):
            return True, "Free $0 SuperGrok $30 SuperGrok Plus $100"
        return False, ""

    monkeypatch.setattr("adapters.grok.get_html", fake_get_html)
    snapshot = fetch_grok()
    by_name = {plan.name: plan for plan in snapshot.plans}
    assert by_name["SuperGrok Lite"].price.display == "-"
    assert by_name["SuperGrok Lite"].price.amount is None
    assert by_name["SuperGrok Heavy"].price.display == "-"
    assert by_name["SuperGrok Heavy"].price.amount is None


def test_grok_adapter_parses_lite_and_heavy_from_subscribe_html(monkeypatch) -> None:
    def fake_get_html(url: str) -> tuple[bool, str]:
        if url.startswith("https://x.ai/"):
            return True, "Free $0 SuperGrok $30 SuperGrok Plus $100"
        if "supergroklite" in url:
            return True, "SuperGrok Lite $10 USD/month SuperGrok $30 USD/month"
        if "grok.com" in url:
            return True, (
                "SuperGrok $30 USD/month SuperGrok Plus $100 USD/month "
                "SuperGrok Heavy $300 USD/month"
            )
        return False, ""

    monkeypatch.setattr("adapters.grok.get_html", fake_get_html)
    snapshot = fetch_grok()
    by_name = {plan.name: plan for plan in snapshot.plans}
    assert by_name["SuperGrok Lite"].price.display == "$10"
    assert by_name["SuperGrok Lite"].price.amount == 10
    assert by_name["SuperGrok Lite"].price.source_url == LITE_SUBSCRIBE_URL
    assert by_name["SuperGrok Heavy"].price.display == "$300"
    assert by_name["SuperGrok Heavy"].price.amount == 300
    assert by_name["SuperGrok Heavy"].price.source_url == HEAVY_SUBSCRIBE_URL
    assert snapshot.parse_ok is True
