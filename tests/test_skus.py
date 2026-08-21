from __future__ import annotations

from pathlib import Path

from kaoyi.load import assemble

ROOT = Path(__file__).resolve().parents[1]


def test_claude_lists_official_max_skus() -> None:
    page = assemble(ROOT).page("claude")
    names = [plan.name for plan in page.snapshot.plans]
    assert names == ["Free", "Pro", "Max 5x", "Max 20x"]
    max20 = next(plan for plan in page.snapshot.plans if plan.name == "Max 20x")
    assert max20.price.display == "-"
    assert "10x" not in max20.name


def test_cursor_lists_individual_official_names() -> None:
    names = [plan.name for plan in assemble(ROOT).page("cursor").snapshot.plans]
    assert names[:4] == ["Hobby", "Pro", "Pro+", "Ultra"]


def test_openai_pro_uses_help_center_names_not_5x() -> None:
    names = [plan.name for plan in assemble(ROOT).page("openai").snapshot.plans]
    assert "Go" in names
    assert "Plus" in names
    assert "Pro $100" in names
    assert "Pro $200" in names
    assert "Pro 5x" not in names
    assert "Pro 20x" not in names
