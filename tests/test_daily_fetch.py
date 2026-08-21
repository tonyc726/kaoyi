from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from kaoyi.daily import run_fetch
from kaoyi.load import assemble, load_events, load_fetch_status, load_snapshots
from kaoyi.models import Event, Plan, PriceCell, Snapshot

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://help.aliyun.com/zh/model-studio/coding-plan"


def _price(display: str, amount: float | None, as_of: str = "2026-08-20") -> PriceCell:
    return PriceCell(
        display=display,
        amount=amount,
        currency="CNY",
        period="month",
        source_url=SOURCE,
        as_of=as_of,
    )


def _plan(sku_id: str, name: str, display: str, amount: float | None) -> Plan:
    return Plan(id=sku_id, name=name, price=_price(display, amount))


def _snapshot(
    vendor_id: str,
    plans: list[Plan],
    *,
    parse_ok: bool = True,
    as_of: str = "2026-08-20",
) -> Snapshot:
    return Snapshot(
        vendor_id=vendor_id,
        source_url=SOURCE,
        as_of=as_of,
        fetched_ok=parse_ok,
        parse_ok=parse_ok,
        status="LIMITED",
        billing_unit="月订阅",
        notes="test fixture",
        plans=plans,
    )


def _write_snapshot(root: Path, snapshot: Snapshot) -> None:
    folder = root / "data" / "snapshots"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{snapshot.vendor_id}.json").write_text(
        json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_vendors(root: Path) -> None:
    (root / "vendors.yml").write_text(
        """
- id: aliyun
  name: 阿里·百炼
  name_en: Alibaba Model Studio
  kind: plan
  status: LIMITED
  region: CN
  currency: CNY
  official_url: https://help.aliyun.com/zh/model-studio/coding-plan
  buy_url: https://help.aliyun.com/zh/model-studio/coding-plan
  docs_url: https://help.aliyun.com/zh/model-studio/coding-plan
  adapter: aliyun
  short: Coding Plan
""",
        encoding="utf-8",
    )


def test_price_diff_writes_one_price_change_event(tmp_path: Path) -> None:
    old = _snapshot("aliyun", [_plan("pro", "Pro", "¥200", 200)])
    _write_snapshot(tmp_path, old)
    _write_vendors(tmp_path)
    fresh = _snapshot(
        "aliyun",
        [_plan("pro", "Pro", "¥220", 220)],
        as_of="2026-08-21",
    )

    result = run_fetch(
        tmp_path,
        vendor_ids=["aliyun"],
        registry={"aliyun": lambda: fresh},
        as_of="2026-08-21",
    )

    assert len(result.events) == 1
    event = result.events[0]
    assert event.layer == "official"
    assert event.kind == "price_change"
    assert event.example is False
    assert event.vendor_id == "aliyun"
    assert event.as_of == "2026-08-21"
    assert event.title == "阿里·百炼 Pro 目录价变动"
    assert event.summary == "官方标价从 ¥200 变为 ¥220。"
    assert event.source_url == SOURCE
    assert event.id == "2026-08-21-aliyun-pro-200-to-220"
    assert event.confidence == 0.9
    assert event.is_unconfirmed is False

    files = list((tmp_path / "data" / "events").glob("*.yml"))
    assert len(files) == 1
    loaded = Event.model_validate(yaml.safe_load(files[0].read_text(encoding="utf-8")))
    assert loaded == event
    assert load_events(tmp_path) == [event]

    again = run_fetch(
        tmp_path,
        vendor_ids=["aliyun"],
        registry={"aliyun": lambda: fresh},
        as_of="2026-08-21",
    )
    assert again.events == []
    assert len(list((tmp_path / "data" / "events").glob("*.yml"))) == 1


def test_unchanged_prices_write_no_event(tmp_path: Path) -> None:
    old = _snapshot("aliyun", [_plan("pro", "Pro", "¥200", 200)])
    _write_snapshot(tmp_path, old)
    fresh = _snapshot(
        "aliyun",
        [_plan("pro", "Pro", "¥200", 200)],
        as_of="2026-08-21",
    )
    fresh.notes = "newer fetch, same list price"

    result = run_fetch(
        tmp_path,
        vendor_ids=["aliyun"],
        registry={"aliyun": lambda: fresh},
        as_of="2026-08-21",
    )

    assert result.events == []
    assert not (tmp_path / "data" / "events").exists()
    written = load_snapshots(tmp_path)["aliyun"]
    assert written.plans[0].price.amount == 200
    assert written.plans[0].price.display == "¥200"
    assert written.as_of == "2026-08-21"


def test_failed_fetch_keeps_last_good_and_counts_failure(tmp_path: Path) -> None:
    last_good = _snapshot("aliyun", [_plan("pro", "Pro", "¥200", 200)])
    _write_snapshot(tmp_path, last_good)
    before = (tmp_path / "data" / "snapshots" / "aliyun.json").read_text(encoding="utf-8")
    stub = Snapshot(
        vendor_id="aliyun",
        source_url=SOURCE,
        as_of="2026-08-21",
        fetched_ok=False,
        parse_ok=False,
        status="LIMITED",
        notes="Adapter stub. No invented numbers.",
        plans=[],
    )

    result = run_fetch(
        tmp_path,
        vendor_ids=["aliyun"],
        registry={"aliyun": lambda: stub},
        as_of="2026-08-21",
    )

    assert result.failed_vendor_ids == ["aliyun"]
    assert result.retained_vendor_ids == ["aliyun"]
    assert result.written_vendor_ids == []
    assert result.events == []
    after = (tmp_path / "data" / "snapshots" / "aliyun.json").read_text(encoding="utf-8")
    assert after == before
    kept = load_snapshots(tmp_path)["aliyun"]
    assert kept.parse_ok is True
    assert kept.plans[0].price.amount == 200
    assert kept.plans[0].price.display == "¥200"
    status = load_fetch_status(tmp_path)
    assert status is not None
    assert status.as_of == "2026-08-21"
    assert status.failed_vendor_ids == ["aliyun"]
    assert status.failed_count == 1


def _write_status(failed: list[str]) -> Path:
    path = ROOT / "data" / "fetch-status.json"
    path.write_text(
        json.dumps(
            {"as_of": "2026-08-21", "failed_vendor_ids": failed},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _build_index() -> str:
    result = subprocess.run(
        [sys.executable, "scripts/build.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return (ROOT / "dist" / "index.html").read_text(encoding="utf-8")


def test_homepage_banner_when_failures() -> None:
    path = _write_status(["volcengine", "claude"])
    try:
        html = _build_index()
        assert "今日失败 2 家" in html
        assert assemble(ROOT).fetch_status is not None
        assert assemble(ROOT).fetch_status.failed_count == 2
    finally:
        path.unlink(missing_ok=True)


def test_homepage_hides_banner_when_no_failures() -> None:
    path = _write_status([])
    try:
        html = _build_index()
        assert "今日失败" not in html
        assert assemble(ROOT).fetch_status is not None
        assert assemble(ROOT).fetch_status.failed_count == 0
    finally:
        path.unlink(missing_ok=True)
