#!/usr/bin/env python3
"""Fetch vendor pages. Adapters may return stubs; never invent prices."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters import REGISTRY  # noqa: E402
from kaoyi.load import load_snapshots  # noqa: E402
from kaoyi.models import Snapshot  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch official pricing pages into snapshots.")
    parser.add_argument("--vendor", help="Only one adapter id")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing snapshot even when the adapter returns a stub",
    )
    args = parser.parse_args()

    existing = load_snapshots(ROOT)
    out_dir = ROOT / "data" / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    selected = [args.vendor] if args.vendor else list(REGISTRY)
    for vendor_id in selected:
        fetch_fn = REGISTRY.get(vendor_id)
        if fetch_fn is None:
            print(f"unknown adapter: {vendor_id}", file=sys.stderr)
            return 2
        snapshot = fetch_fn()
        path = out_dir / f"{vendor_id}.json"
        if _should_keep_existing(snapshot, existing.get(vendor_id), args.force):
            print(f"keep {vendor_id}: adapter stub, existing snapshot retained")
            continue
        path.write_text(
            json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {path.relative_to(ROOT)} parse_ok={snapshot.parse_ok}")
    return 0


def _should_keep_existing(fresh: Snapshot, old: Snapshot | None, force: bool) -> bool:
    if force or old is None:
        return False
    return not fresh.parse_ok


if __name__ == "__main__":
    raise SystemExit(main())
