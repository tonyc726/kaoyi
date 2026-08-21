from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_build_writes_pages_under_kaoyi_base(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    dest = ROOT / "dist"
    if dest.exists():
        # build.py owns dist/; just invoke it
        pass
    result = subprocess.run(
        [sys.executable, "scripts/build.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    index = dest / "index.html"
    css = dest / "assets" / "css" / "site.css"
    assert index.exists()
    assert css.exists()
    html = index.read_text(encoding="utf-8")
    assert "/kaoyi/assets/css/site.css" in html
    assert "考异" in html
    assert "对照各家官方套餐，再决定买哪一档。" in html
    assert "一事多源并列" not in html
    assert "一行一个官方 SKU" not in html
    assert "入门 / 主力 / 高用量" not in html
    assert "会员行" not in html
    assert "API 预付" not in html
    assert "OPEN" in html
    for vendor in (
        "zhipu",
        "minimax",
        "volcengine",
        "aliyun",
        "cursor",
        "claude",
        "grok",
        "openai",
        "openrouter",
    ):
        assert (dest / "vendors" / vendor / "index.html").exists()
    assert (dest / "usage" / "index.html").exists()
    assert (dest / "events" / "index.html").exists()
    assert (dest / "about" / "index.html").exists()
    assert not (dest / "CNAME").exists()
    assert not (ROOT / "CNAME").exists()
    assert not (ROOT / "affiliates.yml").exists()
    assert "dreamfree" not in html.lower()
    assert "/go/" not in html
    assert "入门档" not in html
    assert "主力档" not in html
    assert "高用量档" not in html
    assert "Max 5x" in html
    assert "Max 20x" in html
    assert "Max 10x" not in html
    assert "price-chart" in html
    assert "plan-ladders" not in html
    assert "ladder-chip" not in html
    assert html.index("price-chart") < html.index("table-wrap")
    assert "sku-table" in html
    assert "Lite" in html
    assert "¥118" in html
    chart = html[html.index("price-chart") : html.index("table-wrap")]
    assert "SRC OFFICIAL" not in chart
    assert "年付" not in chart
    assert "约合 ¥/月 · 美元按 6.8 换算，不是牌价" in chart
    assert "≈ ¥" in chart
    assert "≈ ¥136" in chart
    assert "按席" in chart
    assert "$40" in chart
    assert "price-chart-panel" not in chart
    assert "Max 5x" in chart
    assert "Max 20x" not in chart
    assert "方舟" not in chart
    assert "Hobby" not in chart
    assert "Custom" not in chart
    assert "Max 20x" in html
    about = (dest / "about" / "index.html").read_text(encoding="utf-8")
    assert "invert for display" not in about
    assert "uv run python scripts/build.py" not in about
    assert "为什么做这个" in about
    assert "能帮你什么" in about
    assert "买 coding 套餐之前，把官方标价放在一起看。" in about
    assert "<article" in about


def test_volcengine_prices_are_dash() -> None:
    text = (ROOT / "data" / "snapshots" / "volcengine.json").read_text(encoding="utf-8")
    assert '"display": "-"' in text


def test_reviews_are_placeholders() -> None:
    from kaoyi.load import assemble

    site = assemble(ROOT)
    assert all(page.review.is_placeholder for page in site.pages)
    assert all(page.review.status == "未评" for page in site.pages)


def test_openai_is_membership_not_api() -> None:
    from kaoyi.load import assemble

    site = assemble(ROOT)
    openai = site.vendor("openai")
    assert openai.kind == "plan"
    assert "会员" in openai.notes
