from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from kaoyi.load import assemble
from kaoyi.models import Event, OfficialPost, OfficialPostsFile
from kaoyi.official import (
    SOURCES,
    OfficialSource,
    fetch_vendor_posts,
    keep_recent_official_posts,
    load_official_posts_dir,
    merge_posts,
    official_posts_as_events,
    parse_source,
    run_official_fetch,
    stamp_source_kind,
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
    assert "官方博客、Releases、状态页与论坛公告见" in index
    assert 'href="/kaoyi/events/"' in index

    assert "<h2>官方动态</h2>" in cursor_page
    assert "<h2>官方动态</h2>" in zhipu_page
    assert "来自官方博客、Releases、状态页或论坛公告，只列近 90 天。不是目录价。" in cursor_page
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


def test_release_and_status_fixtures_become_official_events() -> None:
    release_posts = stamp_source_kind(
        parse_source(
            "rss",
            _read("official_github_releases.atom"),
            "https://github.com/anthropics/claude-code/releases.atom",
            "2026-08-21",
        ),
        OfficialSource(
            "https://github.com/anthropics/claude-code/releases.atom",
            "rss",
            "releases",
        ),
    )
    assert [post.date for post in release_posts] == ["2026-08-20", "2026-02-02"]
    assert release_posts[0].source_url.endswith("/v2.1.241")
    assert release_posts[0].source_kind == "releases"
    assert release_posts[0].source_label == "RELEASES"
    assert release_posts[0].title == "claude-code v2.1.241"

    status_posts = parse_source(
        "statuspage_incidents",
        _read("official_statuspage_incidents.json"),
        "https://status.cursor.com/api/v2/incidents.json",
        "2026-08-21",
    )
    assert status_posts[0].title == "Investigating service degradation"
    assert status_posts[0].date == "2026-08-21"
    assert status_posts[0].source_url == "https://status.cursor.com/incidents/68krhwzd0r1m"
    assert status_posts[0].source_kind == "status"
    assert status_posts[0].source_label == "STATUS"

    snapshot = OfficialPostsFile(
        vendor_id="claude",
        source_url="https://github.com/anthropics/claude-code/releases.atom",
        as_of="2026-08-21",
        fetched_ok=True,
        parse_ok=True,
        posts=[release_posts[0], status_posts[0]],
    )
    events = official_posts_as_events({"claude": snapshot}, as_of="2026-08-21")
    assert len(events) == 2
    by_kind = {event.kind: event for event in events}
    assert by_kind["official_announce"].layer == "official"
    assert by_kind["official_announce"].source_label == "RELEASES"
    assert by_kind["official_announce"].source_url.endswith("/v2.1.241")
    assert by_kind["status"].layer == "official"
    assert by_kind["status"].kind == "status"
    assert by_kind["status"].source_label == "STATUS"
    assert by_kind["status"].source_url.endswith("/68krhwzd0r1m")
    assert by_kind["status"].effective_confidence == 0.9
    assert by_kind["status"].is_unconfirmed is False


def test_two_hundred_day_old_item_is_dropped() -> None:
    parsed = parse_source(
        "rss",
        _read("official_rss_mixed_age.xml"),
        "https://cursor.com/changelog/rss.xml",
        "2026-08-21",
    )
    assert [post.date for post in parsed] == [
        "2026-08-19",
        "2026-02-02",
        "2025-10-15",
        "2024-11-28",
    ]
    kept = keep_recent_official_posts(parsed, "2026-08-21")
    assert [post.date for post in kept] == ["2026-08-19"]
    assert kept[0].title == "Cloud Agents and Cursor Harness Improvements"
    assert all(post.date >= "2026-05-23" for post in kept)

    snapshot = fetch_vendor_posts(
        "cursor",
        [OfficialSource("https://cursor.com/changelog/rss.xml", "rss")],
        lambda _url: (True, _read("official_rss_mixed_age.xml")),
        "2026-08-21",
    )
    assert snapshot.parse_ok is True
    assert [post.date for post in snapshot.posts] == ["2026-08-19"]
    assert "2026-02-02" not in {post.date for post in snapshot.posts}
    assert "2025-10-15" not in {post.date for post in snapshot.posts}
    assert "2024-11-28" not in {post.date for post in snapshot.posts}


def test_discourse_announcements_skip_release_discussions() -> None:
    posts = parse_source(
        "discourse_announcements",
        _read("official_discourse_announcements.rss"),
        "https://forum.cursor.com/c/announcements/11.rss",
        "2026-08-21",
    )
    assert [post.title for post in posts] == [
        "Grok 4.6 is now Live!",
        "Old announcement from 2025",
    ]
    assert all(post.source_kind == "forum" for post in posts)
    kept = keep_recent_official_posts(posts, "2026-08-21")
    assert [post.title for post in kept] == ["Grok 4.6 is now Live!"]
    assert kept[0].source_label == "FORUM"


def test_merge_does_not_let_status_drown_other_kinds() -> None:
    status = [
        OfficialPost(
            title=f"s{idx}",
            date=f"2026-08-{20 + idx:02d}",
            source_url=f"https://status.example/{idx}",
            as_of="2026-08-24",
            source_kind="status",
        )
        for idx in range(5)
    ]
    blog = [
        OfficialPost(
            title="blog",
            date="2026-08-19",
            source_url="https://example.com/blog/a",
            as_of="2026-08-24",
            source_kind="blog",
        )
    ]
    forum = [
        OfficialPost(
            title="forum",
            date="2026-08-12",
            source_url="https://forum.example/t/1",
            as_of="2026-08-24",
            source_kind="forum",
        )
    ]
    merged = merge_posts([status, blog, forum])
    kinds = {post.source_kind for post in merged}
    assert kinds == {"status", "blog", "forum"}
    assert sum(1 for post in merged if post.source_kind == "status") <= 3


def test_volcengine_company_news_is_not_shared() -> None:
    volc = {source.url for source in SOURCES.get("volcengine", [])}
    agent = {source.url for source in SOURCES.get("volcengine-agent", [])}
    company = "https://www.volcengine.com/news"
    assert company not in volc
    assert company not in agent
    assert not (volc & agent)


def test_existing_snapshot_file_is_filtered_on_load(tmp_path: Path) -> None:
    folder = tmp_path / "data" / "official-posts"
    folder.mkdir(parents=True)
    stale = OfficialPostsFile(
        vendor_id="zhipu",
        source_url="https://www.zhipuai.cn/zh/news",
        as_of="2026-08-21",
        fetched_ok=True,
        parse_ok=True,
        posts=[
            OfficialPost(
                title="old 2025",
                date="2025-08-25",
                source_url="https://www.zhipuai.cn/zh/news/97",
                as_of="2026-08-21",
            ),
            OfficialPost(
                title="old 2024",
                date="2024-11-28",
                source_url="https://www.zhipuai.cn/zh/news/68",
                as_of="2026-08-21",
            ),
            OfficialPost(
                title="recent",
                date="2026-08-01",
                source_url="https://www.zhipuai.cn/zh/news/200",
                as_of="2026-08-21",
            ),
        ],
    )
    (folder / "zhipu.json").write_text(
        json.dumps(stale.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    loaded = load_official_posts_dir(tmp_path, as_of="2026-08-21")
    assert [post.title for post in loaded["zhipu"].posts] == ["recent"]
    events = official_posts_as_events(loaded, as_of="2026-08-21")
    assert [event.title for event in events] == ["recent"]


def test_assemble_drops_stale_official_snapshot_rows() -> None:
    site = assemble(ROOT)
    zhipu_dates = {post.date for post in site.page("zhipu").official_posts}
    assert "2025-08-25" not in zhipu_dates
    assert "2024-12-30" not in zhipu_dates
    assert "2024-11-28" not in zhipu_dates
    volc_titles = {post.title for post in site.page("volcengine").official_posts}
    agent_titles = {post.title for post in site.page("volcengine-agent").official_posts}
    assert not volc_titles.intersection(agent_titles) or not volc_titles
    stale_title = "豆包大模型1.6升级：国内首个原生支持“分档调节思考长度”的大模型"
    assert stale_title not in volc_titles
    assert stale_title not in agent_titles
    announce_dates = {
        event.as_of for event in site.events if event.kind in {"official_announce", "status"}
    }
    assert "2025-10-15" not in announce_dates
    assert "2024-11-28" not in announce_dates
    for post in site.page("cursor").official_posts:
        assert post.date >= "2026-05-23"


def test_official_fetch_does_not_rewrite_snapshot_prices(tmp_path: Path) -> None:
    snap_dir = tmp_path / "data" / "snapshots"
    posts_dir = tmp_path / "data" / "official-posts"
    snap_dir.mkdir(parents=True)
    posts_dir.mkdir(parents=True)
    before = (ROOT / "data" / "snapshots" / "cursor.json").read_text(encoding="utf-8")
    (snap_dir / "cursor.json").write_text(before, encoding="utf-8")
    result = run_official_fetch(
        tmp_path,
        vendor_ids=["cursor"],
        sources={
            "cursor": [
                OfficialSource(
                    "https://status.cursor.com/api/v2/incidents.json",
                    "statuspage_incidents",
                    "status",
                )
            ]
        },
        fetch_fn=lambda _url: (True, _read("official_statuspage_incidents.json")),
        as_of="2026-08-21",
    )
    assert result.written_vendor_ids == ["cursor"]
    assert (snap_dir / "cursor.json").read_text(encoding="utf-8") == before
    written = json.loads((posts_dir / "cursor.json").read_text(encoding="utf-8"))
    assert written["posts"][0]["title"] == "Investigating service degradation"
    assert written["posts"][0]["source_kind"] == "status"
    assert all(item["date"] >= "2026-05-23" for item in written["posts"])


def test_assemble_keeps_catalog_snapshot_prices() -> None:
    site = assemble(ROOT)
    for vendor_id, snapshot in site.snapshots.items():
        raw = json.loads((ROOT / "data" / "snapshots" / f"{vendor_id}.json").read_text())
        assert snapshot.vendor_id == raw["vendor_id"]
        assert [plan.price.display for plan in snapshot.plans] == [
            item["price"]["display"] for item in raw["plans"]
        ]
        assert [plan.price.amount for plan in snapshot.plans] == [
            item["price"]["amount"] for item in raw["plans"]
        ]
        assert [plan.price.source_url for plan in snapshot.plans] == [
            item["price"]["source_url"] for item in raw["plans"]
        ]
        if snapshot.usage is not None and raw.get("usage"):
            assert snapshot.usage.token_list_price == raw["usage"]["token_list_price"]
            assert snapshot.usage.source_url == raw["usage"]["source_url"]


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
