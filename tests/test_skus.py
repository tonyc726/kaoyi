from __future__ import annotations

from pathlib import Path

from adapters.grok import (
    HEAVY_SUBSCRIBE_URL,
    LITE_SUBSCRIBE_URL,
    parse_subscribe_monthly_usd,
)
from adapters.grok import fetch as fetch_grok
from adapters.volcengine_agent import fetch as fetch_volcengine_agent
from kaoyi.load import assemble

ROOT = Path(__file__).resolve().parents[1]


def test_volcengine_agent_lists_official_skus() -> None:
    page = assemble(ROOT).page("volcengine-agent")
    names = [plan.name for plan in page.snapshot.plans]
    assert names == ["Small", "Medium", "Large", "Max"]
    by_name = {plan.name: plan for plan in page.snapshot.plans}

    expected = {
        "Small": (40, "¥40"),
        "Medium": (200, "¥200"),
        "Large": (500, "¥500"),
        "Max": (1000, "¥1000"),
    }
    for name, (amount, display) in expected.items():
        price = by_name[name].price
        assert price.display == display
        assert price.amount == amount
        assert price.currency == "CNY"
        assert price.period == "month"
        assert price.source_url == "https://www.volcengine.com/activity/agentplan"
        assert "9.9" not in price.display
        assert "49.9" not in price.display

    assert "活动价 ¥9.90 见事件" in (by_name["Small"].price.note or "")
    assert "活动价 ¥49.90 见事件" in (by_name["Medium"].price.note or "")
    assert by_name["Large"].price.note is None
    assert by_name["Max"].price.note is None


def test_volcengine_coding_plan_is_unchanged() -> None:
    vendor = assemble(ROOT).vendor("volcengine")
    assert vendor.name == "字节·方舟"
    assert vendor.short == "Coding Plan"
    assert vendor.official_url == "https://www.volcengine.com/activity/codingplan"
    plans = assemble(ROOT).page("volcengine").snapshot.plans
    assert [plan.name for plan in plans] == ["Lite", "Pro"]
    assert all(plan.price.display == "-" for plan in plans)
    assert all(plan.price.amount is None for plan in plans)


def test_volcengine_agent_adapter_does_not_use_promo_as_list(monkeypatch) -> None:
    def fake_get_html(_url: str) -> tuple[bool, str]:
        return True, "<html>活动价 ¥9.90 ¥49.90 Small Medium</html>"

    monkeypatch.setattr("adapters.volcengine_agent.get_html", fake_get_html)
    snapshot = fetch_volcengine_agent()
    assert snapshot.parse_ok is False
    assert snapshot.plans == []
    assert all(plan.price.display != "¥9.90" for plan in snapshot.plans)


def test_volcengine_agent_promo_lives_in_events() -> None:
    events = assemble(ROOT).events_for("volcengine-agent")
    assert events
    event = next(item for item in events if item.kind == "promo")
    assert event.example is False
    assert event.layer == "official"
    assert event.kind == "promo"
    assert "限时" in event.summary
    assert "¥9.90" in event.summary
    assert "¥49.90" in event.summary


def test_claude_lists_official_max_skus() -> None:
    page = assemble(ROOT).page("claude")
    names = [plan.name for plan in page.snapshot.plans]
    assert names == ["Free", "Pro", "Max 5x", "Max 20x"]
    by_name = {plan.name: plan for plan in page.snapshot.plans}

    max5 = by_name["Max 5x"].price
    assert max5.display == "From $100"
    assert max5.amount == 100
    assert max5.currency == "USD"
    assert max5.period == "month"
    assert max5.source_url == "https://claude.com/pricing"

    max20 = by_name["Max 20x"].price
    assert max20.display == "$200"
    assert max20.amount == 200
    assert max20.currency == "USD"
    assert max20.period == "month"
    assert max20.as_of == "2026-08-21"
    assert max20.source_url == (
        "https://support.anthropic.com/en/articles/11049741-what-is-the-max-plan"
    )
    assert max20.note == "定价页只写 From $100"
    assert "未见单独报价" not in (max20.note or "")
    assert "10x" not in by_name["Max 20x"].name


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
    assert "From $100" not in names


def test_openai_go_is_official_eight_dollars() -> None:
    go = next(plan for plan in assemble(ROOT).page("openai").snapshot.plans if plan.name == "Go")
    assert go.price.display == "$8"
    assert go.price.amount == 8
    assert go.price.currency == "USD"
    assert go.price.period == "month"
    assert go.price.source_url == "https://chatgpt.com/pricing/"
    assert go.price.note != "官方有这一档，未见单独报价"
    assert "未见单独报价" not in (go.price.note or "")


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
