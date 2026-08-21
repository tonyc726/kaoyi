from __future__ import annotations

from pathlib import Path

import yaml

from kaoyi.models import (
    Event,
    Review,
    ReviewsFile,
    SiteConfig,
    SiteData,
    Snapshot,
    Vendor,
    VendorPage,
    empty_snapshot,
)
from kaoyi.price_chart import render_price_chart_svg
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


def assemble(root: Path = ROOT) -> SiteData:
    config = load_config(root)
    vendors = load_vendors(root)
    snapshots = load_snapshots(root)
    reviews = load_reviews(root)
    events = load_events(root)

    pages: list[VendorPage] = []
    for vendor in vendors:
        snapshot = snapshots.get(vendor.id) or empty_snapshot(vendor, config.build_as_of)
        review = reviews.vendors.get(vendor.id) or Review()
        pages.append(
            VendorPage(
                vendor=vendor,
                snapshot=snapshot,
                review=review,
                events=[event for event in events if event.vendor_id == vendor.id],
                radar_svg=render_radar_svg(review, config.radar_axes),
            )
        )

    site = SiteData(
        config=config,
        vendors=vendors,
        snapshots=snapshots,
        reviews=reviews,
        events=events,
        pages=pages,
    )
    site.price_chart_svg = render_price_chart_svg(site)
    return site
