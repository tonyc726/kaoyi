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
    amount_parts,
    chart_caption,
    chart_rows,
    format_approx_cny,
    monthly_cny,
    render_price_chart_svg,
    scale_max,
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


def _site(pages: list[VendorPage], rate: float = 6.8) -> SiteData:
    return SiteData(
        config=SiteConfig(
            site_name="考异",
            site_name_en="kaoyi",
            one_liner="x",
            site_base="/kaoyi/",
            pages_url="https://example.test",
            usd_to_cny_rate=rate,
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


def _rects(svg: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for match in re.finditer(r'<rect class="price-bar"([^>]*)/?>', svg):
        found.append(dict(re.findall(r'([\w-]+)="([^"]*)"', match.group(1))))
    return found


def _bar_width(svg: str, vendor_id: str, plan_id: str) -> float:
    for rect in _rects(svg):
        if rect.get("data-vendor-id") == vendor_id and rect.get("data-plan-id") == plan_id:
            return float(rect["width"])
    raise AssertionError(f"missing bar {vendor_id}/{plan_id}")


def test_one_shared_cny_scale() -> None:
    site = _site(
        [
            _page(_vendor("cn", "人民币店"), [_plan("full", "Full", "¥100", 100, "CNY")]),
            _page(_vendor("us", "美元店"), [_plan("ten", "Ten", "$10", 10, "USD")]),
        ]
    )
    rows = chart_rows(site)
    assert scale_max(rows) == 100
    svg = render_price_chart_svg(site)
    assert svg.count("<svg") == 1
    assert 'data-scale-max="100"' in svg
    assert "price-chart-panel" not in svg
    assert _bar_width(svg, "cn", "full") == BAR_MAX
    assert abs(_bar_width(svg, "us", "ten") - BAR_MAX * 68 / 100) < 0.02
    assert format_approx_cny(monthly_cny(10, "USD", 6.8)) == "≈ ¥68"


def test_usd_conversion_uses_config_rate() -> None:
    pages = [
        _page(_vendor("cn", "人民币店"), [_plan("full", "Full", "¥50", 50, "CNY")]),
        _page(_vendor("us", "美元店"), [_plan("twenty", "Twenty", "$20", 20, "USD")]),
    ]
    slow = _site(pages, rate=5.0)
    fast = _site(pages, rate=10.0)
    assert monthly_cny(20, "USD", 5.0) == 100
    assert monthly_cny(20, "USD", 10.0) == 200
    assert scale_max(chart_rows(slow)) == 100
    assert scale_max(chart_rows(fast)) == 200
    slow_svg = render_price_chart_svg(slow)
    fast_svg = render_price_chart_svg(fast)
    assert 'data-rate="5"' in slow_svg
    assert "美元按 5 换算，不是牌价" in slow_svg
    assert "≈ ¥100" in slow_svg
    assert _bar_width(slow_svg, "us", "twenty") == BAR_MAX
    assert _bar_width(slow_svg, "cn", "full") == BAR_MAX * (50 / 100)
    assert "≈ ¥200" in fast_svg
    assert _bar_width(fast_svg, "cn", "full") == BAR_MAX * (50 / 200)
    assert chart_caption(6.8) == "约合 ¥/月 · 美元按 6.8 换算，不是牌价"


def test_missing_custom_and_zeros_are_omitted() -> None:
    site = _site(
        [
            _page(
                _vendor("mix", "混合"),
                [
                    _plan("ok", "Ok", "¥80", 80, "CNY"),
                    _plan("free", "Free", "$0", 0, "USD"),
                    _plan("hobby", "Hobby", "$0", 0, "USD"),
                    _plan("dash", "Dash", "-", None, "CNY"),
                    _plan("custom", "Custom", "Custom", None, None, period=None),
                    _plan("noccy", "NoCcy", "99", 99, None),
                    _plan("none", "NoneAmt", "¥1", None, "CNY"),
                ],
            )
        ]
    )
    svg = render_price_chart_svg(site)
    assert [row.plan_id for row in chart_rows(site)] == ["ok"]
    assert "混合  Ok" in svg
    assert "¥80" in svg
    assert "Free" not in svg
    assert "Hobby" not in svg
    assert "$0" not in svg
    assert "Dash" not in svg
    assert "Custom" not in svg
    assert "NoCcy" not in svg
    assert "NoneAmt" not in svg
    assert "price-tick" not in svg


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
    site = _site(
        [
            _page(
                _vendor("first", "先"),
                [
                    _plan("high", "High", "¥900", 900, "CNY"),
                    _plan("low", "Low", "¥10", 10, "CNY"),
                ],
            ),
            _page(
                _vendor("second", "后"),
                [
                    _plan("mid", "Mid", "¥50", 50, "CNY"),
                    _plan("zero", "Zero", "¥0", 0, "CNY"),
                    _plan("gap", "Gap", "-", None, "CNY"),
                    _plan("usd", "Seat", "$40", 40, "USD", period="user-month"),
                ],
            ),
        ]
    )
    ids = [(row.vendor_id, row.plan_id) for row in chart_rows(site)]
    assert ids == [("first", "high"), ("first", "low"), ("second", "mid"), ("second", "usd")]
    svg = render_price_chart_svg(site)
    order = re.findall(
        r'class="price-chart-name" data-vendor-id="([^"]+)" data-plan-id="([^"]+)"',
        svg,
    )
    assert order == [("first", "high"), ("first", "low"), ("second", "mid"), ("second", "usd")]
    assert "Zero" not in svg
    assert "Gap" not in svg
    primary, secondary = amount_parts(chart_rows(site)[-1])
    assert primary == "≈ ¥272 按席"
    assert secondary == "$40"
    assert "≈ ¥272 按席" in svg
    assert "$40" in svg
    assert "SRC OFFICIAL" not in svg


def test_official_snapshots_share_converted_scale() -> None:
    site = assemble(Path(__file__).resolve().parents[1])
    rate = site.config.usd_to_cny_rate
    assert rate == 6.8
    rows = chart_rows(site)
    assert scale_max(rows) == monthly_cny(200, "USD", rate)
    svg = render_price_chart_svg(site)
    peak = 200 * rate
    assert abs(_bar_width(svg, "openai", "pro-200") - BAR_MAX) < 0.02
    assert abs(_bar_width(svg, "zhipu", "max") - BAR_MAX * (1078 / peak)) < 0.02
    assert abs(_bar_width(svg, "cursor", "pro") - BAR_MAX * (20 * rate / peak)) < 0.02
    assert "约合 ¥/月 · 美元按 6.8 换算，不是牌价" in svg
    assert "≈ ¥136" in svg
    assert "$20" in svg
    assert "字节·方舟" not in svg
    assert "Hobby" not in svg
    assert "Max 20x" not in svg
    assert "Pro+" not in svg
    assert "Go" not in svg
    assert "Custom" not in svg
    assert "price-chart-panel" not in svg
    ids = [(row.vendor_id, row.plan_id) for row in rows]
    assert ids == [
        ("zhipu", "lite"),
        ("zhipu", "pro"),
        ("zhipu", "max"),
        ("minimax", "plus"),
        ("minimax", "max"),
        ("minimax", "ultra"),
        ("aliyun", "pro"),
        ("cursor", "pro"),
        ("cursor", "teams"),
        ("claude", "pro"),
        ("claude", "max-5x"),
        ("grok", "supergrok"),
        ("grok", "plus"),
        ("openai", "plus"),
        ("openai", "pro-100"),
        ("openai", "pro-200"),
    ]
