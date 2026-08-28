from __future__ import annotations

from kaoyi.models import OfficialPost, OfficialPostsFile, RadarAxis, Review
from kaoyi.radar import invert_for_display
from kaoyi.scores import (
    cheapness_score,
    composite_score,
    derive_stability,
    merge_review,
)


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


def test_composite_ignores_missing_axes() -> None:
    review = Review(
        status="已评",
        updated_at="2026-08-21",
        scores={"availability": 5, "price_structure": 1, "billing_transparency": 1},
        reasons={
            "availability": "OPEN",
            "price_structure": "all dash",
            "billing_transparency": "no list",
        },
    )
    score = composite_score(review, _axes())
    assert score.scored_n == 3
    assert score.value == 2.3
    assert score.display == "2.3 / 5"
    assert score.scored_label == "已评 3/8"


def test_composite_requires_three_scored_axes() -> None:
    review = Review(
        status="已评",
        updated_at="2026-08-21",
        scores={"availability": 5, "price_structure": 5},
        reasons={"availability": "OPEN", "price_structure": "numeric"},
    )
    score = composite_score(review, _axes())
    assert score.value is None
    assert score.scored_n == 2
    assert score.display == "暂无综合分"


def test_composite_inverts_switching_cost_like_radar() -> None:
    axis = RadarAxis(id="switching_cost", label="切换成本", invert=True)
    assert invert_for_display(axis, 2) == 4
    review = Review(
        status="已评",
        updated_at="2026-08-21",
        scores={"availability": 5, "capability": 3, "switching_cost": 2},
        reasons={
            "availability": "OPEN",
            "capability": "coding plan",
            "switching_cost": "isolated balance",
        },
    )
    score = composite_score(review, _axes())
    assert score.value == 4.0
    assert score.scored_n == 3


def test_stability_unscored_without_official_status_source() -> None:
    posts = OfficialPostsFile(
        vendor_id="zhipu",
        source_url="https://www.zhipuai.cn/zh/news",
        as_of="2026-08-21",
        fetched_ok=True,
        parse_ok=True,
        posts=[
            OfficialPost(
                title="blog only",
                date="2026-08-20",
                source_url="https://www.zhipuai.cn/zh/news/1",
                as_of="2026-08-21",
                source_kind="blog",
            )
        ],
    )
    assert derive_stability("zhipu", {"zhipu": posts}, has_status_source=False) is None


def test_stability_counts_only_ingested_status_posts() -> None:
    file = OfficialPostsFile(
        vendor_id="cursor",
        source_url="https://status.cursor.com/api/v2/incidents.json",
        as_of="2026-08-21",
        fetched_ok=True,
        parse_ok=True,
        posts=[
            OfficialPost(
                title="incident a",
                date="2026-08-20",
                source_url="https://status.cursor.com/incidents/a",
                as_of="2026-08-21",
                source_kind="status",
            ),
            OfficialPost(
                title="incident b",
                date="2026-08-19",
                source_url="https://status.cursor.com/incidents/b",
                as_of="2026-08-21",
                source_kind="status",
            ),
            OfficialPost(
                title="changelog",
                date="2026-08-18",
                source_url="https://cursor.com/changelog/x",
                as_of="2026-08-21",
                source_kind="blog",
            ),
        ],
    )
    zero = OfficialPostsFile(
        vendor_id="claude",
        source_url="https://status.claude.com/api/v2/incidents.json",
        as_of="2026-08-21",
        fetched_ok=True,
        parse_ok=True,
        posts=[],
    )
    scored = derive_stability("cursor", {"cursor": file}, has_status_source=True)
    empty = derive_stability("claude", {"claude": zero}, has_status_source=True)
    assert scored == (3, "官方状态页近90天记录 2 起事故。")
    assert empty == (4, "官方状态页近90天无事故")


def test_merge_keeps_handwritten_capability_and_drops_stale_usage() -> None:
    handwritten = Review(
        status="已评",
        updated_at="2026-08-21",
        scores={
            "usage_economy": 2,
            "capability": 5,
            "switching_cost": 4,
        },
        reasons={
            "usage_economy": "handwritten stale 2",
            "capability": "official Claude Code",
            "switching_cost": "membership portable",
        },
    )
    merged = merge_review(
        handwritten,
        {"availability": 5, "price_structure": 5, "billing_transparency": 4},
        {
            "availability": "官方状态 OPEN。",
            "price_structure": "官方各档均有刊例数字。",
            "billing_transparency": "刊例含来源与日期，但官方用量为文字或「-」。",
        },
        as_of="2026-08-21",
    )
    assert "usage_economy" not in merged.scores
    assert merged.scores["capability"] == 5
    assert merged.scores["switching_cost"] == 4
    assert merged.scores["availability"] == 5
    assert "stale" not in (merged.reasons.get("usage_economy") or "")


def test_cheapness_scale_is_five_to_two() -> None:
    assert cheapness_score(0, 1) == 5
    assert cheapness_score(0, 2) == 5
    assert cheapness_score(1, 2) == 2
    assert cheapness_score(0, 4) == 5
    assert cheapness_score(3, 4) == 2
