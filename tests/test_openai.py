from __future__ import annotations

from adapters.openai import parse_individual

INDIVIDUAL_WITH_GO_8 = """
<section>
  <h2>Individual</h2>
  <article><h3>Free</h3><p>$0 / month</p></article>
  <article>
    <h3>Go</h3>
    <p>$8 / month</p>
    <p>This plan may include ads</p>
    <a>Get Go</a>
  </article>
  <article><h3>Plus</h3><p>$20 / month</p></article>
  <article>
    <h3>Pro</h3>
    <p>From $100 / month</p>
    <p>5x or 20x more usage</p>
  </article>
</section>
"""

INDIVIDUAL_GO_UNPRICED = """
<section>
  <h2>Individual</h2>
  <article><h3>Free</h3><p>$0 / month</p></article>
  <article>
    <h3>Go</h3>
    <p>This plan may include ads</p>
    <a>Get Go</a>
  </article>
  <article><h3>Plus</h3><p>$20 / month</p></article>
  <article>
    <h3>Pro</h3>
    <p>From $100 / month</p>
    <p>5x or 20x more usage</p>
  </article>
</section>
"""


def test_parse_go_eight_from_individual_page() -> None:
    snapshot = parse_individual(INDIVIDUAL_WITH_GO_8, as_of="2026-08-21")
    assert snapshot is not None
    go = next(plan for plan in snapshot.plans if plan.name == "Go")
    assert go.price.display == "$8"
    assert go.price.amount == 8
    assert go.price.currency == "USD"
    assert go.price.period == "month"
    assert go.price.source_url == "https://chatgpt.com/pricing/"
    assert go.price.as_of == "2026-08-21"
    assert "未见单独报价" not in (go.price.note or "")


def test_parse_missing_go_price_stays_dash() -> None:
    snapshot = parse_individual(INDIVIDUAL_GO_UNPRICED, as_of="2026-08-21")
    assert snapshot is not None
    go = next(plan for plan in snapshot.plans if plan.name == "Go")
    assert go.price.display == "-"
    assert go.price.amount is None


def test_parse_does_not_rename_pro_or_invent_second_amount() -> None:
    snapshot = parse_individual(INDIVIDUAL_WITH_GO_8, as_of="2026-08-21")
    assert snapshot is not None
    names = [plan.name for plan in snapshot.plans]
    assert names == ["Free", "Go", "Plus", "Pro $100", "Pro $200"]
    assert "From $100" not in names
    plus = next(plan for plan in snapshot.plans if plan.name == "Plus")
    assert plus.price.display == "$20"
    assert plus.price.amount == 20
