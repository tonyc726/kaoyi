#!/usr/bin/env python3
"""Fetch vendor pages. Adapters may return stubs; never invent prices."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters import REGISTRY  # noqa: E402
from kaoyi.daily import run_fetch  # noqa: E402
from kaoyi.official import run_official_fetch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch official pricing pages into snapshots.")
    parser.add_argument("--vendor", help="Only one adapter id")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing snapshot even when the adapter returns a stub",
    )
    args = parser.parse_args()

    selected = [args.vendor] if args.vendor else list(REGISTRY)
    for vendor_id in selected:
        if vendor_id not in REGISTRY:
            print(f"unknown adapter: {vendor_id}", file=sys.stderr)
            return 2

    result = run_fetch(ROOT, vendor_ids=selected, force=args.force)
    official = run_official_fetch(ROOT, vendor_ids=selected, force=args.force)
    print(
        f"fetch-status as_of={result.as_of} failed={len(result.failed_vendor_ids)} "
        f"events={len(result.events)} official_posts={len(official.written_vendor_ids)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
