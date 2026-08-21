from __future__ import annotations

from kaoyi.models import Plan, SiteData, VendorPage

# Pixel budget for one panel. Bar length is amount / panel max * BAR_MAX.
PANEL_WIDTH = 520
PAD_X = 12
PAD_Y = 10
TITLE_H = 28
VENDOR_H = 20
ROW_H = 20
GROUP_GAP = 8
NAME_W = 118
GUTTER = 10
BAR_MAX = 240
BAR_H = 10
TICK_W = 1
AMOUNT_GAP = 8
USER_MONTH_MARK = "按席"

PANELS: tuple[tuple[str, str], ...] = (
    ("CNY", "人民币"),
    ("USD", "美元"),
)


def is_chartable(plan: Plan, currency: str) -> bool:
    price = plan.price
    if price.is_missing or price.amount is None or price.currency != currency:
        return False
    return True


def groups_for(site: SiteData, currency: str) -> list[tuple[VendorPage, list[Plan]]]:
    groups: list[tuple[VendorPage, list[Plan]]] = []
    for page in site.plan_vendors():
        plans = [plan for plan in page.snapshot.plans if is_chartable(plan, currency)]
        if plans:
            groups.append((page, plans))
    return groups


def panel_scale_max(site: SiteData, currency: str) -> float:
    amounts = [
        float(plan.price.amount)
        for _, plans in groups_for(site, currency)
        for plan in plans
        if plan.price.amount is not None
    ]
    return max(amounts) if amounts else 0.0


def bar_width(amount: float, scale_max: float) -> float:
    if amount <= 0 or scale_max <= 0:
        return 0.0
    return BAR_MAX * (amount / scale_max)


def amount_label(plan: Plan) -> str:
    label = plan.price.display
    if plan.price.period == "user-month":
        return f"{label} {USER_MONTH_MARK}"
    return label


def render_price_chart_svg(site: SiteData) -> str:
    panels = [_render_panel(site, currency, title) for currency, title in PANELS]
    return (
        '<div class="price-chart" aria-label="官方标价对照">'
        + "".join(panels)
        + "</div>"
    )


def _render_panel(site: SiteData, currency: str, title: str) -> str:
    groups = groups_for(site, currency)
    scale_max = panel_scale_max(site, currency)
    height = _panel_height(groups)
    baseline_x = PAD_X + NAME_W + GUTTER
    y = PAD_Y + TITLE_H

    parts: list[str] = [
        f'<svg class="price-chart-panel" data-currency="{_xml(currency)}" '
        f'data-scale-max="{_fmt(scale_max)}" viewBox="0 0 {PANEL_WIDTH} {height}" '
        f'role="img" aria-label="{_xml(title + "官方标价")}">',
        f'<text x="{PAD_X:.1f}" y="{PAD_Y + 16:.1f}" class="price-chart-title">'
        f"{_xml(title)}</text>",
    ]

    first_row_y: float | None = None
    last_row_y: float | None = None
    for page, plans in groups:
        parts.append(
            f'<text x="{PAD_X:.1f}" y="{y + 14:.1f}" class="price-chart-vendor" '
            f'data-vendor-id="{_xml(page.vendor.id)}">{_xml(page.vendor.name)}</text>'
        )
        y += VENDOR_H
        for plan in plans:
            mid = y + ROW_H / 2
            if first_row_y is None:
                first_row_y = mid
            last_row_y = mid
            amount = float(plan.price.amount) if plan.price.amount is not None else 0.0
            width = bar_width(amount, scale_max)
            bar_y = mid - BAR_H / 2
            parts.append(
                f'<text x="{PAD_X + NAME_W:.1f}" y="{mid:.1f}" '
                f'class="price-chart-name" data-plan-id="{_xml(plan.id)}">'
                f"{_xml(plan.name)}</text>"
            )
            if width > 0:
                parts.append(
                    f'<rect class="price-bar" data-currency="{_xml(currency)}" '
                    f'data-vendor-id="{_xml(page.vendor.id)}" '
                    f'data-plan-id="{_xml(plan.id)}" data-amount="{_fmt(amount)}" '
                    f'x="{baseline_x:.1f}" y="{bar_y:.1f}" '
                    f'width="{width:.2f}" height="{BAR_H}" />'
                )
                label_x = baseline_x + width + AMOUNT_GAP
            else:
                parts.append(
                    f'<rect class="price-tick" data-currency="{_xml(currency)}" '
                    f'data-vendor-id="{_xml(page.vendor.id)}" '
                    f'data-plan-id="{_xml(plan.id)}" data-amount="{_fmt(amount)}" '
                    f'x="{baseline_x:.1f}" y="{bar_y:.1f}" '
                    f'width="{TICK_W}" height="{BAR_H}" />'
                )
                label_x = baseline_x + AMOUNT_GAP
            parts.append(
                f'<text x="{label_x:.1f}" y="{mid:.1f}" class="price-chart-amount">'
                f"{_xml(amount_label(plan))}</text>"
            )
            y += ROW_H
        y += GROUP_GAP

    if first_row_y is not None and last_row_y is not None:
        top = first_row_y - BAR_H / 2
        bottom = last_row_y + BAR_H / 2
        parts.append(
            f'<line class="price-chart-baseline" x1="{baseline_x:.1f}" y1="{top:.1f}" '
            f'x2="{baseline_x:.1f}" y2="{bottom:.1f}" />'
        )

    parts.append("</svg>")
    return "".join(parts)


def _panel_height(groups: list[tuple[VendorPage, list[Plan]]]) -> int:
    rows = sum(len(plans) for _, plans in groups)
    vendors = len(groups)
    height = PAD_Y + TITLE_H + vendors * VENDOR_H + rows * ROW_H + max(vendors - 1, 0) * GROUP_GAP
    if vendors:
        height += GROUP_GAP
    return height + PAD_Y


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
