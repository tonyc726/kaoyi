#!/usr/bin/env python3
"""Build the static 考异 site into dist/."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kaoyi.load import assemble  # noqa: E402
from kaoyi.models import Plan, SiteData  # noqa: E402
from kaoyi.scores import persist_scores  # noqa: E402

SITE = ROOT / "site"
DIST = ROOT / "dist"


def url_join(base: str, path: str) -> str:
    base = base if base.endswith("/") else base + "/"
    path = path.lstrip("/")
    return base + path


def cny_equiv(amount: float | None, currency: str | None, rate: float) -> str | None:
    if amount is None or amount == 0 or currency != "USD":
        return None
    return f"≈ ¥{amount * rate:.1f}"


def period_label(period: str | None) -> str:
    labels = {
        "month": "按月",
        "user-month": "按席 / 月",
        "usage": "按量",
    }
    if not period:
        return "-"
    return labels.get(period, period)


def price_or_dash(plan: Plan | None) -> str:
    if plan is None or plan.price.is_missing:
        return "-"
    return plan.price.display


def main() -> int:
    data = assemble(ROOT)
    persist_scores(ROOT, data)
    env = Environment(
        loader=FileSystemLoader(str(SITE / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals.update(
        {
            "site": data,
            "cfg": data.config,
            "base": data.config.site_base,
            "abs": lambda path: url_join(data.config.site_base, path),
            "cny_equiv": lambda amount, currency: cny_equiv(
                amount, currency, data.config.usd_to_cny_rate
            ),
            "price_or_dash": price_or_dash,
            "period_label": period_label,
        }
    )

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    _write(DIST / "index.html", env.get_template("index.html").render())
    _write(DIST / "usage" / "index.html", env.get_template("usage.html").render())
    _write(DIST / "events" / "index.html", env.get_template("events.html").render())
    _write(DIST / "about" / "index.html", env.get_template("about.html").render())
    _write(DIST / "value" / "index.html", env.get_template("value.html").render())
    for page in data.pages:
        _write(
            DIST / "vendors" / page.vendor.id / "index.html",
            env.get_template("vendor.html").render(page=page),
        )

    assets_src = SITE / "static"
    assets_dst = DIST / "assets"
    shutil.copytree(assets_src, assets_dst)

    _assert_no_cname(DIST)
    print(f"built {len(list(DIST.rglob('*.html')))} html pages → {DIST}")
    _summary(data)
    return 0


def _write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def _assert_no_cname(dist: Path) -> None:
    if (dist / "CNAME").exists():
        raise SystemExit("CNAME must not be generated for project Pages")


def _summary(data: SiteData) -> None:
    official_n = sum(len(item.posts) for item in data.official_posts.values() if item.parse_ok)
    print(
        f"vendors={len(data.vendors)} events={len(data.events)} "
        f"official_posts={official_n} base={data.config.site_base}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
