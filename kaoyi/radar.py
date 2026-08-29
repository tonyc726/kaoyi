from __future__ import annotations

import math

from kaoyi.models import RadarAxis, Review

# Outer ring is better. Switching-cost is inverted before drawing.
DEFAULT_MAX = 5
SIZE = 320
CENTER = SIZE / 2
RADIUS = 108


def invert_for_display(axis: RadarAxis, score: int) -> int:
    value = int(score)
    if axis.invert:
        return DEFAULT_MAX + 1 - value
    return value


def buyer_axis_values(review: Review, axes: list[RadarAxis]) -> list[int]:
    """Higher is better for the buyer. switching_cost is inverted like the radar."""
    values: list[int] = []
    for axis in axes:
        raw = review.scores.get(axis.id)
        if raw is None:
            continue
        value = int(raw)
        if not (1 <= value <= DEFAULT_MAX):
            continue
        values.append(invert_for_display(axis, value))
    return values


def radar_caption(review: Review, axes: list[RadarAxis]) -> str:
    values = buyer_axis_values(review, axes)
    if not values:
        return "未评"
    if len(values) < 3:
        return "暂无综合分"
    return f"{sum(values) / len(values):.1f} / 5"


def _point(index: int, total: int, magnitude: float) -> tuple[float, float]:
    # Start at 12 o'clock, clockwise.
    angle = -math.pi / 2 + (2 * math.pi * index / total)
    x = CENTER + RADIUS * magnitude * math.cos(angle)
    y = CENTER + RADIUS * magnitude * math.sin(angle)
    return x, y


def render_radar_svg(review: Review, axes: list[RadarAxis]) -> str:
    rings = []
    for level in range(1, DEFAULT_MAX + 1):
        pts = [_point(i, len(axes), level / DEFAULT_MAX) for i in range(len(axes))]
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        rings.append(
            f'<polygon points="{points}" class="radar-ring" data-level="{level}" />'
        )

    spokes = []
    labels = []
    for index, axis in enumerate(axes):
        x, y = _point(index, len(axes), 1.0)
        spokes.append(
            f'<line x1="{CENTER:.1f}" y1="{CENTER:.1f}" '
            f'x2="{x:.1f}" y2="{y:.1f}" class="radar-spoke" />'
        )
        lx, ly = _point(index, len(axes), 1.28)
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" class="radar-label">{_xml(axis.label)}</text>'
        )

    polygon = ""
    dots: list[str] = []
    caption = radar_caption(review, axes)
    scored_points: list[tuple[float, float]] = []
    for index, axis in enumerate(axes):
        raw = review.scores.get(axis.id)
        if raw is None:
            continue
        value = int(raw)
        if not (1 <= value <= DEFAULT_MAX):
            continue
        display = invert_for_display(axis, value)
        x, y = _point(index, len(axes), display / DEFAULT_MAX)
        scored_points.append((x, y))
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" class="radar-dot" />')

    if scored_points:
        if len(scored_points) >= 3:
            points = " ".join(f"{x:.1f},{y:.1f}" for x, y in scored_points)
            polygon = f'<polygon points="{points}" class="radar-shape" />'
        elif len(scored_points) == 2:
            (x1, y1), (x2, y2) = scored_points
            polygon = (
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" '
                f'x2="{x2:.1f}" y2="{y2:.1f}" class="radar-shape" />'
            )

    label = f"评价雷达 {caption}"
    return f"""<svg class="radar" viewBox="0 0 {SIZE} {SIZE}" role="img" aria-label="{_xml(label)}">
  <g class="radar-grid">
    {"".join(rings)}
    {"".join(spokes)}
  </g>
  {polygon}
  {"".join(dots)}
  {"".join(labels)}
  <text x="{CENTER:.1f}" y="{CENTER + 4:.1f}" class="radar-caption">{_xml(caption)}</text>
</svg>"""


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
