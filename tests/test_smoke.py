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
    assert "一事多源并列，写明取舍" in html
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
