"""Derive official-signal axes, merge handwritten overlay, persist scores.json."""

from __future__ import annotations

import json
from pathlib import Path

from kaoyi.models import (
    CompositeScore,
    OfficialPostsFile,
    RadarAxis,
    Review,
    ReviewsFile,
    SiteData,
    Snapshot,
    UnitCostLeague,
    UnitCostRow,
    ValueReport,
    Vendor,
    VendorValueRow,
)
from kaoyi.official import has_official_status_source
from kaoyi.quota import best_unit_cost_line, build_unit_cost_leagues
from kaoyi.radar import buyer_axis_values

DERIVED_AXES = (
    "availability",
    "price_structure",
    "usage_economy",
    "stability",
    "payment_region",
    "billing_transparency",
)
HANDWRITTEN_ONLY = ("capability", "switching_cost")
STATUS_SCORE = {"OPEN": 5, "LIMITED": 3, "SOLD OUT": 1, "PAUSED": 1}
SCORES_NAME = "scores.json"


def composite_score(review: Review, axes: list[RadarAxis]) -> CompositeScore:
    values = buyer_axis_values(review, axes)
    scored_n = len(values)
    axis_n = len(axes)
    if scored_n < 3:
        return CompositeScore(value=None, scored_n=scored_n, axis_n=axis_n)
    return CompositeScore(value=round(sum(values) / scored_n, 1), scored_n=scored_n, axis_n=axis_n)


def cheapness_score(rank_index: int, n: int) -> int:
    """0 = cheapest → 5; last → 2. A single vendor in a league is 5."""
    if n <= 1:
        return 5
    return int(round(5 - 3 * (rank_index / (n - 1))))


def usage_economy_from_leagues(leagues: list[UnitCostLeague]) -> dict[str, tuple[int, str]]:
    collected: dict[str, list[tuple[int, str]]] = {}
    for league in leagues:
        best_row: dict[str, UnitCostRow] = {}
        for row in league.rows:
            current = best_row.get(row.vendor_id)
            if current is None or row.unit_cost_cny < current.unit_cost_cny:
                best_row[row.vendor_id] = row
        ranked = sorted(best_row.values(), key=lambda item: item.unit_cost_cny)
        costs = [item.unit_cost_cny for item in ranked]
        n = len(ranked)
        for item in ranked:
            rank = costs.index(item.unit_cost_cny)
            score = cheapness_score(rank, n)
            if score >= 5:
                tone = "本联赛最低"
            elif score <= 2:
                tone = "本联赛偏高"
            else:
                tone = "本联赛居中"
            reason = f"官方可核单位成本 {item.display}，{tone}（{league.label}）。"
            collected.setdefault(item.vendor_id, []).append((score, reason))
    result: dict[str, tuple[int, str]] = {}
    for vendor_id, items in collected.items():
        items.sort(key=lambda pair: (-pair[0], pair[1]))
        result[vendor_id] = items[0]
    return result


def derive_availability(snapshot: Snapshot, vendor: Vendor) -> tuple[int, str] | None:
    status = snapshot.status or vendor.status
    score = STATUS_SCORE.get(status)
    if score is None:
        return None
    return score, f"官方状态 {status}。"


def derive_price_structure(snapshot: Snapshot) -> tuple[int, str]:
    plans = snapshot.plans
    if not plans:
        return 1, "官方快照没有套餐行。"
    numbered = [
        plan for plan in plans if plan.price.amount is not None and not plan.price.is_missing
    ]
    missing = [plan for plan in plans if plan.price.amount is None or plan.price.is_missing]
    if not missing:
        return 5, "官方各档均有刊例数字。"
    if numbered:
        names = "、".join(plan.name for plan in missing)
        return 3, f"官方 {names} 未见刊例数字。"
    return 1, "官方各档刊例均为「-」。"


def derive_billing_transparency(snapshot: Snapshot) -> tuple[int, str]:
    priced = [
        plan
        for plan in snapshot.plans
        if plan.price.amount is not None
        and not plan.price.is_missing
        and plan.price.source_url
        and plan.price.as_of
    ]
    if not priced:
        return 1, "官方套餐未见刊例数字。"
    if any(plan.official_quota is not None for plan in priced):
        return 5, "刊例含来源与日期，且官方用量为可核对数。"
    return 4, "刊例含来源与日期，但官方用量为文字或「-」。"


def derive_stability(
    vendor_id: str,
    official_posts: dict[str, OfficialPostsFile],
    *,
    has_status_source: bool | None = None,
) -> tuple[int, str] | None:
    if has_status_source is None:
        has_status_source = has_official_status_source(vendor_id)
    if not has_status_source:
        return None
    file = official_posts.get(vendor_id)
    count = 0
    if file is not None:
        count = sum(1 for post in file.posts if post.source_kind == "status")
    if count == 0:
        return 4, "官方状态页近90天无事故"
    if count <= 2:
        return 3, f"官方状态页近90天记录 {count} 起事故。"
    return 2, f"官方状态页近90天记录 {count} 起事故。"


def derive_payment_region(vendor: Vendor) -> tuple[int, str] | None:
    region = (vendor.region or "").upper()
    currency = (vendor.currency or "").upper()
    if region == "CN" and currency == "CNY":
        return 5, "官方区域 CN，购买页人民币计价。"
    if region == "GLOBAL" and currency == "USD":
        return 3, "官方区域 GLOBAL，购买页美元计价。"
    return None


def merge_review(
    handwritten: Review,
    derived_scores: dict[str, int],
    derived_reasons: dict[str, str],
    *,
    as_of: str,
) -> Review:
    scores: dict[str, int] = {}
    reasons: dict[str, str] = {}
    for axis in DERIVED_AXES:
        if axis in derived_scores:
            scores[axis] = derived_scores[axis]
            reasons[axis] = derived_reasons[axis]
        elif axis == "payment_region" and axis in handwritten.scores:
            scores[axis] = handwritten.scores[axis]
            reasons[axis] = (handwritten.reasons.get(axis) or "").strip()
    for axis in HANDWRITTEN_ONLY:
        if axis in handwritten.scores:
            scores[axis] = handwritten.scores[axis]
            reasons[axis] = (handwritten.reasons.get(axis) or "").strip()
    return Review(
        status="已评" if scores else "未评",
        scores=scores,
        reasons=reasons,
        note=handwritten.note,
        updated_at=as_of,
    )


def derive_vendor_axes(
    vendor: Vendor,
    snapshot: Snapshot,
    *,
    official_posts: dict[str, OfficialPostsFile],
    usage_economy: dict[str, tuple[int, str]],
) -> tuple[dict[str, int], dict[str, str]]:
    scores: dict[str, int] = {}
    reasons: dict[str, str] = {}

    availability = derive_availability(snapshot, vendor)
    if availability:
        scores["availability"], reasons["availability"] = availability

    price_structure = derive_price_structure(snapshot)
    scores["price_structure"], reasons["price_structure"] = price_structure

    if vendor.id in usage_economy:
        scores["usage_economy"], reasons["usage_economy"] = usage_economy[vendor.id]

    billing = derive_billing_transparency(snapshot)
    scores["billing_transparency"], reasons["billing_transparency"] = billing

    stability = derive_stability(vendor.id, official_posts)
    if stability:
        scores["stability"], reasons["stability"] = stability

    payment = derive_payment_region(vendor)
    if payment:
        scores["payment_region"], reasons["payment_region"] = payment

    return scores, reasons


def build_value_layer(
    vendors: list[Vendor],
    snapshots: dict[str, Snapshot],
    editorial: ReviewsFile,
    official_posts: dict[str, OfficialPostsFile],
    axes: list[RadarAxis],
    *,
    usd_to_cny_rate: float,
    as_of: str,
) -> tuple[ReviewsFile, ValueReport, dict[str, object]]:
    leagues, unranked = build_unit_cost_leagues(vendors, snapshots, usd_to_cny_rate)
    usage_economy = usage_economy_from_leagues(leagues)
    merged: dict[str, Review] = {}
    rows: list[VendorValueRow] = []

    for vendor in vendors:
        snapshot = snapshots[vendor.id] if vendor.id in snapshots else None
        if snapshot is None:
            continue
        handwritten = editorial.vendors.get(vendor.id) or Review()
        derived_scores, derived_reasons = derive_vendor_axes(
            vendor,
            snapshot,
            official_posts=official_posts,
            usage_economy=usage_economy,
        )
        review = merge_review(handwritten, derived_scores, derived_reasons, as_of=as_of)
        merged[vendor.id] = review
        composite = composite_score(review, axes)
        best = best_unit_cost_line(vendor.id, leagues)
        rows.append(
            VendorValueRow(
                vendor_id=vendor.id,
                name=vendor.name,
                kind=vendor.kind,
                composite=composite,
                review=review,
                best_unit_cost=best,
                as_of=snapshot.as_of,
            )
        )

    rows.sort(
        key=lambda row: (
            row.composite.value is None,
            -(row.composite.value or 0),
            row.name,
        )
    )
    reviews = ReviewsFile(axes=list(editorial.axes), vendors=merged)
    report = ValueReport(as_of=as_of, vendors=rows, leagues=leagues, unranked=unranked)
    artifact = scores_artifact(reviews, rows, as_of=as_of)
    return reviews, report, artifact


def scores_artifact(
    reviews: ReviewsFile,
    rows: list[VendorValueRow],
    *,
    as_of: str,
) -> dict[str, object]:
    vendors: dict[str, object] = {}
    by_id = {row.vendor_id: row for row in rows}
    for vendor_id, review in reviews.vendors.items():
        row = by_id.get(vendor_id)
        payload = review.model_dump(mode="json")
        payload["composite"] = row.composite.value if row else None
        payload["scored_n"] = row.composite.scored_n if row else 0
        vendors[vendor_id] = payload
    return {
        "as_of": as_of,
        "derived_axes": list(DERIVED_AXES),
        "handwritten_axes": list(HANDWRITTEN_ONLY),
        "vendors": vendors,
    }


def persist_scores(root: Path, data: SiteData) -> Path:
    path = root / "data" / SCORES_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact = scores_artifact(
        data.reviews,
        data.value.vendors if data.value else [],
        as_of=data.scores_as_of or data.config.build_as_of,
    )
    path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
