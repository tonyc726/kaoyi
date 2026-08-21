from __future__ import annotations

from kaoyi.models import RadarAxis, Review
from kaoyi.radar import invert_for_display, render_radar_svg


def test_switching_cost_inverts_before_draw() -> None:
    axis = RadarAxis(id="switching_cost", label="切换成本", invert=True)
    assert invert_for_display(axis, 1) == 5
    assert invert_for_display(axis, 5) == 1
    assert invert_for_display(axis, 3) == 3


def test_placeholder_radar_has_no_filled_shape() -> None:
    axes = [
        RadarAxis(id="availability", label="可获得性"),
        RadarAxis(id="price_structure", label="价格结构"),
        RadarAxis(id="usage_economy", label="用量经济"),
        RadarAxis(id="capability", label="能力覆盖"),
        RadarAxis(id="stability", label="稳定性"),
        RadarAxis(id="payment_region", label="支付与区域"),
        RadarAxis(id="billing_transparency", label="计费透明度"),
        RadarAxis(id="switching_cost", label="切换成本", invert=True),
    ]
    svg = render_radar_svg(Review(status="未评", scores={}), axes)
    assert "radar-shape" not in svg
    assert "未评" in svg
    assert svg.count("radar-spoke") == 8
