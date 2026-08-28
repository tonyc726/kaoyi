from __future__ import annotations

from kaoyi.models import RadarAxis, Review
from kaoyi.radar import invert_for_display, render_radar_svg


def test_switching_cost_inverts_before_draw() -> None:
    axis = RadarAxis(id="switching_cost", label="切换成本", invert=True)
    assert invert_for_display(axis, 1) == 5
    assert invert_for_display(axis, 5) == 1
    assert invert_for_display(axis, 3) == 3


def _axes() -> list[RadarAxis]:
    return [
        RadarAxis(id="availability", label="可获得性"),
        RadarAxis(id="price_structure", label="价格结构"),
        RadarAxis(id="usage_economy", label="用量经济"),
        RadarAxis(id="capability", label="能力覆盖"),
        RadarAxis(id="stability", label="稳定性"),
        RadarAxis(id="payment_region", label="支付与区域"),
        RadarAxis(id="billing_transparency", label="计费透明度"),
        RadarAxis(id="switching_cost", label="切换成本", invert=True),
    ]


def test_placeholder_radar_has_no_filled_shape() -> None:
    svg = render_radar_svg(Review(status="未评", scores={}), _axes())
    assert "radar-shape" not in svg
    assert "未评" in svg
    assert svg.count("radar-spoke") == 8


def test_partial_radar_skips_missing_axes() -> None:
    review = Review(
        status="已评",
        updated_at="2026-08-24",
        scores={
            "availability": 2,
            "price_structure": 1,
            "payment_region": 4,
            "billing_transparency": 1,
        },
        reasons={
            "availability": "LIMITED 且目录价「-」。",
            "price_structure": "活动页有档名无单独报价。",
            "payment_region": "国内人民币活动页。",
            "billing_transparency": "活动页未能解析刊例。",
        },
    )
    svg = render_radar_svg(review, _axes())
    assert "radar-shape" in svg
    assert "radar-dot" in svg
    assert "2.0 / 5" in svg
    assert "无总分" not in svg
    assert svg.count("radar-dot") == 4
    assert review.scores.get("usage_economy") is None
    assert review.scores.get("capability") is None
    assert review.scores.get("stability") is None
    assert review.scores.get("switching_cost") is None
