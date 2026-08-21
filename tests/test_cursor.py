from __future__ import annotations

from pathlib import Path

from adapters.cursor import parse

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_cursor_json_ld_offers_set_pro_plus_and_ultra() -> None:
    html = (FIXTURES / "cursor_pricing_offers.html").read_text(encoding="utf-8")
    snapshot = parse(html, as_of="2026-08-21")
    plans = {plan.name: plan for plan in snapshot.plans}

    assert snapshot.parse_ok
    assert snapshot.source_url == "https://cursor.com/pricing"
    assert [plan.name for plan in snapshot.plans] == [
        "Hobby",
        "Pro",
        "Pro+",
        "Ultra",
        "Teams",
        "Enterprise",
    ]

    assert plans["Hobby"].price.display == "$0"
    assert plans["Hobby"].price.amount == 0
    assert plans["Pro"].price.display == "$20"
    assert plans["Pro"].price.amount == 20
    assert plans["Pro+"].price.display == "$60"
    assert plans["Pro+"].price.amount == 60
    assert plans["Pro+"].price.currency == "USD"
    assert plans["Pro+"].price.period == "month"
    assert plans["Pro+"].price.note is None
    assert plans["Ultra"].price.display == "$200"
    assert plans["Ultra"].price.amount == 200
    assert plans["Ultra"].price.currency == "USD"
    assert plans["Ultra"].price.period == "month"
    assert plans["Ultra"].price.note is None
    assert plans["Teams"].price.display == "$40"
    assert plans["Teams"].price.amount == 40
    assert plans["Enterprise"].price.display == "Custom"
    assert plans["Enterprise"].price.amount is None


def test_cursor_missing_json_ld_leaves_pro_plus_ultra_dash() -> None:
    html = (FIXTURES / "cursor_pricing_no_ldjson.html").read_text(encoding="utf-8")
    snapshot = parse(html, as_of="2026-08-21")
    plans = {plan.name: plan for plan in snapshot.plans}

    assert snapshot.parse_ok
    assert plans["Pro+"].name == "Pro+"
    assert plans["Pro+"].price.display == "-"
    assert plans["Pro+"].price.amount is None
    assert plans["Ultra"].price.display == "-"
    assert plans["Ultra"].price.amount is None
    assert plans["Enterprise"].price.display == "Custom"


def test_cursor_does_not_infer_ultra_from_pro() -> None:
    html = """<!doctype html><html><head>
    <script type="application/ld+json">
    {"@type":"SoftwareApplication","offers":[
      {"@type":"Offer","name":"Hobby","price":"0","priceCurrency":"USD"},
      {"@type":"Offer","name":"Pro","price":"20","priceCurrency":"USD"},
      {"@type":"Offer","name":"Pro+","price":"60","priceCurrency":"USD"},
      {"@type":"Offer","name":"Teams","price":"40","priceCurrency":"USD"}
    ]}
    </script></head><body>Hobby Pro+ Ultra Teams Enterprise</body></html>
    """
    snapshot = parse(html, as_of="2026-08-21")
    ultra = next(plan for plan in snapshot.plans if plan.name == "Ultra")
    assert ultra.price.display == "-"
    assert ultra.price.amount is None
    assert ultra.price.amount != 200
