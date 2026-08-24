"""Official publication posts: blogs/changelogs/RSS on vendor domains. Never invent."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

from selectolax.parser import HTMLParser

from adapters.base import get_url, today
from kaoyi.models import Event, OfficialPost, OfficialPostsFile

ACCEPT_DOCUMENT = (
    "text/html,application/xhtml+xml,application/rss+xml,application/xml;q=0.9,text/xml;q=0.8"
)
MAX_POSTS = 5
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

ParseFn = Callable[[str, str, str], list[OfficialPost]]


@dataclass(frozen=True)
class OfficialSource:
    url: str
    parser: str


@dataclass
class OfficialFetchResult:
    as_of: str
    written_vendor_ids: list[str] = field(default_factory=list)
    retained_vendor_ids: list[str] = field(default_factory=list)
    failed_vendor_ids: list[str] = field(default_factory=list)


# Publication URLs verified on official domains (2026-08-21). Not social scrapes.
SOURCES: dict[str, list[OfficialSource]] = {
    "cursor": [
        OfficialSource("https://cursor.com/changelog/rss.xml", "rss"),
        OfficialSource("https://cursor.com/blog", "cursor_blog"),
    ],
    "claude": [OfficialSource("https://www.anthropic.com/news", "anthropic_news")],
    "grok": [OfficialSource("https://x.ai/news", "xai_news")],
    "openai": [
        OfficialSource("https://openai.com/news/rss.xml", "rss"),
        OfficialSource("https://developers.openai.com/rss.xml", "rss"),
    ],
    "openrouter": [OfficialSource("https://openrouter.ai/blog/feed.xml", "rss")],
    "zhipu": [OfficialSource("https://www.zhipuai.cn/zh/news", "zhipu_news")],
    "minimax": [
        OfficialSource("https://www.minimaxi.com/", "minimax_listing"),
        OfficialSource("https://www.minimaxi.com/news", "minimax_listing"),
    ],
    "volcengine": [OfficialSource("https://www.volcengine.com/news", "volcengine_news")],
    "volcengine-agent": [OfficialSource("https://www.volcengine.com/news", "volcengine_news")],
    "aliyun": [OfficialSource("https://www.aliyun.com/product/news/", "aliyun_product_news")],
}


def run_official_fetch(
    root: Path,
    *,
    vendor_ids: list[str] | None = None,
    sources: dict[str, list[OfficialSource]] | None = None,
    fetch_fn: Callable[[str], tuple[bool, str]] | None = None,
    force: bool = False,
    as_of: str | None = None,
) -> OfficialFetchResult:
    """Fetch official publication pages. Parse failure keeps last-good posts."""
    catalog = sources if sources is not None else SOURCES
    selected = list(vendor_ids) if vendor_ids is not None else list(catalog)
    day = as_of or today()
    existing = load_official_posts_dir(root)
    getter = fetch_fn or _fetch_document
    out_dir = root / "data" / "official-posts"
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    retained: list[str] = []
    failed: list[str] = []

    for vendor_id in selected:
        vendor_sources = catalog.get(vendor_id)
        if not vendor_sources:
            continue
        snapshot = fetch_vendor_posts(vendor_id, vendor_sources, getter, day)
        old = existing.get(vendor_id)
        path = out_dir / f"{vendor_id}.json"
        if _should_keep_existing(snapshot, old, force):
            print(f"keep official {vendor_id}: parse miss, existing posts retained")
            retained.append(vendor_id)
            failed.append(vendor_id)
            continue
        path.write_text(
            json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(vendor_id)
        n_posts = len(snapshot.posts)
        print(f"wrote {path.relative_to(root)} parse_ok={snapshot.parse_ok} n={n_posts}")
        if not snapshot.parse_ok:
            failed.append(vendor_id)

    return OfficialFetchResult(
        as_of=day,
        written_vendor_ids=written,
        retained_vendor_ids=retained,
        failed_vendor_ids=failed,
    )


def fetch_vendor_posts(
    vendor_id: str,
    sources: list[OfficialSource],
    getter: Callable[[str], tuple[bool, str]],
    as_of: str,
) -> OfficialPostsFile:
    groups: list[list[OfficialPost]] = []
    fetched_any = False
    primary_url = sources[0].url if sources else ""
    for source in sources:
        fetched, body = getter(source.url)
        if fetched and body.strip():
            fetched_any = True
            groups.append(parse_source(source.parser, body, source.url, as_of))
    posts = merge_posts(groups)
    parse_ok = bool(posts)
    notes_url = primary_url
    return OfficialPostsFile(
        vendor_id=vendor_id,
        source_url=notes_url,
        as_of=as_of,
        fetched_ok=fetched_any,
        parse_ok=parse_ok,
        posts=posts,
    )


def parse_source(parser: str, body: str, source_url: str, as_of: str) -> list[OfficialPost]:
    fn = PARSERS.get(parser)
    if fn is None:
        return []
    try:
        return fn(body, source_url, as_of)
    except (ET.ParseError, json.JSONDecodeError, ValueError, TypeError):
        return []


def parse_rss(body: str, source_url: str, as_of: str) -> list[OfficialPost]:
    root = ET.fromstring(body)
    posts: list[OfficialPost] = []
    seen: set[str] = set()
    for item in root.findall(".//item"):
        title = _child_text(item, "title")
        link = _child_text(item, "link") or _child_attr(item, "link", "href")
        date = normalize_date(_child_text(item, "pubDate") or _child_text(item, "date"))
        post = _post(title, date, link, as_of)
        if post is None or post.source_url in seen:
            continue
        seen.add(post.source_url)
        posts.append(post)
    if posts:
        return posts[:MAX_POSTS]
    atom = "{http://www.w3.org/2005/Atom}"
    for item in root.findall(f".//{atom}entry"):
        title = _child_text(item, f"{atom}title") or _child_text(item, "title")
        link = _child_attr(item, f"{atom}link", "href") or _child_text(item, "link")
        date = normalize_date(
            _child_text(item, f"{atom}published")
            or _child_text(item, f"{atom}updated")
            or _child_text(item, "published")
        )
        post = _post(title, date, link, as_of)
        if post is None or post.source_url in seen:
            continue
        seen.add(post.source_url)
        posts.append(post)
    return posts[:MAX_POSTS]


def parse_cursor_blog(body: str, source_url: str, as_of: str) -> list[OfficialPost]:
    posts: list[OfficialPost] = []
    seen: set[str] = set()
    tree = HTMLParser(body)
    for node in tree.css("a"):
        href = node.attributes.get("href") or ""
        if not _is_cursor_blog_post(href):
            continue
        url = urljoin(source_url, href)
        time_node = node.css_first("time")
        date = ""
        if time_node is not None:
            date = normalize_date(time_node.attributes.get("datetime") or time_node.text() or "")
        title = _clean_cursor_blog_title(_anchor_title(node), date)
        post = _post(title, date, url, as_of)
        if post is None:
            continue
        if post.source_url in seen:
            existing = next(item for item in posts if item.source_url == post.source_url)
            if len(post.title) < len(existing.title):
                posts[posts.index(existing)] = post
            continue
        seen.add(post.source_url)
        posts.append(post)
    return posts[:MAX_POSTS]


def parse_anthropic_news(body: str, source_url: str, as_of: str) -> list[OfficialPost]:
    posts: list[OfficialPost] = []
    seen: set[str] = set()
    tree = HTMLParser(body)
    for node in tree.css("a"):
        href = node.attributes.get("href") or ""
        if not _path_match(href, "/news/"):
            continue
        if href.rstrip("/") in {"/news", "https://www.anthropic.com/news"}:
            continue
        time_node = node.css_first("time")
        if time_node is None:
            continue
        date = normalize_date(time_node.text() or time_node.attributes.get("datetime") or "")
        title = _clean_title(_anchor_title(node, skip_time=True), date)
        title = _strip_leading_category(title)
        post = _post(title, date, urljoin(source_url, href), as_of)
        if post is None:
            continue
        if post.source_url in seen:
            existing = next(item for item in posts if item.source_url == post.source_url)
            if len(post.title) < len(existing.title):
                posts[posts.index(existing)] = post
            continue
        seen.add(post.source_url)
        posts.append(post)
    return posts[:MAX_POSTS]


def parse_xai_news(body: str, source_url: str, as_of: str) -> list[OfficialPost]:
    posts: list[OfficialPost] = []
    seen: set[str] = set()
    tree = HTMLParser(body)
    for node in tree.css("a"):
        href = node.attributes.get("href") or ""
        if not _path_match(href, "/news/"):
            continue
        text = " ".join((node.text() or "").split())
        heading = node.css_first("h2") or node.css_first("h3") or node.css_first("h1")
        heading_text = " ".join((heading.text() or "").split()) if heading is not None else ""
        date = normalize_date(_extract_english_date(text) or "")
        title = _clean_title(heading_text or text, date)
        if title.lower() in {"all posts", "changelog", "news"}:
            continue
        post = _post(title, date, urljoin(source_url, href), as_of)
        if post is None or post.source_url in seen:
            continue
        seen.add(post.source_url)
        posts.append(post)
    return posts[:MAX_POSTS]


def parse_zhipu_news(body: str, source_url: str, as_of: str) -> list[OfficialPost]:
    posts: list[OfficialPost] = []
    seen: set[str] = set()
    tree = HTMLParser(body)
    for node in tree.css("a"):
        href = node.attributes.get("href") or ""
        if not re.search(r"/zh/news/\d+", href):
            continue
        img = node.css_first("img")
        alt = (img.attributes.get("alt") if img is not None else "") or ""
        text = " ".join((node.text() or "").split())
        date = normalize_date(_extract_ymd(alt + text) or "")
        title = alt.strip() or _clean_title(text, date)
        post = _post(title, date, urljoin(source_url, href), as_of)
        if post is None or post.source_url in seen:
            continue
        seen.add(post.source_url)
        posts.append(post)
    return posts[:MAX_POSTS]


def parse_minimax_listing(body: str, source_url: str, as_of: str) -> list[OfficialPost]:
    posts: list[OfficialPost] = []
    seen: set[str] = set()
    tree = HTMLParser(body)
    for node in tree.css("a"):
        href = node.attributes.get("href") or ""
        if not (_path_match(href, "/news/") or _path_match(href, "/blog/")):
            continue
        text = " ".join((node.text() or "").split())
        date = normalize_date(_extract_ymd(text) or "")
        title = _clean_minimax_title(text, date)
        post = _post(title, date, urljoin("https://www.minimaxi.com/", href), as_of)
        if post is None or len(post.title) < 8:
            continue
        key = post.source_url.rstrip("/")
        if key in seen:
            existing = next(item for item in posts if item.source_url.rstrip("/") == key)
            if post.date and not existing.date:
                posts[posts.index(existing)] = post
            elif post.date == existing.date and len(post.title) < len(existing.title):
                posts[posts.index(existing)] = post
            continue
        seen.add(key)
        posts.append(post)
    return posts[:MAX_POSTS]


def parse_volcengine_news(body: str, source_url: str, as_of: str) -> list[OfficialPost]:
    payload = _router_data(body)
    if payload is None:
        return []
    loader = payload.get("loaderData")
    if not isinstance(loader, dict):
        return []
    page = loader.get("__ssr_without_user/news/page")
    if not isinstance(page, dict):
        return []
    articles = page.get("listOnlineArticle")
    rows: list[dict[str, object]] = []
    if isinstance(articles, dict) and isinstance(articles.get("List"), list):
        rows = [row for row in articles["List"] if isinstance(row, dict)]
    posts: list[OfficialPost] = []
    seen: set[str] = set()
    for row in rows:
        title = str(row.get("Title") or "").strip()
        doc_id = row.get("DocumentID")
        if not title or doc_id is None:
            continue
        date = normalize_date(str(row.get("CreatedTime") or ""))
        url = f"https://www.volcengine.com/news/detail/{doc_id}"
        post = _post(title, date, url, as_of)
        if post is None or post.source_url in seen:
            continue
        seen.add(post.source_url)
        posts.append(post)
    if posts:
        return posts[:MAX_POSTS]
    banner = page.get("banner")
    if isinstance(banner, list):
        for row in banner:
            if not isinstance(row, dict):
                continue
            post = _post(
                str(row.get("title") or ""),
                normalize_date(str(row.get("date") or "")),
                str(row.get("link") or ""),
                as_of,
            )
            if post is None or post.source_url in seen:
                continue
            seen.add(post.source_url)
            posts.append(post)
    return posts[:MAX_POSTS]


def parse_aliyun_product_news(body: str, source_url: str, as_of: str) -> list[OfficialPost]:
    posts: list[OfficialPost] = []
    seen: set[str] = set()
    pattern = re.compile(
        r'href="(https://www\.aliyun\.com/product/news/\d+)"[^>]*>\s*'
        r'<p class="desc">([^<]+)</p>.*?'
        r'<b class="clic-text">([^<]+)',
        re.S,
    )
    for match in pattern.finditer(body):
        url, title, date_raw = match.group(1), match.group(2).strip(), match.group(3).strip()
        if "百炼" not in title:
            continue
        date = normalize_date(date_raw)
        post = _post(title, date, url, as_of)
        if post is None or post.source_url in seen:
            continue
        seen.add(post.source_url)
        posts.append(post)
    posts.sort(key=lambda item: item.date, reverse=True)
    return posts[:MAX_POSTS]


PARSERS: dict[str, ParseFn] = {
    "rss": parse_rss,
    "cursor_blog": parse_cursor_blog,
    "anthropic_news": parse_anthropic_news,
    "xai_news": parse_xai_news,
    "zhipu_news": parse_zhipu_news,
    "minimax_listing": parse_minimax_listing,
    "volcengine_news": parse_volcengine_news,
    "aliyun_product_news": parse_aliyun_product_news,
}


def merge_posts(groups: list[list[OfficialPost]]) -> list[OfficialPost]:
    seen: set[str] = set()
    merged: list[OfficialPost] = []
    for group in groups:
        for post in group:
            key = post.source_url.rstrip("/")
            if key in seen:
                for idx, old in enumerate(merged):
                    if old.source_url.rstrip("/") != key:
                        continue
                    if post.date and not old.date:
                        merged[idx] = post
                    elif old.date and not post.date:
                        break
                    elif len(post.title) < len(old.title):
                        merged[idx] = post
                    break
                continue
            seen.add(key)
            merged.append(post)
    merged.sort(key=lambda item: (item.date or "", item.source_url), reverse=True)
    return merged[:MAX_POSTS]


def load_official_posts_dir(root: Path) -> dict[str, OfficialPostsFile]:
    files: dict[str, OfficialPostsFile] = {}
    folder = root / "data" / "official-posts"
    if not folder.exists():
        return files
    for path in sorted(folder.glob("*.json")):
        snapshot = OfficialPostsFile.model_validate_json(path.read_text(encoding="utf-8"))
        files[snapshot.vendor_id] = snapshot
    return files


def official_posts_as_events(
    files: dict[str, OfficialPostsFile],
) -> list[Event]:
    events: list[Event] = []
    for vendor_id, snapshot in files.items():
        if not snapshot.parse_ok:
            continue
        for post in snapshot.posts:
            events.append(
                Event(
                    id=_announce_id(vendor_id, post),
                    vendor_id=vendor_id,
                    layer="official",
                    kind="official_announce",
                    title=post.title,
                    summary="官方发布页上的更新，不是目录价，也不是社区传闻。",
                    as_of=post.date or post.as_of,
                    source_url=post.source_url,
                    example=False,
                    status="OPEN",
                    note="官方层。来自官方博客/更新日志/RSS，不改写套餐标价。",
                    confidence=0.9,
                )
            )
    return events


def normalize_date(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    ymd = _extract_ymd(text)
    if ymd:
        return ymd
    english = _extract_english_date(text)
    if english:
        parsed = _parse_english_date(english)
        if parsed:
            return parsed
    try:
        parsed_dt = parsedate_to_datetime(text)
        return parsed_dt.date().isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        iso = text.replace("Z", "+00:00")
        return datetime.fromisoformat(iso).date().isoformat()
    except ValueError:
        return ""


def _fetch_document(url: str) -> tuple[bool, str]:
    return get_url(url, accept=ACCEPT_DOCUMENT)


def _should_keep_existing(
    fresh: OfficialPostsFile,
    old: OfficialPostsFile | None,
    force: bool,
) -> bool:
    if force or old is None:
        return False
    return not fresh.parse_ok


def _post(title: str, date: str, url: str, as_of: str) -> OfficialPost | None:
    title = " ".join((title or "").split())
    url = (url or "").strip()
    if not title or not url or url.startswith("mailto:"):
        return None
    if url.startswith("//"):
        url = "https:" + url
    return OfficialPost(title=title, date=date, source_url=url, as_of=as_of)


def _announce_id(vendor_id: str, post: OfficialPost) -> str:
    day = post.date or post.as_of
    path = urlparse(post.source_url).path.rstrip("/")
    last = path.split("/")[-1] if path else "post"
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", last).strip("-").lower() or "post"
    return f"{day}-{vendor_id}-announce-{slug[:48]}"


def _child_text(node: ET.Element, name: str) -> str:
    child = node.find(name)
    if child is not None and child.text:
        return child.text.strip()
    tail = name.rsplit("}", 1)[-1]
    for item in node:
        if item.tag == name or item.tag.endswith(tail):
            if item.text:
                return item.text.strip()
    return ""


def _child_attr(node: ET.Element, name: str, attr: str) -> str:
    child = node.find(name)
    if child is not None:
        value = child.attrib.get(attr)
        if value:
            return value.strip()
    tail = name.rsplit("}", 1)[-1]
    for item in node:
        if item.tag == name or item.tag.endswith(tail):
            value = item.attrib.get(attr)
            if value:
                return value.strip()
    return ""


def _anchor_title(node: object, *, skip_time: bool = False) -> str:
    heading = None
    if hasattr(node, "css_first"):
        heading = node.css_first("h2") or node.css_first("h3") or node.css_first("h4")
    if heading is not None and heading.text():
        return " ".join(heading.text().split())
    text = " ".join((node.text() or "").split()) if hasattr(node, "text") else ""
    if skip_time:
        text = re.sub(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+\d{4}\b",
            " ",
            text,
            flags=re.I,
        )
        text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_cursor_blog_title(title: str, date: str) -> str:
    text = _clean_title(title, date)
    text = re.sub(
        r"^·?\s*(Company|Research|Product|Customers|Ideas)\s*",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"Cursor Team.*$", "", text)
    text = re.sub(r"\b\d+m(?:\d+)?(?:\s*min read)?.*$", "", text, flags=re.I)
    text = re.sub(r"([a-z])[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+.*$", r"\1", text)
    text = re.sub(r"\s*[·•]\s*$", "", text)
    return text.strip(" ·-–—|")


def _clean_title(title: str, date: str) -> str:
    text = " ".join((title or "").split())
    if date:
        text = text.replace(date, " ")
    text = re.sub(
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+\d{4}",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(r"20\d{2}[/.年-]\d{1,2}[/.月-]\d{1,2}", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ·-–—|")
    return text


def _strip_leading_category(title: str) -> str:
    return re.sub(
        r"^(Announcements|Product|Economic Research|Policy|Societal Impacts|Research)\s*",
        "",
        title,
    ).strip()


def _clean_minimax_title(text: str, date: str) -> str:
    cleaned = _clean_title(text, date)
    cleaned = re.sub(r"了解更多>?$", "", cleaned).strip()
    headline = re.search(r"(MiniMax[^：\n]{0,40}：[^了解]{6,80})", cleaned)
    if headline:
        return headline.group(1).strip(" ·-–—|")
    named = re.search(r"(MiniMax [A-Za-z0-9.]+(?:\s+[A-Za-z0-9.]+)*)", cleaned)
    if named:
        return named.group(1).strip()
    cleaned = re.sub(
        r"^(?:AI|Music Generation|Open Weights|Video Generation|Multimodal|Frontier Model|MSA)+",
        "",
        cleaned,
    ).strip()
    return cleaned


def _is_cursor_blog_post(href: str) -> bool:
    path = urlparse(href).path if "://" in href else href
    if not path.startswith("/blog/"):
        return False
    slug = path[len("/blog/") :].strip("/")
    if not slug or "/" in slug:
        return False
    return slug not in {"topic", "rss.xml", "atom.xml"}


def _path_match(href: str, prefix: str) -> bool:
    path = urlparse(href).path if "://" in href else href.split("?", 1)[0]
    return path.startswith(prefix) and len(path) > len(prefix)


def _extract_ymd(text: str) -> str | None:
    match = re.search(r"(20\d{2})[/.年-](\d{1,2})[/.月-](\d{1,2})", text)
    if not match:
        return None
    year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _extract_english_date(text: str) -> str | None:
    match = re.search(
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+\d{4})",
        text,
        flags=re.I,
    )
    return match.group(1) if match else None


def _parse_english_date(text: str) -> str:
    match = re.search(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),\s+(\d{4})",
        text,
        flags=re.I,
    )
    if not match:
        return ""
    month = MONTHS[match.group(1)[:3].lower()]
    try:
        return datetime(int(match.group(3)), month, int(match.group(2))).date().isoformat()
    except ValueError:
        return ""


def _router_data(html: str) -> dict[str, object] | None:
    marker = "window._ROUTER_DATA = "
    start = html.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = html.find("</script>", start)
    if end < 0:
        return None
    blob = html[start:end].strip().rstrip(";")
    try:
        payload = json.loads(blob)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
