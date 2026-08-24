from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from kaoyi.load import assemble

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

VOLCENGINE_OMITTED = (
    "usage_economy",
    "capability",
    "stability",
    "switching_cost",
)


def test_reviews_are_no_longer_all_pending() -> None:
    site = assemble(ROOT)
    assert site.reviews.axes == AXES
    scored = [page for page in site.pages if page.review.scores]
    assert len(scored) == len(site.pages)
    assert all(page.review.status != "未评" for page in scored)
    assert all(page.review.status == "已评" for page in scored)
    assert all(page.review.updated_at == "2026-08-24" for page in scored)
    assert all(not page.review.is_placeholder for page in scored)
    for page in scored:
        for axis, score in page.review.scores.items():
            assert axis in AXES
            assert isinstance(score, int)
            assert 1 <= score <= 5
            assert page.review.reasons.get(axis)
        assert "stability" not in page.review.scores


def test_volcengine_omitted_axes_stay_empty() -> None:
    site = assemble(ROOT)
    review = site.page("volcengine").review
    assert review.status == "已评"
    assert review.scores == {
        "availability": 2,
        "price_structure": 1,
        "payment_region": 4,
        "billing_transparency": 1,
    }
    for axis in VOLCENGINE_OMITTED:
        assert axis not in review.scores
        assert review.scores.get(axis) is None
        assert axis not in review.reasons
    assert 3 not in review.scores.values()


def test_openrouter_note_says_not_first_party() -> None:
    site = assemble(ROOT)
    review = site.page("openrouter").review
    assert review.scores["switching_cost"] == 5
    assert "不是官方直营" in review.note


def test_vendor_pages_list_scores_and_keep_missing_axes_pending() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    zhipu = (ROOT / "dist" / "vendors" / "zhipu" / "index.html").read_text(encoding="utf-8")
    assert "已评" in zhipu
    assert "官方落地页状态 OPEN，现时可买。" in zhipu
    assert "SRC EDITORIAL · AS OF 2026-08-24" in zhipu
    assert "radar-shape" in zhipu
    assert "编辑维度 · 无总分" in zhipu

    volc = (ROOT / "dist" / "vendors" / "volcengine" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "已评" in volc
    assert "活动页未能解析刊例。" in volc
    assert volc.count(">未评<") == 4

    openrouter = (ROOT / "dist" / "vendors" / "openrouter" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "不是官方直营" in openrouter
    assert "一 Key 多家，迁出容易。" in openrouter
