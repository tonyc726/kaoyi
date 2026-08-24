from __future__ import annotations

from pathlib import Path

import yaml

from kaoyi.models import (
    Event,
    FetchStatus,
    OfficialPostsFile,
    Review,
    ReviewsFile,
    SiteConfig,
    SiteData,
    Snapshot,
    Vendor,
    VendorPage,
    empty_snapshot,
)
from kaoyi.official import load_official_posts_dir, official_posts_as_events
from kaoyi.radar import render_radar_svg

ROOT = Path(__file__).resolve().parent.parent


def load_yaml(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_config(root: Path = ROOT) -> SiteConfig:
    return SiteConfig.model_validate(load_yaml(root / "config.yml"))


def load_vendors(root: Path = ROOT) -> list[Vendor]:
    raw = load_yaml(root / "vendors.yml") or []
    return [Vendor.model_validate(item) for item in raw]


def load_reviews(root: Path = ROOT) -> ReviewsFile:
    return ReviewsFile.model_validate(load_yaml(root / "reviews.yml"))


def load_events(root: Path = ROOT) -> list[Event]:
    events: list[Event] = []
    folder = root / "data" / "events"
    if not folder.exists():
        return events
    for path in sorted(folder.glob("*.yml")):
        events.append(Event.model_validate(load_yaml(path)))
    return events


def load_snapshots(root: Path = ROOT) -> dict[str, Snapshot]:
    snapshots: dict[str, Snapshot] = {}
    folder = root / "data" / "snapshots"
    if not folder.exists():
        return snapshots
    for path in sorted(folder.glob("*.json")):
        snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
        snapshots[snapshot.vendor_id] = snapshot
    return snapshots


def load_official_posts(root: Path = ROOT) -> dict[str, OfficialPostsFile]:
    return load_official_posts_dir(root)


def load_fetch_status(root: Path = ROOT) -> FetchStatus | None:
    path = root / "data" / "fetch-status.json"
    if not path.exists():
        return None
    return FetchStatus.model_validate_json(path.read_text(encoding="utf-8"))


def assemble(root: Path = ROOT) -> SiteData:
    config = load_config(root)
    vendors = load_vendors(root)
    snapshots = load_snapshots(root)
    reviews = load_reviews(root)
    events = load_events(root)
    fetch_status = load_fetch_status(root)
    official_posts = load_official_posts(root)
    announce_events = official_posts_as_events(official_posts)
    yaml_ids = {event.id for event in events}
    merged_events = events + [event for event in announce_events if event.id not in yaml_ids]
    merged_events.sort(key=lambda event: (event.as_of, event.id), reverse=True)

    pages: list[VendorPage] = []
    for vendor in vendors:
        snapshot = snapshots.get(vendor.id) or empty_snapshot(vendor, config.build_as_of)
        review = reviews.vendors.get(vendor.id) or Review()
        vendor_events = [
            event
            for event in merged_events
            if event.vendor_id == vendor.id and event.kind != "official_announce"
        ]
        file = official_posts.get(vendor.id)
        pages.append(
            VendorPage(
                vendor=vendor,
                snapshot=snapshot,
                review=review,
                events=vendor_events,
                radar_svg=render_radar_svg(review, config.radar_axes),
                official_posts=file.posts if file and file.parse_ok else [],
            )
        )

    return SiteData(
        config=config,
        vendors=vendors,
        snapshots=snapshots,
        reviews=reviews,
        events=merged_events,
        fetch_status=fetch_status,
        official_posts=official_posts,
        pages=pages,
    )
