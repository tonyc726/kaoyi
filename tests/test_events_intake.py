from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from kaoyi.load import assemble
from kaoyi.models import Event

ROOT = Path(__file__).resolve().parents[1]


def _event(**overrides: object) -> Event:
    payload: dict[str, object] = {
        "id": "fixture",
        "vendor_id": "zhipu",
        "layer": "community",
        "kind": "anecdote",
        "title": "fixture",
        "summary": "fixture",
        "as_of": "2026-08-21",
    }
    payload.update(overrides)
    return Event.model_validate(payload)


def test_example_and_low_confidence_are_unconfirmed() -> None:
    example = _event(example=True, kind="example", layer="community")
    assert example.effective_confidence < 0.6
    assert example.is_unconfirmed

    low = _event(example=False, confidence=0.4, layer="community", kind="anecdote")
    assert low.is_unconfirmed

    omitted_community = _event(example=False, layer="community", kind="anecdote")
    assert omitted_community.effective_confidence == 0.3
    assert omitted_community.is_unconfirmed


def test_official_promo_and_price_change_default_confirmed() -> None:
    promo = _event(
        vendor_id="aliyun",
        layer="official",
        kind="promo",
        example=False,
        title="官方活动",
    )
    assert promo.effective_confidence >= 0.6
    assert promo.is_unconfirmed is False

    price_change = _event(
        vendor_id="aliyun",
        layer="official",
        kind="price_change",
        example=False,
        title="目录价变动",
    )
    assert price_change.effective_confidence >= 0.6
    assert price_change.is_unconfirmed is False


def test_built_events_page_marks_example_unconfirmed() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    html = (ROOT / "dist" / "events" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "dist" / "assets" / "css" / "site.css").read_text(encoding="utf-8")
    js = (ROOT / "dist" / "assets" / "js" / "binary-field.js").read_text(encoding="utf-8")
    about = (ROOT / "dist" / "about" / "index.html").read_text(encoding="utf-8")
    index = (ROOT / "dist" / "index.html").read_text(encoding="utf-8")

    assert 'id="binary-field"' in index
    assert 'class="binary-field"' in index
    assert "/kaoyi/assets/js/binary-field.js" in index
    assert "prefers-reduced-motion" in js
    assert "pointer-events: none" in css
    assert "rgba(255,255,255," in js
    assert "#00" not in js.lower() and "green" not in js.lower()

    assert "升格" in about
    assert "单帖" in about
    assert "48 小时" in about
    assert "未确认" in about

    example_event = next(event for event in assemble(ROOT).events if event.example)
    assert example_event.vendor_id == "zhipu"
    assert example_event.is_unconfirmed
    assert "EXAMPLE" in html
    assert "未确认" in html
    assert 'class="event-unconfirmed"' in html
    assert "【示例】社区反馈某档位短暂售罄" in html

    example_idx = html.index("【示例】社区反馈某档位短暂售罄")
    row_start = html.rfind("<tr", 0, example_idx)
    row_html = html[row_start:example_idx]
    assert "event-unconfirmed" in row_html
    assert "EXAMPLE" in row_html
    assert "未确认" in row_html

    promo_titles = (
        "百炼 Coding Plan Pro 新客首月特惠",
        "方舟 Agent Plan Small / Medium 限时 2.5 折",
    )
    for title in promo_titles:
        idx = html.index(title)
        start = html.rfind("<tr", 0, idx)
        row = html[start:idx]
        assert "event-unconfirmed" not in row
        assert "未确认" not in row


def test_issue_templates_ask_for_source_and_forbid_affiliates() -> None:
    folder = ROOT / ".github" / "ISSUE_TEMPLATE"
    names = {
        "new-vendor.yml": "新厂商",
        "price-correction.yml": "价格或规则纠错",
        "measured.yml": "带方法的实测",
    }
    for filename, title in names.items():
        text = (folder / filename).read_text(encoding="utf-8")
        assert title in text
        assert "官方或公开来源 URL" in text
        assert "厂商 id" in text
        assert "SKU" in text
        assert "affiliate" in text.lower()
        assert "没有公开来源，我不会要求改价" in text
