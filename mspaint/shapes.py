# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometry for all shapes offered by the Paint shape gallery."""
from __future__ import annotations

import math

SHAPE_ORDER = [
    'line', 'curve',
    'ellipse', 'rectangle', 'rounded_rectangle', 'triangle', 'right_triangle',
    'diamond', 'pentagon', 'hexagon',
    'arrow_right', 'arrow_left', 'arrow_up', 'arrow_down',
    'star4', 'star5', 'star6',
    'rounded_callout', 'oval_callout', 'cloud_callout',
    'heart', 'lightning',
]

SHAPE_LABELS_ZH = {
    'line': '直线', 'curve': '曲线', 'ellipse': '椭圆形', 'rectangle': '矩形',
    'rounded_rectangle': '圆角矩形', 'triangle': '三角形', 'right_triangle': '直角三角形',
    'diamond': '菱形', 'pentagon': '五边形', 'hexagon': '六边形',
    'arrow_right': '向右的箭头', 'arrow_left': '向左的箭头',
    'arrow_up': '向上的箭头', 'arrow_down': '向下的箭头',
    'star4': '四角星形', 'star5': '五角星形', 'star6': '六角星形',
    'rounded_callout': '圆角矩形标注', 'oval_callout': '椭圆形插图编号',
    'cloud_callout': '云形插图编号', 'heart': '心形', 'lightning': '闪电形',
}
SHAPE_LABELS_EN = {
    'line': 'Line', 'curve': 'Curve', 'ellipse': 'Ellipse', 'rectangle': 'Rectangle',
    'rounded_rectangle': 'Rounded rectangle', 'triangle': 'Triangle', 'right_triangle': 'Right triangle',
    'diamond': 'Diamond', 'pentagon': 'Pentagon', 'hexagon': 'Hexagon',
    'arrow_right': 'Right arrow', 'arrow_left': 'Left arrow',
    'arrow_up': 'Up arrow', 'arrow_down': 'Down arrow',
    'star4': 'Four-point star', 'star5': 'Five-point star', 'star6': 'Six-point star',
    'rounded_callout': 'Rounded rectangular callout', 'oval_callout': 'Oval callout',
    'cloud_callout': 'Cloud callout', 'heart': 'Heart', 'lightning': 'Lightning',
}

# Gallery positions: the reference ribbon has three rows of six slots
GALLERY_ROWS = [
    ['line', 'curve', 'ellipse', 'rectangle', 'rounded_rectangle', 'triangle'],
    ['right_triangle', 'diamond', 'pentagon', 'hexagon', 'arrow_right', 'arrow_left'],
    ['arrow_up', 'arrow_down', 'star4', 'star5', 'star6', 'rounded_callout'],
    ['oval_callout', 'cloud_callout', 'heart', 'lightning'],
]


def _polygon(ctx, points, close=True):
    for i, (x, y) in enumerate(points):
        if i == 0:
            ctx.move_to(x, y)
        else:
            ctx.line_to(x, y)
    if close:
        ctx.close_path()


def _regular_polygon(cx, cy, rx, ry, n, start=-math.pi / 2, rotate=0.0):
    pts = []
    for i in range(n):
        a = start + rotate + i * 2 * math.pi / n
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def _star(cx, cy, rx, ry, n, inner=0.38):
    pts = []
    for i in range(n * 2):
        a = -math.pi / 2 + i * math.pi / n
        r = 1.0 if i % 2 == 0 else inner
        pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    return pts


def build_shape_path(ctx, shape: str, x: float, y: float, w: float, h: float,
                     *, corner_radius: float | None = None):
    """Append *shape* to the current Cairo path inside the given bounds."""
    x, y, w, h = float(x), float(y), float(w), float(h)
    if w == 0 or h == 0:
        return
    # normalize negative sizes
    if w < 0:
        x += w; w = -w
    if h < 0:
        y += h; h = -h
    cx, cy = x + w / 2, y + h / 2
    if shape == 'ellipse':
        ctx.save()
        ctx.translate(cx, cy)
        ctx.scale(w / 2, h / 2)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
    elif shape == 'rectangle':
        ctx.rectangle(x, y, w, h)
    elif shape == 'rounded_rectangle':
        r = min(corner_radius if corner_radius is not None else min(w, h) * 0.18,
                w / 2, h / 2)
        _rounded_rect(ctx, x, y, w, h, r)
    elif shape == 'triangle':
        _polygon(ctx, [(cx, y), (x + w, y + h), (x, y + h)])
    elif shape == 'right_triangle':
        _polygon(ctx, [(x, y), (x, y + h), (x + w, y + h)])
    elif shape == 'diamond':
        _polygon(ctx, [(cx, y), (x + w, cy), (cx, y + h), (x, cy)])
    elif shape == 'pentagon':
        _polygon(ctx, _regular_polygon(cx, cy, w / 2, h / 2, 5))
    elif shape == 'hexagon':
        _polygon(ctx, [(x + w * 0.25, y), (x + w * 0.75, y), (x + w, cy),
                       (x + w * 0.75, y + h), (x + w * 0.25, y + h), (x, cy)])
    elif shape in ('arrow_right', 'arrow_left', 'arrow_up', 'arrow_down'):
        if shape in ('arrow_right', 'arrow_left'):
            shaft = h * 0.28
            head_len = min(w * 0.38, h * 0.75)
            if shape == 'arrow_right':
                pts = [(x, cy - shaft), (x + w - head_len, cy - shaft),
                       (x + w - head_len, y), (x + w, cy),
                       (x + w - head_len, y + h), (x + w - head_len, cy + shaft),
                       (x, cy + shaft)]
            else:
                pts = [(x + w, cy - shaft), (x + head_len, cy - shaft),
                       (x + head_len, y), (x, cy), (x + head_len, y + h),
                       (x + head_len, cy + shaft), (x + w, cy + shaft)]
        else:
            shaft = w * 0.28
            head_len = min(h * 0.38, w * 0.75)
            if shape == 'arrow_down':
                pts = [(cx - shaft, y), (cx - shaft, y + h - head_len),
                       (x, y + h - head_len), (cx, y + h),
                       (x + w, y + h - head_len), (cx + shaft, y + h - head_len),
                       (cx + shaft, y)]
            else:
                pts = [(cx - shaft, y + h), (cx - shaft, y + head_len),
                       (x, y + head_len), (cx, y), (x + w, y + head_len),
                       (cx + shaft, y + head_len), (cx + shaft, y + h)]
        _polygon(ctx, pts)
    elif shape in ('star4', 'star5', 'star6'):
        n = {'star4': 4, 'star5': 5, 'star6': 6}[shape]
        inner = {'star4': 0.32, 'star5': 0.38, 'star6': 0.52}[shape]
        _polygon(ctx, _star(cx, cy, w / 2, h / 2, n, inner))
    elif shape == 'rounded_callout':
        bw = w * 0.78
        bh = h * 0.76
        _rounded_rect(ctx, x + w * 0.22, y, bw, bh, min(bw, bh) * 0.18)
        # tail
        ctx.move_to(x + w * 0.30, y + bh * 0.88)
        ctx.line_to(x + w * 0.06, y + h)
        ctx.line_to(x + w * 0.44, y + bh * 0.92)
        ctx.close_path()
    elif shape == 'oval_callout':
        bw, bh = w * 0.78, h * 0.76
        ctx.save()
        ctx.translate(x + w * 0.61, y + bh / 2)
        ctx.scale(bw / 2, bh / 2)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.move_to(x + w * 0.30, y + bh * 0.88)
        ctx.line_to(x + w * 0.06, y + h)
        ctx.line_to(x + w * 0.46, y + bh * 0.92)
        ctx.close_path()
    elif shape == 'cloud_callout':
        bw, bh = w * 0.78, h * 0.76
        _cloud(ctx, x + w * 0.22, y, bw, bh)
        ctx.move_to(x + w * 0.34, y + bh * 0.80)
        ctx.line_to(x + w * 0.06, y + h)
        ctx.line_to(x + w * 0.48, y + bh * 0.84)
        ctx.close_path()
    elif shape == 'heart':
        ctx.move_to(cx, y + h * 0.30)
        ctx.curve_to(cx + w * 0.12, y, x + w, y + h * 0.12, x + w * 0.82, y + h * 0.48)
        ctx.curve_to(x + w * 0.68, y + h * 0.72, cx + w * 0.18, y + h * 0.82, cx, y + h)
        ctx.curve_to(cx - w * 0.18, y + h * 0.82, x + w * 0.32, y + h * 0.72, x + w * 0.18, y + h * 0.48)
        ctx.curve_to(x, y + h * 0.12, cx - w * 0.12, y, cx, y + h * 0.30)
        ctx.close_path()
    elif shape == 'lightning':
        _polygon(ctx, [
            (x + w * 0.56, y), (x + w * 0.12, y + h * 0.58),
            (x + w * 0.45, y + h * 0.58), (x + w * 0.30, y + h),
            (x + w * 0.90, y + h * 0.36), (x + w * 0.55, y + h * 0.36),
            (x + w * 0.78, y),
        ])
    else:
        ctx.rectangle(x, y, w, h)


def _rounded_rect(ctx, x, y, w, h, r):
    if r <= 0:
        ctx.rectangle(x, y, w, h)
        return
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _cloud(ctx, x, y, w, h):
    # A simple Paint-like cloud from overlapping circles.  All circles are
    # subpaths so a single fill/stroke handles the union sensibly.
    circles = [
        (x + w * 0.20, y + h * 0.62, w * 0.18, h * 0.28),
        (x + w * 0.33, y + h * 0.34, w * 0.20, h * 0.30),
        (x + w * 0.53, y + h * 0.23, w * 0.22, h * 0.33),
        (x + w * 0.73, y + h * 0.38, w * 0.19, h * 0.30),
        (x + w * 0.80, y + h * 0.63, w * 0.18, h * 0.27),
        (x + w * 0.50, y + h * 0.66, w * 0.30, h * 0.31),
    ]
    for cx, cy, rx, ry in circles:
        ctx.save()
        ctx.translate(cx, cy)
        ctx.scale(rx, ry)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()


def shape_bounds(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def star_points(cx, cy, r, n=5, start=-math.pi / 2):
    return _star(cx, cy, r, r, n, 0.38)
