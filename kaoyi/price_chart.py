from __future__ import annotations

from dataclasses import dataclass

from kaoyi.models import Plan, SiteData

CHART_WIDTH = 720
PAD_X = 8
PAD_Y = 6
CAPTION_H = 18
ROW_H = 15
NAME_W = 220
GUTTER = 8
BAR_MAX = 300
BAR_H = 7
AMOUNT_GAP = 6
USER_MONTH_MARK = "按席"
CAPTION_TMPL = "约合 ¥/月 · 美元按 {rate} 换算，不是牌价"


@dataclass(frozen=True)
class ChartRow:
    vendor_id: str
    vendor_name: str
    plan_id: str
    plan_name: str
    currency: str
    display: str
    monthly_cny: float
    period: str | None


def is_chartable(plan: Plan) -> bool:
    price = plan.price
    if price.is_missing or price.amount is None or price.amount == 0:
        return False
    return price.currency in {"CNY", "USD"}


def monthly_cny(amount: float, currency: str, rate: float) -> float:
    raw = amount if currency == "CNY" else amount * rate
    return round(raw, 1)


def format_approx_cny(value: float) -> str:
    rounded = round(value, 1)
    if rounded == int(rounded):
        return f"≈ ¥{int(rounded)}"
    return f"≈ ¥{rounded:.1f}"


def format_rate(rate: float) -> str:
    return f"{rate:g}"


def chart_caption(rate: float) -> str:
    return CAPTION_TMPL.format(rate=format_rate(rate))


def chart_rows(site: SiteData) -> list[ChartRow]:
    rate = site.config.usd_to_cny_rate
    rows: list[ChartRow] = []
    for page in site.plan_vendors():
        for plan in page.snapshot.plans:
            if not is_chartable(plan):
                continue
            currency = plan.price.currency or ""
            amount = float(plan.price.amount) if plan.price.amount is not None else 0.0
            rows.append(
                ChartRow(
                    vendor_id=page.vendor.id,
                    vendor_name=page.vendor.name,
                    plan_id=plan.id,
                    plan_name=plan.name,
                    currency=currency,
                    display=plan.price.display,
                    monthly_cny=monthly_cny(amount, currency, rate),
                    period=plan.price.period,
                )
            )
    return rows


def scale_max(rows: list[ChartRow]) -> float:
    if not rows:
        return 0.0
    return max(row.monthly_cny for row in rows)


def bar_width(amount: float, panel_max: float) -> float:
    if amount <= 0 or panel_max <= 0:
        return 0.0
    return BAR_MAX * (amount / panel_max)


def left_label(row: ChartRow) -> str:
    return f"{row.vendor_name}  {row.plan_name}"


def amount_parts(row: ChartRow) -> tuple[str, str | None]:
    seat = f" {USER_MONTH_MARK}" if row.period == "user-month" else ""
    if row.currency == "CNY":
        return f"{row.display}{seat}", None
    return f"{format_approx_cny(row.monthly_cny)}{seat}", row.display


def render_price_chart_svg(site: SiteData) -> str:
    rate = site.config.usd_to_cny_rate
    rows = chart_rows(site)
    peak = scale_max(rows)
    caption = chart_caption(rate)
    height = PAD_Y + CAPTION_H + len(rows) * ROW_H + PAD_Y
    baseline_x = PAD_X + NAME_W + GUTTER
    y = PAD_Y + CAPTION_H

    parts: list[str] = [
        f'<svg class="price-chart" data-scale-max="{_fmt(peak)}" '
        f'data-rate="{_xml(format_rate(rate))}" viewBox="0 0 {CHART_WIDTH} {height}" '
        f'role="img" aria-label="{_xml(caption)}">',
        f'<text x="{PAD_X:.1f}" y="{PAD_Y + 12:.1f}" class="price-chart-caption">'
        f"{_xml(caption)}</text>",
    ]

    first_row_y: float | None = None
    last_row_y: float | None = None
    for row in rows:
        mid = y + ROW_H / 2
        if first_row_y is None:
            first_row_y = mid
        last_row_y = mid
        width = bar_width(row.monthly_cny, peak)
        bar_y = mid - BAR_H / 2
        primary, secondary = amount_parts(row)
        parts.append(
            f'<text x="{PAD_X + NAME_W:.1f}" y="{mid:.1f}" class="price-chart-name" '
            f'data-vendor-id="{_xml(row.vendor_id)}" data-plan-id="{_xml(row.plan_id)}">'
            f"{_xml(left_label(row))}</text>"
        )
        parts.append(
            f'<rect class="price-bar" data-vendor-id="{_xml(row.vendor_id)}" '
            f'data-plan-id="{_xml(row.plan_id)}" data-currency="{_xml(row.currency)}" '
            f'data-monthly-cny="{_fmt(row.monthly_cny)}" '
            f'x="{baseline_x:.1f}" y="{bar_y:.1f}" '
            f'width="{width:.2f}" height="{BAR_H}" />'
        )
        label_x = baseline_x + width + AMOUNT_GAP
        amount_xml = _xml(primary)
        if secondary:
            amount_xml += (
                f' <tspan class="price-chart-fx">{_xml(secondary)}</tspan>'
            )
        parts.append(
            f'<text x="{label_x:.1f}" y="{mid:.1f}" class="price-chart-amount">'
            f"{amount_xml}</text>"
        )
        y += ROW_H

    if first_row_y is not None and last_row_y is not None:
        top = first_row_y - BAR_H / 2
        bottom = last_row_y + BAR_H / 2
        parts.append(
            f'<line class="price-chart-baseline" x1="{baseline_x:.1f}" y1="{top:.1f}" '
            f'x2="{baseline_x:.1f}" y2="{bottom:.1f}" />'
        )

    parts.append("</svg>")
    return "".join(parts)


def _fmt(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
