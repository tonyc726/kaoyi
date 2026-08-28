"""Structured official quotas and same-unit unit-cost leagues.

Never invent a number. Fuzzy copy (约 N Agent) and multipliers (5x / 20x) stay out.
"""

from __future__ import annotations

import re

from kaoyi.models import (
    OfficialQuota,
    Plan,
    PriceCell,
    Snapshot,
    UnitCostLeague,
    UnitCostRow,
    UnrankedSku,
    Vendor,
)

PER_WAN = 10_000.0

LEAGUE_PHRASE: dict[tuple[str, str], str] = {
    ("credits", "week"): "每周积分",
    ("credits", "month"): "每月积分",
    ("credits", "5h"): "每5小时积分",
    ("requests", "week"): "每周请求",
    ("requests", "month"): "每月请求",
    ("requests", "5h"): "每5小时请求",
}

UNIT_PER_WAN: dict[str, str] = {
    "credits": "万积分",
    "requests": "万次",
}

_NUM = r"([\d,，]+)"
_WEEKLY_CREDITS = re.compile(rf"每周\s*{_NUM}\s*积分")
_FIVEH_CREDITS = re.compile(rf"(?:每\s*)?5\s*小时\s*{_NUM}\s*积分")
_MONTHLY_REQUESTS = re.compile(rf"每月\s*{_NUM}\s*次")
_WEEKLY_REQUESTS = re.compile(rf"每周\s*{_NUM}\s*次")
_FIVEH_REQUESTS = re.compile(rf"每\s*5\s*小时\s*{_NUM}\s*次")
_FUZZY_AGENT = re.compile(r"(约|大约|左右).{0,12}(Agent|个)")


def parse_official_quota(quota: str, source_url: str, as_of: str) -> OfficialQuota | None:
    """Extract a hard official number. Return None when the text is not comparable."""
    text = (quota or "").strip()
    if not text or text == "-":
        return None
    if _FUZZY_AGENT.search(text):
        return None

    for match, unit, window in (
        (_WEEKLY_CREDITS.search(text), "credits", "week"),
        (_MONTHLY_REQUESTS.search(text), "requests", "month"),
        (_WEEKLY_REQUESTS.search(text), "requests", "week"),
        (_FIVEH_CREDITS.search(text), "credits", "5h"),
        (_FIVEH_REQUESTS.search(text), "requests", "5h"),
    ):
        if match is None:
            continue
        amount = _positive_number(match.group(1))
        if amount is None:
            continue
        return OfficialQuota(
            amount=amount,
            unit=unit,  # type: ignore[arg-type]
            window=window,  # type: ignore[arg-type]
            source_url=source_url,
            as_of=as_of,
        )
    return None


def hydrate_plan_quota(plan: Plan, *, source_url: str, as_of: str) -> Plan:
    if plan.official_quota is not None:
        return plan
    parsed = parse_official_quota(
        plan.quota,
        plan.price.source_url or source_url,
        plan.price.as_of or as_of,
    )
    if parsed is None:
        return plan
    return plan.model_copy(update={"official_quota": parsed})


def hydrate_snapshot(snapshot: Snapshot) -> Snapshot:
    plans = [
        hydrate_plan_quota(plan, source_url=snapshot.source_url, as_of=snapshot.as_of)
        for plan in snapshot.plans
    ]
    return snapshot.model_copy(update={"plans": plans})


def monthly_list_cny(price: PriceCell, usd_to_cny_rate: float) -> tuple[float | None, bool]:
    """List-price CNY and whether USD was converted with the editorial rate."""
    if price.amount is None or price.is_missing:
        return None, False
    if price.currency == "CNY":
        return float(price.amount), False
    if price.currency == "USD":
        return float(price.amount) * usd_to_cny_rate, True
    return None, False


def format_unit_cost(per_unit_cny: float, unit: str, *, converted: bool) -> str:
    per_wan = per_unit_cny * PER_WAN
    label = UNIT_PER_WAN.get(unit, "万单位")
    suffix = "（编辑换算）" if converted else ""
    return f"{_format_yuan(per_wan)} / {label}{suffix}"


def league_id(unit: str, window: str) -> str:
    return f"{unit}/{window}"


def league_label(unit: str, window: str) -> str:
    return LEAGUE_PHRASE.get((unit, window), f"{unit}/{window}")


def unranked_reason(*, has_price: bool, has_quota: bool) -> str:
    if not has_price and not has_quota:
        return "官方未给可核对刊例或用量，无法自动比性价比。"
    if not has_quota:
        return "官方未给可核对用量，无法自动比性价比。"
    return "官方未给可核对刊例，无法自动比性价比。"


def build_unit_cost_leagues(
    vendors: list[Vendor],
    snapshots: dict[str, Snapshot],
    usd_to_cny_rate: float,
) -> tuple[list[UnitCostLeague], list[UnrankedSku]]:
    names = {vendor.id: vendor.name for vendor in vendors}
    buckets: dict[str, list[UnitCostRow]] = {}
    unranked: list[UnrankedSku] = []

    for vendor in vendors:
        snapshot = snapshots.get(vendor.id)
        if snapshot is None:
            continue
        for plan in snapshot.plans:
            monthly, converted = monthly_list_cny(plan.price, usd_to_cny_rate)
            quota = plan.official_quota
            has_price = monthly is not None
            has_quota = quota is not None
            if not has_price or not has_quota or quota is None or monthly is None:
                unranked.append(
                    UnrankedSku(
                        vendor_id=vendor.id,
                        vendor_name=vendor.name,
                        sku_id=plan.id,
                        sku_name=plan.name,
                        reason=unranked_reason(has_price=has_price, has_quota=has_quota),
                        as_of=plan.price.as_of or snapshot.as_of,
                    )
                )
                continue
            per_unit = monthly / quota.amount
            key = league_id(quota.unit, quota.window)
            label = league_label(quota.unit, quota.window)
            buckets.setdefault(key, []).append(
                UnitCostRow(
                    vendor_id=vendor.id,
                    vendor_name=names[vendor.id],
                    sku_id=plan.id,
                    sku_name=plan.name,
                    league_id=key,
                    league_label=label,
                    monthly_list_cny=monthly,
                    quota_amount=quota.amount,
                    unit_cost_cny=per_unit,
                    display=format_unit_cost(per_unit, quota.unit, converted=converted),
                    converted=converted,
                    source_url=quota.source_url or plan.price.source_url,
                    as_of=quota.as_of or plan.price.as_of,
                )
            )

    leagues: list[UnitCostLeague] = []
    for key in sorted(buckets):
        rows = sorted(
            buckets[key],
            key=lambda row: (row.unit_cost_cny, row.vendor_id, row.sku_id),
        )
        if not rows:
            continue
        best_cost = rows[0].unit_cost_cny
        marked: list[UnitCostRow] = []
        for row in rows:
            marked.append(row.model_copy(update={"is_best": row.unit_cost_cny == best_cost}))
        best = next(row for row in marked if row.is_best)
        sku = f"{best.vendor_name} {best.sku_name}"
        opinion = (
            f"在官方写明{best.league_label}的套餐中，{sku} 刊例约 {best.display}，本轮最低。"
        )
        leagues.append(
            UnitCostLeague(
                id=key,
                label=best.league_label,
                unit=key.split("/", 1)[0],
                window=key.split("/", 1)[1],
                rows=marked,
                opinion=opinion,
            )
        )
    return leagues, unranked


def best_unit_cost_line(vendor_id: str, leagues: list[UnitCostLeague]) -> str | None:
    candidates = [row for league in leagues for row in league.rows if row.vendor_id == vendor_id]
    if not candidates:
        return None
    best = min(candidates, key=lambda row: (row.unit_cost_cny, row.sku_id))
    return f"{best.sku_name} {best.display}"


def _positive_number(raw: str) -> float | None:
    text = (raw or "").replace(",", "").replace("，", "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _format_yuan(value: float) -> str:
    if value >= 100:
        return f"¥{value:.0f}"
    if value >= 10:
        return f"¥{value:.1f}"
    return f"¥{value:.2f}"
