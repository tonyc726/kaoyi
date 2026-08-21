from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from kaoyi.load import assemble
from kaoyi.models import Event, OfficialPost, OfficialPostsFile
from kaoyi.official import (
    OfficialSource,
    fetch_vendor_posts,
    official_posts_as_events,
    parse_source,
    run_official_fetch,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_rss_fixture_yields_posts_with_source_url() -> None:
    posts = parse_source(
        "rss",
        _read("official_rss.xml"),
        "https://cursor.com/changelog/rss.xml",
        "2026-08-21",
    )
    assert len(posts) == 3
    assert posts[0].title == "Cloud Agents and Cursor Harness Improvements"
    assert posts[0].source_url == "https://cursor.com/changelog/08-19-26"
    assert posts[0].date == "2026-08-19"
    assert posts[0].as_of == "2026-08-21"
    assert all(post.source_url.startswith("https://cursor.com/") for post in posts)


def test_html_fixture_yields_posts_with_source_url() -> None:
    posts = parse_source(
        "anthropic_news",
        _read("official_anthropic_news.html"),
        "https://www.anthropic.com/news",
        "2026-08-21",
    )
    assert len(posts) == 2
    assert posts[0].title == "How Claude’s text watermark works"
    assert posts[0].source_url == "https://www.anthropic.com/news/claude-text-watermark"
    assert posts[0].date == "2026-08-14"
    assert posts[1].source_url == "https://www.anthropic.com/news/claude-opus-5"


def test_parse_failure_returns_empty() -> None:
    posts = parse_source(
        "anthropic_news",
        _read("official_empty.html"),
        "https://www.anthropic.com/news",
        "2026-08-21",
    )
    assert posts == []
    broken = parse_source("rss", "<not-xml", "https://example.com/rss.xml", "2026-08-21")
    assert broken == []


def test_failed_official_fetch_keeps_last_good(tmp_path: Path) -> None:
    last_good = OfficialPostsFile(
        vendor_id="cursor",
        source_url="https://cursor.com/changelog/rss.xml",
        as_of="2026-08-20",
        fetched_ok=True,
        parse_ok=True,
        posts=[
            OfficialPost(
                title="kept",
                date="2026-08-19",
                source_url="https://cursor.com/changelog/08-19-26",
                as_of="2026-08-20",
            )
        ],
    )
    folder = tmp_path / "data" / "official-posts"
    folder.mkdir(parents=True)
    path = folder / "cursor.json"
    path.write_text(
        json.dumps(last_good.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    before = path.read_text(encoding="utf-8")

    result = run_official_fetch(
        tmp_path,
        vendor_ids=["cursor"],
        sources={"cursor": [OfficialSource("https://cursor.com/changelog/rss.xml", "rss")]},
        fetch_fn=lambda _url: (True, "<html><p>no posts</p></html>"),
        as_of="2026-08-21",
    )

    assert result.retained_vendor_ids == ["cursor"]
    assert result.failed_vendor_ids == ["cursor"]
    assert result.written_vendor_ids == []
    assert path.read_text(encoding="utf-8") == before


def test_official_announce_events_are_official_layer() -> None:
    snapshot = OfficialPostsFile(
        vendor_id="cursor",
        source_url="https://cursor.com/changelog/rss.xml",
        as_of="2026-08-21",
        fetched_ok=True,
        parse_ok=True,
        posts=[
            OfficialPost(
                title="Cloud Agents",
                date="2026-08-19",
                source_url="https://cursor.com/changelog/08-19-26",
                as_of="2026-08-21",
            )
        ],
    )
    events = official_posts_as_events({"cursor": snapshot})
    assert len(events) == 1
    event = events[0]
    assert event.layer == "official"
    assert event.kind == "official_announce"
    assert event.example is False
    assert event.source_url == "https://cursor.com/changelog/08-19-26"
    assert event.confidence == 0.9
    assert event.is_unconfirmed is False


def test_fetch_vendor_posts_empty_when_parse_fails() -> None:
    snapshot = fetch_vendor_posts(
        "cursor",
        [OfficialSource("https://cursor.com/changelog/rss.xml", "rss")],
        lambda _url: (True, "not xml at all"),
        "2026-08-21",
    )
    assert snapshot.parse_ok is False
    assert snapshot.posts == []


def test_vendor_page_has_official_section_and_homepage_is_not_a_wall() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    index = (ROOT / "dist" / "index.html").read_text(encoding="utf-8")
    events_html = (ROOT / "dist" / "events" / "index.html").read_text(encoding="utf-8")
    cursor_page = (ROOT / "dist" / "vendors" / "cursor" / "index.html").read_text(encoding="utf-8")
    zhipu_page = (ROOT / "dist" / "vendors" / "zhipu" / "index.html").read_text(encoding="utf-8")

    hero_end = index.find("套餐对照")
    assert hero_end > 0
    assert "官方动态" not in index[:hero_end]
    assert "官方博客与更新日志见" in index
    assert 'href="/kaoyi/events/"' in index

    assert "<h2>官方动态</h2>" in cursor_page
    assert "<h2>官方动态</h2>" in zhipu_page
    assert "来自官方博客或更新日志。不是目录价。" in cursor_page
    assert "X @cursor_ai" in cursor_page
    assert "https://x.com/cursor_ai" in cursor_page
    assert "https://github.com/cursor" in cursor_page
    claude_page = (ROOT / "dist" / "vendors" / "claude" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "https://x.com/claudeai" in claude_page
    assert "https://x.com/AnthropicAI" in claude_page
    assert "产品号" in claude_page
    assert "https://github.com/anthropics" in claude_page
    assert "https://x.com/Zai_org" in zhipu_page
    assert "@cursor_ai" not in zhipu_page
    minimax_page = (ROOT / "dist" / "vendors" / "minimax" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "https://x.com/MiniMax__AI" in minimax_page
    assert "https://x.com/MiniMax_AI" in minimax_page
    assert "并列不单选" in minimax_page
    volc_page = (ROOT / "dist" / "vendors" / "volcengine" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "x.com/" not in volc_page
    aliyun_page = (ROOT / "dist" / "vendors" / "aliyun" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "alibaba_cloud" in aliyun_page
    assert "阿里云公司号" in aliyun_page
    assert "百炼 X" not in aliyun_page or "没有单独的百炼" in aliyun_page
    openai_page = (ROOT / "dist" / "vendors" / "openai" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "https://x.com/OpenAIDevs" in openai_page
    assert 'href="https://x.com/OpenAI"' not in openai_page
    grok_page = (ROOT / "dist" / "vendors" / "grok" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "https://x.com/grok" in grok_page
    assert "产品号" in grok_page
    assert "@OpenAI" not in index
    assert "@AnthropicAI" not in index
    assert "@xai" not in index
    openrouter_page = (ROOT / "dist" / "vendors" / "openrouter" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "twitter.com/OpenRouterAI" not in openrouter_page
    assert "x.com/OpenRouterAI" not in openrouter_page
    assert "https://x.com/openrouter" in openrouter_page

    site = assemble(ROOT)
    cursor_prices = [plan.price.display for plan in site.page("cursor").snapshot.plans]
    assert "$20" in cursor_prices or any(display.startswith("$") for display in cursor_prices)
    announces = [event for event in site.events if event.kind == "official_announce"]
    for event in announces:
        assert event.layer == "official"
        assert event.example is False
        assert event.source_url
        assert event.is_unconfirmed is False
        assert "EXAMPLE" not in event.title

    if announces:
        title = announces[0].title
        idx = events_html.index(title)
        start = events_html.rfind("<tr", 0, idx)
        row = events_html[start:idx]
        assert "event-unconfirmed" not in row
        assert "EXAMPLE" not in row
        assert "OFFICIAL" in row


def test_official_announce_default_confidence() -> None:
    event = Event(
        id="x",
        vendor_id="cursor",
        layer="official",
        kind="official_announce",
        title="官方更新",
        summary="fixture",
        as_of="2026-08-21",
        source_url="https://cursor.com/changelog/08-19-26",
        example=False,
    )
    assert event.effective_confidence == 0.9
    assert event.is_unconfirmed is False
