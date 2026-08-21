from __future__ import annotations

import re
from pathlib import Path

from kaoyi.load import assemble
from kaoyi.models import (
    Plan,
    PriceCell,
    Review,
    ReviewsFile,
    SiteConfig,
    SiteData,
    Snapshot,
    Vendor,
    VendorPage,
)
from kaoyi.price_chart import (
    BAR_MAX,
    amount_label,
    bar_width,
    groups_for,
    panel_scale_max,
    render_price_chart_svg,
)


def _vendor(vendor_id: str, name: str) -> Vendor:
    return Vendor(
        id=vendor_id,
        name=name,
        name_en=name,
        kind="plan",
        status="OPEN",
        region="CN",
        currency="CNY",
        official_url="https://example.test",
        buy_url="https://example.test",
        docs_url="https://example.test",
        adapter=vendor_id,
        short=name,
    )


def _plan(
    plan_id: str,
    name: str,
    display: str,
    amount: float | None,
    currency: str | None,
    period: str | None = "month",
) -> Plan:
    return Plan(
        id=plan_id,
        name=name,
        price=PriceCell(
            display=display,
            amount=amount,
            currency=currency,
            period=period,
            source_url="https://example.test",
            as_of="2026-01-01",
        ),
    )


def _page(vendor: Vendor, plans: list[Plan]) -> VendorPage:
    return VendorPage(
        vendor=vendor,
        snapshot=Snapshot(
            vendor_id=vendor.id,
            source_url="https://example.test",
            as_of="2026-01-01",
            plans=plans,
        ),
        review=Review(),
        events=[],
        radar_svg="",
    )


def _site(pages: list[VendorPage]) -> SiteData:
    return SiteData(
        config=SiteConfig(
            site_name="考异",
            site_name_en="kaoyi",
            one_liner="x",
            site_base="/kaoyi/",
            pages_url="https://example.test",
            usd_to_cny_rate=6.8,
            usd_to_cny_as_of="2026-01-01",
            usd_to_cny_note="x",
            build_as_of="2026-01-01",
            footer_zh="x",
            footer_en="x",
            layers=[],
            radar_axes=[],
            status_literals=[],
        ),
        vendors=[page.vendor for page in pages],
        snapshots={page.vendor.id: page.snapshot for page in pages},
        reviews=ReviewsFile(axes=[], vendors={}),
        events=[],
        pages=pages,
    )


def _rects(svg: str, cls: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for match in re.finditer(rf'<rect class="{cls}"([^>]*)/?>', svg):
        found.append(dict(re.findall(r'([\w-]+)="([^"]*)"', match.group(1))))
    return found


def _bar_widths(svg: str, currency: str) -> dict[str, float]:
    return {
        rect["data-plan-id"]: float(rect["width"])
        for rect in _rects(svg, "price-bar")
        if rect.get("data-currency") == currency
    }


def _bar_width(svg: str, currency: str, vendor_id: str, plan_id: str) -> float:
    for rect in _rects(svg, "price-bar"):
        if (
            rect.get("data-currency") == currency
            and rect.get("data-vendor-id") == vendor_id
            and rect.get("data-plan-id") == plan_id
        ):
            return float(rect["width"])
    raise AssertionError(f"missing {currency} bar {vendor_id}/{plan_id}")


def test_cny_and_usd_never_share_a_scale() -> None:
    site = _site(
        [
            _page(
                _vendor("cn", "人民币店"),
                [
                    _plan("cheap", "Cheap", "¥50", 50, "CNY"),
                    _plan("full", "Full", "¥100", 100, "CNY"),
                ],
            ),
            _page(
                _vendor("us", "美元店"),
                [_plan("ten", "Ten", "$10", 10, "USD")],
            ),
        ]
    )
    assert panel_scale_max(site, "CNY") == 100
    assert panel_scale_max(site, "USD") == 10
    svg = render_price_chart_svg(site)
    assert 'data-currency="CNY" data-scale-max="100"' in svg
    assert 'data-currency="USD" data-scale-max="10"' in svg
    cny = _bar_widths(svg, "CNY")
    usd = _bar_widths(svg, "USD")
    assert cny["full"] == BAR_MAX
    assert cny["cheap"] == BAR_MAX / 2
    assert usd["ten"] == BAR_MAX
    assert usd["ten"] != cny["cheap"]


def test_missing_custom_and_currencyless_prices_are_omitted() -> None:
    site = _site(
        [
            _page(
                _vendor("mix", "混合"),
                [
                    _plan("ok", "Ok", "¥80", 80, "CNY"),
                    _plan("dash", "Dash", "-", None, "CNY"),
                    _plan("custom", "Custom", "Custom", None, None, period=None),
                    _plan("noccy", "NoCcy", "99", 99, None),
                    _plan("none", "NoneAmt", "¥1", None, "CNY"),
                ],
            )
        ]
    )
    svg = render_price_chart_svg(site)
    assert "Ok" in svg
    assert "¥80" in svg
    assert "Dash" not in svg
    assert "Custom" not in svg
    assert "NoCcy" not in svg
    assert "NoneAmt" not in svg
    assert "data-plan-id=" in svg
    assert groups_for(site, "CNY")[0][1][0].id == "ok"
    assert [plan.id for _, plans in groups_for(site, "CNY") for plan in plans] == ["ok"]


def test_zero_amount_has_no_bar_width() -> None:
    site = _site(
        [
            _page(
                _vendor("us", "美元店"),
                [
                    _plan("free", "Free", "$0", 0, "USD"),
                    _plan("paid", "Paid", "$20", 20, "USD"),
                ],
            )
        ]
    )
    assert bar_width(0, 20) == 0
    svg = render_price_chart_svg(site)
    assert 'class="price-bar"' in svg
    assert re.search(r'class="price-tick"[^>]*data-plan-id="free"', svg)
    assert not re.search(r'class="price-bar"[^>]*data-plan-id="free"', svg)
    assert "$0" in svg
    assert "Free" in svg
    paid = _bar_widths(svg, "USD")
    assert paid["paid"] == BAR_MAX
    assert "free" not in paid


def test_labels_are_xml_escaped() -> None:
    site = _site(
        [
            _page(
                _vendor("x", 'A&B <shop> "q"'),
                [_plan("p", 'Lite <pro> & "max"', "¥1", 1, "CNY")],
            )
        ]
    )
    svg = render_price_chart_svg(site)
    assert "A&amp;B &lt;shop&gt; &quot;q&quot;" in svg
    assert "Lite &lt;pro&gt; &amp; &quot;max&quot;" in svg
    assert "<pro>" not in svg
    assert "A&B" not in svg


def test_vendor_and_sku_order_is_preserved_not_sorted_by_price() -> None:
    first = _vendor("first", "先")
    second = _vendor("second", "后")
    site = _site(
        [
            _page(
                first,
                [
                    _plan("high", "High", "¥900", 900, "CNY"),
                    _plan("low", "Low", "¥10", 10, "CNY"),
                ],
            ),
            _page(
                second,
                [
                    _plan("mid", "Mid", "¥50", 50, "CNY"),
                    _plan("zero", "Zero", "¥0", 0, "CNY"),
                    _plan("gap", "Gap", "-", None, "CNY"),
                ],
            ),
        ]
    )
    svg = render_price_chart_svg(site)
    vendor_ids = re.findall(r'class="price-chart-vendor" data-vendor-id="([^"]+)"', svg)
    assert vendor_ids == ["first", "second"]
    plan_ids = re.findall(r'class="price-chart-name" data-plan-id="([^"]+)"', svg)
    assert plan_ids == ["high", "low", "mid", "zero"]
    assert "Gap" not in svg


def test_user_month_appends_seat_mark() -> None:
    plan = _plan("teams", "Teams", "$40", 40, "USD", period="user-month")
    assert amount_label(plan) == "$40 按席"
    site = _site([_page(_vendor("us", "美元店"), [plan])])
    svg = render_price_chart_svg(site)
    assert "$40 按席" in svg
    assert "SRC OFFICIAL" not in svg
    assert "≈ ¥" not in svg


def test_official_snapshots_split_scales_and_drop_gaps() -> None:
    site = assemble(Path(__file__).resolve().parents[1])
    svg = render_price_chart_svg(site)
    assert panel_scale_max(site, "CNY") == 1078
    assert panel_scale_max(site, "USD") == 200
    assert _bar_width(svg, "CNY", "zhipu", "max") == BAR_MAX
    assert _bar_width(svg, "USD", "openai", "pro-200") == BAR_MAX
    assert abs(_bar_width(svg, "CNY", "aliyun", "pro") - BAR_MAX * (200 / 1078)) < 0.02
    assert _bar_width(svg, "USD", "cursor", "pro") == BAR_MAX * (20 / 200)
    assert "字节·方舟" not in svg
    assert "Max 20x" not in svg
    assert "Pro+" not in svg
    assert "Go" not in svg
    assert "Custom" not in svg
    vendor_ids = re.findall(r'class="price-chart-vendor" data-vendor-id="([^"]+)"', svg)
    assert vendor_ids == [
        "zhipu",
        "minimax",
        "aliyun",
        "cursor",
        "claude",
        "grok",
        "openai",
    ]
