from __future__ import annotations

from adapters.claude import (
    HELP_MAX_URL,
    SOURCE_URL,
    fetch,
    parse_help_monthly_usd,
)

PRICING_HTML = (
    "<html>$20 billed monthly From $100 Max 5x Max 20x Individual membership</html>"
)
HELP_WITH_20X = """
Max 5x: $100 per month
Max 20x: $200 per month
"""


def test_parse_help_reads_printed_usd_month() -> None:
    assert parse_help_monthly_usd(HELP_WITH_20X, "Max 5x") == 100
    assert parse_help_monthly_usd(HELP_WITH_20X, "Max 20x") == 200
    table = "Max 5x $100 monthly Max 20x $200 monthly"
    assert parse_help_monthly_usd(table, "Max 20x") == 200


def test_parse_help_does_not_infer_20x_from_5x() -> None:
    html = """
    Max 5x: $100 per month
    Max 20x provides 20 times more usage than the Pro plan.
    """
    assert parse_help_monthly_usd(html, "Max 5x") == 100
    assert parse_help_monthly_usd(html, "Max 20x") is None
    twice = "Max 20x is twice Max 5x $100 per month"
    assert parse_help_monthly_usd(twice, "Max 20x") is None


def test_claude_adapter_parses_max20_from_help(monkeypatch) -> None:
    def fake_get_html(url: str) -> tuple[bool, str]:
        if url == SOURCE_URL:
            return True, PRICING_HTML
        if url == HELP_MAX_URL:
            return True, HELP_WITH_20X
        return False, ""

    monkeypatch.setattr("adapters.claude.get_html", fake_get_html)
    snapshot = fetch()
    by_name = {plan.name: plan for plan in snapshot.plans}
    assert [plan.name for plan in snapshot.plans] == ["Free", "Pro", "Max 5x", "Max 20x"]
    assert by_name["Max 5x"].price.display == "From $100"
    assert by_name["Max 5x"].price.amount == 100
    assert by_name["Max 5x"].price.source_url == SOURCE_URL
    assert by_name["Max 20x"].price.display == "$200"
    assert by_name["Max 20x"].price.amount == 200
    assert by_name["Max 20x"].price.currency == "USD"
    assert by_name["Max 20x"].price.period == "month"
    assert by_name["Max 20x"].price.source_url == HELP_MAX_URL
    assert by_name["Max 20x"].price.note == "定价页只写 From $100"
    assert snapshot.parse_ok is True


def test_claude_adapter_missing_help_price_stays_dash(monkeypatch) -> None:
    def fake_get_html(url: str) -> tuple[bool, str]:
        if url == SOURCE_URL:
            return True, PRICING_HTML
        if url == HELP_MAX_URL:
            return True, "Max 5x: $100 per month Max 20x provides 20 times more usage"
        return False, ""

    monkeypatch.setattr("adapters.claude.get_html", fake_get_html)
    snapshot = fetch()
    max20 = next(plan for plan in snapshot.plans if plan.name == "Max 20x")
    assert max20.price.display == "-"
    assert max20.price.amount is None
    assert max20.price.amount != 200
    assert max20.price.source_url == HELP_MAX_URL
    assert snapshot.parse_ok is False


def test_claude_adapter_blocked_help_fetch_stays_dash(monkeypatch) -> None:
    def fake_get_html(url: str) -> tuple[bool, str]:
        if url == SOURCE_URL:
            return True, PRICING_HTML
        return False, ""

    monkeypatch.setattr("adapters.claude.get_html", fake_get_html)
    snapshot = fetch()
    max20 = next(plan for plan in snapshot.plans if plan.name == "Max 20x")
    assert max20.price.display == "-"
    assert max20.price.amount is None
    assert snapshot.parse_ok is False
