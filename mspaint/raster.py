# SPDX-License-Identifier: GPL-3.0-or-later
"""Raster drawing primitives, brushes, fills and shape rendering."""
from __future__ import annotations

import math
import random
from collections import deque

import cairo

from .shapes import build_shape_path


# Palette used by ms-paint (20 colours, two rows of 10).
DEFAULT_PALETTE = [
    '#000000', '#7F7F7F', '#880015', '#ED1C24', '#FF7F27',
    '#FFF200', '#22B14C', '#00A2E8', '#3F48CC', '#A349A4',
    '#FFFFFF', '#C3C3C3', '#B97A57', '#FFAEC9', '#FFC90E',
    '#EFE4B0', '#B5E61D', '#99D9EA', '#7092BE', '#C8BFE7',
]

BRUSH_LABELS = {
    'brush': ('刷子', 'Brush'),
    'calligraphy1': ('书法笔刷 1', 'Calligraphy brush 1'),
    'calligraphy2': ('书法笔刷 2', 'Calligraphy brush 2'),
    'airbrush': ('喷枪', 'Airbrush'),
    'paintbrush': ('颜料刷', 'Paintbrush'),
    'crayon': ('蜡笔', 'Crayon'),
    'marker': ('记号笔', 'Marker'),
    'pencil': ('普通铅笔', 'Regular pencil'),
    'watercolor': ('水彩笔刷', 'Watercolor brush'),
}
BRUSH_ORDER = list(BRUSH_LABELS)
LINE_WIDTHS = [1, 2, 3, 4, 5, 6, 8, 10, 16, 24, 30, 40]
SHAPE_OUTLINE_STYLES = {
    'none': ('无轮廓', 'No outline'),
    'solid': ('实线', 'Solid color'),
    'crayon': ('蜡笔', 'Crayon'),
    'marker': ('记号笔', 'Marker'),
    'oil': ('油画笔', 'Oil'),
    'pencil': ('普通铅笔', 'Natural pencil'),
    'watercolor': ('水彩', 'Watercolor'),
}
SHAPE_FILL_STYLES = {
    'none': ('无填充', 'No fill'),
    'solid': ('纯色', 'Solid color'),
    'crayon': ('蜡笔', 'Crayon'),
    'marker': ('记号笔', 'Marker'),
    'oil': ('油画笔', 'Oil'),
    'pencil': ('普通铅笔', 'Natural pencil'),
    'watercolor': ('水彩', 'Watercolor'),
}


def rgb(rgb_tuple, alpha=1.0):
    return (rgb_tuple[0] / 255.0, rgb_tuple[1] / 255.0, rgb_tuple[2] / 255.0, alpha)


def _lerp(a, b, t):
    return a + (b - a) * t


def stroke_segment(ctx, p0, p1, color_rgb, width, brush='brush', *, seed=0, alpha=1.0):
    """Draw one brush segment.  The caller has already configured the context."""
    x0, y0 = p0
    x1, y1 = p1
    rng = random.Random((seed * 1315423911) ^ (int(x0) * 73856093) ^ (int(y0) * 19349663))
    ctx.save()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    w = max(0.5, float(width))
    if brush == 'pencil':
        ctx.set_line_width(max(0.7, w * 0.25))
        ctx.set_source_rgba(*color_rgb, alpha)
        ctx.move_to(*p0); ctx.line_to(*p1); ctx.stroke()
    elif brush == 'calligraphy1':
        _stamp_rotated(ctx, p0, p1, color_rgb, w, -math.pi / 4, alpha)
    elif brush == 'calligraphy2':
        _stamp_rotated(ctx, p0, p1, color_rgb, w, math.pi / 4, alpha)
    elif brush == 'airbrush':
        dist = max(1.0, math.hypot(x1 - x0, y1 - y0))
        n = max(3, int(dist * (w / 3.0)) + 2)
        for _ in range(n):
            t = rng.random()
            cx = _lerp(x0, x1, t) + rng.uniform(-1, 1) * w * 0.7
            cy = _lerp(y0, y1, t) + rng.uniform(-1, 1) * w * 0.7
            rr = rng.uniform(0.35, max(0.7, w * 0.18))
            ctx.set_source_rgba(*color_rgb, alpha * rng.uniform(0.25, 0.8))
            ctx.arc(cx, cy, rr, 0, 2 * math.pi)
            ctx.fill()
    elif brush == 'paintbrush':
        # A bundle of bristles with uneven ends.
        strokes = max(3, int(w / 2.5))
        for i in range(strokes):
            off = (i - (strokes - 1) / 2) * (w / max(4, strokes))
            nx, ny = (-(y1 - y0), x1 - x0)
            ln = math.hypot(nx, ny) or 1
            jx = nx / ln * off + rng.uniform(-0.7, 0.7)
            jy = ny / ln * off + rng.uniform(-0.7, 0.7)
            ctx.set_source_rgba(*color_rgb, alpha * rng.uniform(0.55, 1.0))
            ctx.set_line_width(max(0.6, rng.uniform(0.55, 1.25)))
            ctx.move_to(x0 + jx, y0 + jy)
            ctx.line_to(x1 + jx, y1 + jy)
            ctx.stroke()
    elif brush == 'crayon':
        n = max(2, int(w / 2))
        for _ in range(n):
            j = rng.uniform(-w / 2, w / 2)
            ctx.set_source_rgba(*color_rgb, alpha * rng.uniform(0.35, 0.8))
            ctx.set_line_width(max(0.5, w * 0.16))
            nx, ny = (-(y1 - y0), x1 - x0)
            ln = math.hypot(nx, ny) or 1
            ctx.move_to(x0 + nx / ln * j, y0 + ny / ln * j)
            ctx.line_to(x1 + nx / ln * j + rng.uniform(-1, 1),
                        y1 + ny / ln * j + rng.uniform(-1, 1))
            ctx.stroke()
    elif brush == 'marker':
        ctx.set_line_width(w)
        ctx.set_source_rgba(*color_rgb, alpha * 0.62)
        ctx.move_to(*p0); ctx.line_to(*p1); ctx.stroke()
        ctx.set_line_width(max(1.0, w * 0.65))
        ctx.set_source_rgba(*color_rgb, alpha * 0.55)
        ctx.move_to(*p0); ctx.line_to(*p1); ctx.stroke()
    elif brush == 'watercolor':
        ctx.set_source_rgba(*color_rgb, alpha * 0.16)
        ctx.set_line_width(w * 1.5)
        ctx.move_to(*p0); ctx.line_to(*p1); ctx.stroke()
        for _ in range(2):
            ctx.set_source_rgba(*color_rgb, alpha * 0.10)
            ox = rng.uniform(-w * 0.35, w * 0.35)
            oy = rng.uniform(-w * 0.35, w * 0.35)
            ctx.arc(_lerp(x0, x1, 0.5) + ox, _lerp(y0, y1, 0.5) + oy,
                    rng.uniform(w * 0.35, w * 0.8), 0, 2 * math.pi)
            ctx.fill()
    else:  # standard round brush
        ctx.set_line_width(w)
        ctx.set_source_rgba(*color_rgb, alpha)
        ctx.move_to(*p0); ctx.line_to(*p1); ctx.stroke()
        # Slight edge texture so the standard brush does not look like the pencil.
        if w >= 4:
            ctx.set_line_width(max(1.0, w * 0.42))
            ctx.set_source_rgba(*color_rgb, alpha * 0.35)
            ctx.move_to(x0, y0); ctx.line_to(x1, y1); ctx.stroke()
    ctx.restore()


def _stamp_rotated(ctx, p0, p1, color, width, angle, alpha):
    ctx.save()
    ctx.set_source_rgba(*color, alpha)
    ctx.set_line_width(max(0.7, width * 0.35))
    ctx.move_to(*p0); ctx.line_to(*p1); ctx.stroke()
    # Slanted chisel tip stamps along the segment.
    dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    steps = max(1, int(dist / max(1.0, width * 0.35)))
    for i in range(steps + 1):
        t = i / steps
        cx = _lerp(p0[0], p1[0], t)
        cy = _lerp(p0[1], p1[1], t)
        ctx.save()
        ctx.translate(cx, cy)
        ctx.rotate(angle)
        ctx.scale(width * 0.52, width * 0.22)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.fill()
    ctx.restore()


def draw_freehand(ctx, points, color, width, brush='brush', seed=0):
    if len(points) == 1:
        points = [points[0], (points[0][0] + 0.01, points[0][1] + 0.01)]
    for i in range(len(points) - 1):
        stroke_segment(ctx, points[i], points[i + 1], color, width, brush, seed=seed + i)


def draw_pixel_line(surface: cairo.ImageSurface, x0, y0, x1, y1, color_rgb):
    """Draw a crisp one-pixel Bresenham line directly into an ARGB32 surface.

    Used by the pencil at 1 px so a click changes exactly the pixel under the
    pointer and a drag has no anti-aliased fringe.
    """
    import math as _math
    w, h = surface.get_width(), surface.get_height()
    x0, y0 = int(_math.floor(x0)), int(_math.floor(y0))
    x1, y1 = int(_math.floor(x1)), int(_math.floor(y1))
    surface.flush()
    stride = surface.get_stride()
    data = surface.get_data()
    px = (max(0, min(255, int(round(color_rgb[2] * 255)))),
          max(0, min(255, int(round(color_rgb[1] * 255)))),
          max(0, min(255, int(round(color_rgb[0] * 255)))), 255)
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < w and 0 <= y0 < h:
            off = y0 * stride + x0 * 4
            data[off:off + 4] = bytes(px)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    surface.mark_dirty()


def bucket_fill(surface: cairo.ImageSurface, x: int, y: int, color_rgb, tolerance=0,
                alpha=1.0):
    """Scanline flood fill with exact / tolerance matching on ARGB32."""
    w, h = surface.get_width(), surface.get_height()
    if x < 0 or y < 0 or x >= w or y >= h:
        return False
    surface.flush()
    stride = surface.get_stride()
    data = surface.get_data()
    target = tuple(data[y * stride + x * 4:y * stride + x * 4 + 4])
    a = max(0, min(255, int(round(alpha * 255))))
    # Cairo stores premultiplied BGRA data.
    new = (int(color_rgb[2] * 255 + 0.5) * a // 255,
           int(color_rgb[1] * 255 + 0.5) * a // 255,
           int(color_rgb[0] * 255 + 0.5) * a // 255,
           a)
    if target == new:
        return False

    def matches(off):
        return (abs(data[off] - target[0]) <= tolerance
                and abs(data[off + 1] - target[1]) <= tolerance
                and abs(data[off + 2] - target[2]) <= tolerance
                and abs(data[off + 3] - target[3]) <= tolerance)

    seen = bytearray(w * h)
    stack = deque([(x, y)])
    while stack:
        cx, cy = stack.pop()
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            continue
        idx = cy * w + cx
        if seen[idx]:
            continue
        off = cy * stride + cx * 4
        if not matches(off):
            continue
        # scan left and right on this row
        left = cx
        while left > 0:
            o = cy * stride + (left - 1) * 4
            if seen[cy * w + left - 1] or not matches(o):
                break
            left -= 1
        right = cx
        while right < w - 1:
            o = cy * stride + (right + 1) * 4
            if seen[cy * w + right + 1] or not matches(o):
                break
            right += 1
        for px in range(left, right + 1):
            seen[cy * w + px] = 1
            off = cy * stride + px * 4
            data[off] = new[0]
            data[off + 1] = new[1]
            data[off + 2] = new[2]
            data[off + 3] = new[3]
            if cy > 0:
                oo = (cy - 1) * stride + px * 4
                if not seen[(cy - 1) * w + px] and matches(oo):
                    stack.append((px, cy - 1))
            if cy < h - 1:
                oo = (cy + 1) * stride + px * 4
                if not seen[(cy + 1) * w + px] and matches(oo):
                    stack.append((px, cy + 1))
    surface.mark_dirty()
    return True


def fill_shape(ctx, shape, x, y, w, h, fill_style, fill_color, outline_style,
               outline_color, line_width, *, alpha=1.0, corner_radius=None):
    """Render a shape with Paint's outline/fill styles."""
    if fill_style != 'none':
        ctx.save()
        ctx.new_path()
        build_shape_path(ctx, shape, x, y, w, h, corner_radius=corner_radius)
        if fill_style == 'solid':
            ctx.set_source_rgba(*fill_color, alpha)
            ctx.fill_preserve()
        else:
            ctx.clip_preserve()
            _style_fill(ctx, shape, x, y, w, h, fill_style, fill_color, alpha)
            ctx.new_path()
            build_shape_path(ctx, shape, x, y, w, h, corner_radius=corner_radius)
        ctx.restore()
    if outline_style != 'none':
        ctx.save()
        ctx.new_path()
        build_shape_path(ctx, shape, x, y, w, h, corner_radius=corner_radius)
        ctx.set_line_width(max(0.8, line_width))
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        if outline_style == 'solid':
            ctx.set_source_rgba(*outline_color, alpha)
            ctx.stroke()
        else:
            _style_stroke_path(ctx, outline_style, outline_color, line_width, alpha)
        ctx.restore()


def _style_fill(ctx, shape, x, y, w, h, style, color, alpha):
    ctx.save()
    if style == 'watercolor':
        # Soft washes clipped inside the shape.
        rng = random.Random(int(x + y * 3 + w * 7 + h * 11))
        for _ in range(30):
            cx = x + rng.random() * w
            cy = y + rng.random() * h
            r = rng.uniform(4, max(8, min(w, h) * 0.22))
            grad = cairo.RadialGradient(cx, cy, 0, cx, cy, r)
            grad.add_color_stop_rgba(0, *color, alpha * 0.18)
            grad.add_color_stop_rgba(1, *color, 0)
            ctx.set_source(grad)
            ctx.arc(cx, cy, r, 0, 2 * math.pi)
            ctx.fill()
    elif style == 'crayon':
        rng = random.Random(int(x * 5 + y * 13 + w + h * 3))
        for _ in range(140):
            px, py = x + rng.random() * w, y + rng.random() * h
            ctx.set_source_rgba(*color, alpha * rng.uniform(0.15, 0.55))
            ctx.arc(px, py, rng.uniform(0.5, 1.4), 0, 2 * math.pi)
            ctx.fill()
    elif style == 'marker':
        ctx.set_source_rgba(*color, alpha * 0.35)
        ctx.paint()
    elif style == 'pencil':
        rng = random.Random(int(x + y * 2 + w * 3))
        for _ in range(100):
            px = x + rng.random() * w
            py = y + rng.random() * h
            ctx.set_source_rgba(*color, alpha * rng.uniform(0.2, 0.65))
            ctx.rectangle(px, py, rng.uniform(0.6, 1.6), 1)
            ctx.fill()
    elif style == 'oil':
        rng = random.Random(int(x * 2 + y * 7 + w))
        for _ in range(60):
            px, py = x + rng.random() * w, y + rng.random() * h
            ctx.set_source_rgba(*color, alpha * rng.uniform(0.2, 0.5))
            ctx.save()
            ctx.translate(px, py)
            ctx.rotate(rng.random() * math.pi)
            ctx.scale(rng.uniform(2, 8), rng.uniform(0.6, 1.8))
            ctx.arc(0, 0, 1, 0, 2 * math.pi)
            ctx.restore()
            ctx.fill()
    else:
        ctx.set_source_rgba(*color, alpha * 0.5)
        ctx.paint()
    ctx.restore()


def _style_stroke_path(ctx, style, color, width, alpha):
    ctx.set_line_width(max(0.8, width))
    if style == 'marker':
        ctx.set_source_rgba(*color, alpha * 0.5)
        ctx.stroke_preserve()
        ctx.set_line_width(max(1, width * 0.5))
        ctx.set_source_rgba(*color, alpha * 0.8)
        ctx.stroke()
    elif style == 'watercolor':
        for i in range(3):
            ctx.set_line_width(max(1, width * (1 + i * 0.45)))
            ctx.set_source_rgba(*color, alpha * (0.18 + i * 0.07))
            ctx.stroke_preserve()
        ctx.new_path()
    elif style in ('crayon', 'pencil'):
        ctx.set_source_rgba(*color, alpha * 0.7)
        ctx.set_dash([1.5, 1.8])
        ctx.stroke()
        ctx.set_dash([])
    elif style == 'oil':
        ctx.set_line_width(max(1, width * 1.2))
        ctx.set_source_rgba(*color, alpha * 0.75)
        ctx.stroke()
    else:
        ctx.set_source_rgba(*color, alpha)
        ctx.stroke()


def draw_curve(ctx, p0, p1, c1, c2, color, width, outline_style='solid', alpha=1.0):
    ctx.save()
    ctx.move_to(*p0)
    ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p1[0], p1[1])
    ctx.set_line_width(max(0.8, width))
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    if outline_style == 'solid':
        ctx.set_source_rgba(*color, alpha)
        ctx.stroke()
    else:
        _style_stroke_path(ctx, outline_style, color, width, alpha)
    ctx.restore()


def draw_eraser(ctx, x, y, size, color, clear=False):
    ctx.save()
    rgba = tuple(color)
    if len(rgba) == 3:
        rgba = rgba + (1.0,)
    if clear or rgba[3] <= 0:
        # Erase to full transparency instead of painting the background colour.
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.set_source_rgba(0, 0, 0, 0)
    else:
        ctx.set_source_rgba(*rgba)
    ctx.rectangle(round(x - size / 2), round(y - size / 2), size, size)
    ctx.fill()
    ctx.restore()


def pick_color(surface, x, y):
    w, h = surface.get_width(), surface.get_height()
    if not (0 <= x < w and 0 <= y < h):
        return None
    surface.flush()
    stride = surface.get_stride()
    data = surface.get_data()
    off = int(y) * stride + int(x) * 4
    b, g, r, a = data[off], data[off + 1], data[off + 2], data[off + 3]
    if 0 < a < 255:
        # Return the straight (un-premultiplied) colour and its alpha.
        r = min(255, (r * 255 + a // 2) // a)
        g = min(255, (g * 255 + a // 2) // a)
        b = min(255, (b * 255 + a // 2) // a)
    elif a == 0:
        return (0, 0, 0, 0)
    return (r, g, b, a)
