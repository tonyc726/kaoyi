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
    caption = "未评"
    if not review.is_placeholder:
        display_scores: list[int] = []
        complete = True
        for axis in axes:
            raw = review.scores.get(axis.id)
            if raw is None or not (1 <= int(raw) <= DEFAULT_MAX):
                complete = False
                break
            display_scores.append(invert_for_display(axis, int(raw)))
        if complete:
            pts = [
                _point(i, len(axes), score / DEFAULT_MAX)
                for i, score in enumerate(display_scores)
            ]
            points = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            polygon = f'<polygon points="{points}" class="radar-shape" />'
            caption = "编辑维度 · 无总分"

    label = f"评价雷达 {caption}"
    return f"""<svg class="radar" viewBox="0 0 {SIZE} {SIZE}" role="img" aria-label="{_xml(label)}">
  <g class="radar-grid">
    {"".join(rings)}
    {"".join(spokes)}
  </g>
  {polygon}
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
