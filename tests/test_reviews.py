from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from kaoyi.load import assemble
from kaoyi.official import has_official_status_source

ROOT = Path(__file__).resolve().parents[1]

AXES = [
    "availability",
    "price_structure",
    "usage_economy",
    "capability",
    "stability",
    "payment_region",
    "billing_transparency",
    "switching_cost",
]

VOLCENGINE_UNSCORED = (
    "usage_economy",
    "capability",
    "stability",
    "switching_cost",
)


def test_live_reviews_merge_derived_and_handwritten() -> None:
    site = assemble(ROOT)
    assert site.reviews.axes == AXES
    scored = [page for page in site.pages if page.review.scores]
    assert len(scored) == len(site.pages)
    assert all(page.review.status == "已评" for page in scored)
    assert site.editorial_reviews is not None
    assert all(
        site.editorial_reviews.vendors[page.vendor.id].updated_at == "2026-08-24"
        for page in scored
    )
    for page in scored:
        for axis, score in page.review.scores.items():
            assert axis in AXES
            assert isinstance(score, int)
            assert 1 <= score <= 5
            assert page.review.reasons.get(axis)
        if has_official_status_source(page.vendor.id):
            assert "stability" in page.review.scores
        else:
            assert "stability" not in page.review.scores


def test_volcengine_does_not_invent_missing_axes() -> None:
    site = assemble(ROOT)
    review = site.page("volcengine").review
    assert review.status == "已评"
    assert review.scores["availability"] == 3
    assert review.scores["price_structure"] == 1
    assert review.scores["payment_region"] == 5
    assert review.scores["billing_transparency"] == 1
    for axis in VOLCENGINE_UNSCORED:
        assert axis not in review.scores
        assert review.scores.get(axis) is None
        assert axis not in review.reasons


def test_usage_economy_unscored_without_numeric_quota() -> None:
    site = assemble(ROOT)
    for vendor_id in (
        "minimax",
        "claude",
        "cursor",
        "grok",
        "openai",
        "openrouter",
        "volcengine-agent",
    ):
        assert "usage_economy" not in site.page(vendor_id).review.scores
    assert "usage_economy" in site.page("zhipu").review.scores
    assert "usage_economy" in site.page("aliyun").review.scores


def test_handwritten_capability_and_switching_survive() -> None:
    site = assemble(ROOT)
    zhipu = site.page("zhipu").review
    assert zhipu.scores["capability"] == 3
    assert zhipu.scores["switching_cost"] == 2
    assert zhipu.reasons["capability"] == "官方限定为编码套餐、规定工具内使用。"
    openrouter = site.page("openrouter").review
    assert openrouter.scores["switching_cost"] == 5
    assert "不是官方直营" in openrouter.note


def test_vendor_pages_list_composite_and_keep_missing_axes_pending() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    zhipu = (ROOT / "dist" / "vendors" / "zhipu" / "index.html").read_text(encoding="utf-8")
    assert "已评 7/8" in zhipu
    assert "官方状态 OPEN。" in zhipu
    assert "SRC EDITORIAL · AS OF 2026-08-24" in zhipu
    assert "SRC DERIVED · AS OF" in zhipu
    assert "radar-shape" in zhipu
    assert "无总分" not in zhipu
    assert "暂无综合分" not in zhipu

    volc = (ROOT / "dist" / "vendors" / "volcengine" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "已评 4/8" in volc
    assert "官方各档刊例均为「-」。" in volc
    assert volc.count(">未评<") == 4

    openrouter = (ROOT / "dist" / "vendors" / "openrouter" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "不是官方直营" in openrouter
    assert "一 Key 多家，迁出容易。" in openrouter
