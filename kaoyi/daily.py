"""Daily official-price fetch: retain last-good, record failures, emit price_change."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from adapters import REGISTRY
from adapters.base import today
from kaoyi.load import load_events, load_snapshots, load_vendors
from kaoyi.models import Event, FetchStatus, Plan, Snapshot

FetchFn = Callable[[], Snapshot]


@dataclass
class FetchRunResult:
    as_of: str
    failed_vendor_ids: list[str] = field(default_factory=list)
    written_vendor_ids: list[str] = field(default_factory=list)
    retained_vendor_ids: list[str] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)


def run_fetch(
    root: Path,
    *,
    vendor_ids: list[str] | None = None,
    registry: dict[str, FetchFn] | None = None,
    force: bool = False,
    as_of: str | None = None,
) -> FetchRunResult:
    """Fetch adapters, keep last-good on stub, write fetch-status and price events."""
    adapters = registry if registry is not None else REGISTRY
    selected = list(vendor_ids) if vendor_ids is not None else list(adapters)
    day = as_of or today()
    existing = load_snapshots(root)
    out_dir = root / "data" / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    failed: list[str] = []
    written: list[str] = []
    retained: list[str] = []
    successful_new: dict[str, Snapshot] = {}

    for vendor_id in selected:
        fetch_fn = adapters.get(vendor_id)
        if fetch_fn is None:
            raise KeyError(f"unknown adapter: {vendor_id}")
        snapshot = fetch_fn()
        old = existing.get(vendor_id)
        path = out_dir / f"{vendor_id}.json"
        if _should_keep_existing(snapshot, old, force):
            print(f"keep {vendor_id}: adapter stub, existing snapshot retained")
            retained.append(vendor_id)
            failed.append(vendor_id)
            continue
        path.write_text(
            json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(vendor_id)
        print(f"wrote {path.relative_to(root)} parse_ok={snapshot.parse_ok}")
        if snapshot.parse_ok:
            successful_new[vendor_id] = snapshot
        else:
            failed.append(vendor_id)

    status = FetchStatus(as_of=day, failed_vendor_ids=failed)
    write_fetch_status(root, status)
    events = write_price_change_events(root, existing, successful_new, day)
    return FetchRunResult(
        as_of=day,
        failed_vendor_ids=failed,
        written_vendor_ids=written,
        retained_vendor_ids=retained,
        events=events,
    )


def write_fetch_status(root: Path, status: FetchStatus) -> Path:
    path = root / "data" / "fetch-status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(status.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_price_change_events(
    root: Path,
    old_snapshots: dict[str, Snapshot],
    new_snapshots: dict[str, Snapshot],
    as_of: str,
) -> list[Event]:
    """Write one official price_change event per vendor+sku+old→new+date."""
    existing_ids = {event.id for event in load_events(root)}
    names = _vendor_names(root)
    folder = root / "data" / "events"
    written: list[Event] = []
    for vendor_id, new in new_snapshots.items():
        old = old_snapshots.get(vendor_id)
        if old is None:
            continue
        for event in iter_price_change_events(old, new, as_of, names.get(vendor_id, vendor_id)):
            if event.id in existing_ids:
                continue
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{event.id}.yml"
            path.write_text(_dump_event_yaml(event), encoding="utf-8")
            existing_ids.add(event.id)
            written.append(event)
            print(f"wrote {path.relative_to(root)}")
    return written


def iter_price_change_events(
    old: Snapshot,
    new: Snapshot,
    as_of: str,
    vendor_label: str,
) -> list[Event]:
    events: list[Event] = []
    old_plans = {plan.id: plan for plan in old.plans}
    new_plans = {plan.id: plan for plan in new.plans}
    for sku_id in sorted(set(old_plans) | set(new_plans)):
        old_plan = old_plans.get(sku_id)
        new_plan = new_plans.get(sku_id)
        if not _list_price_changed(old_plan, new_plan):
            continue
        old_display = _plan_display(old_plan)
        new_display = _plan_display(new_plan)
        plan_name = (new_plan or old_plan).name if (new_plan or old_plan) else sku_id
        source_url = ""
        if new_plan is not None:
            source_url = new_plan.price.source_url or new.source_url
        elif old_plan is not None:
            source_url = old_plan.price.source_url or old.source_url
        event_id = price_change_event_id(
            as_of, new.vendor_id, sku_id, old_display, new_display, old_plan, new_plan
        )
        events.append(
            Event(
                id=event_id,
                vendor_id=new.vendor_id,
                layer="official",
                kind="price_change",
                title=f"{vendor_label} {plan_name} 目录价变动",
                summary=f"官方标价从 {old_display} 变为 {new_display}。",
                as_of=as_of,
                source_url=source_url,
                example=False,
                status="OPEN",
                note="官方层。由每日抓取对照上次快照生成，不是社区传闻。",
            )
        )
    return events


def price_change_event_id(
    as_of: str,
    vendor_id: str,
    sku_id: str,
    old_display: str,
    new_display: str,
    old_plan: Plan | None,
    new_plan: Plan | None,
) -> str:
    old_slug = _price_slug(old_display, old_plan.price.amount if old_plan else None)
    new_slug = _price_slug(new_display, new_plan.price.amount if new_plan else None)
    return f"{as_of}-{vendor_id}-{sku_id}-{old_slug}-to-{new_slug}"


def _should_keep_existing(fresh: Snapshot, old: Snapshot | None, force: bool) -> bool:
    if force or old is None:
        return False
    return not fresh.parse_ok


def _list_price_changed(old_plan: Plan | None, new_plan: Plan | None) -> bool:
    if _price_missing(old_plan) and _price_missing(new_plan):
        return False
    old_amount = old_plan.price.amount if old_plan else None
    new_amount = new_plan.price.amount if new_plan else None
    old_display = _plan_display(old_plan)
    new_display = _plan_display(new_plan)
    return old_amount != new_amount or old_display != new_display


def _price_missing(plan: Plan | None) -> bool:
    if plan is None:
        return True
    return plan.price.is_missing and plan.price.amount is None


def _plan_display(plan: Plan | None) -> str:
    if plan is None:
        return "-"
    display = plan.price.display.strip()
    return display or "-"


def _price_slug(display: str, amount: float | None) -> str:
    if amount is not None:
        if float(amount) == int(amount):
            return str(int(amount))
        return str(amount).replace(".", "p")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", display.strip().lower()).strip("-")
    return cleaned or "dash"


def _vendor_names(root: Path) -> dict[str, str]:
    path = root / "vendors.yml"
    if not path.exists():
        return {}
    return {vendor.id: vendor.name for vendor in load_vendors(root)}


def _dump_event_yaml(event: Event) -> str:
    payload = event.model_dump(mode="json")
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    return text if text.endswith("\n") else text + "\n"
