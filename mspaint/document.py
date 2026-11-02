# SPDX-License-Identifier: GPL-3.0-or-later
"""Document, selection, history and raster file I/O for the Paint clone."""
from __future__ import annotations

import copy
import io
import math
import os
from dataclasses import dataclass, field

import cairo
from PIL import Image, ImageOps


def _copy_surface(surface: cairo.ImageSurface) -> cairo.ImageSurface:
    w, h = surface.get_width(), surface.get_height()
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(out)
    ctx.set_source_surface(surface, 0, 0)
    ctx.paint()
    return out


def normalize_rgba(color) -> tuple[float, float, float, float]:
    """Return a Cairo-friendly RGBA tuple, accepting RGB or RGBA input."""
    values = tuple(float(v) for v in color)
    if len(values) == 3:
        values += (1.0,)
    if len(values) < 3:
        values = (0.0, 0.0, 0.0, 1.0)
    return tuple(max(0.0, min(1.0, v)) for v in values[:4])  # type: ignore[return-value]


def is_transparent_color(color) -> bool:
    values = normalize_rgba(color)
    return values[3] <= 0.0


def new_surface(width: int, height: int, color=(1, 1, 1, 1)) -> cairo.ImageSurface:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, int(width)), max(1, int(height)))
    ctx = cairo.Context(surface)
    ctx.set_source_rgba(*normalize_rgba(color))
    ctx.paint()
    return surface


def clear_surface(surface: cairo.ImageSurface, color=(1, 1, 1, 1)) -> None:
    ctx = cairo.Context(surface)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_SOURCE)
    ctx.set_source_rgba(*normalize_rgba(color))
    ctx.paint()
    ctx.restore()


def surface_has_transparency(surface: cairo.ImageSurface, threshold: int = 254) -> bool:
    """Return True when any pixel in *surface* has alpha below *threshold*."""
    surface.flush()
    width, height = surface.get_width(), surface.get_height()
    stride = surface.get_stride()
    data = surface.get_data()
    if stride == width * 4:
        # Fast path: walk a single contiguous byte array.
        for off in range(3, len(data), 4):
            if data[off] <= threshold:
                return True
    else:
        for y in range(height):
            off = y * stride + 3
            end = off + width * 4
            while off < end:
                if data[off] <= threshold:
                    return True
                off += 4
    return False


surface_has_alpha = surface_has_transparency


def pil_has_transparency(im: Image.Image) -> bool:
    """Return True if a Pillow image has an alpha channel/key with real alpha."""
    if im.mode in ('RGBA', 'LA', 'PA') or 'A' in im.getbands():
        try:
            alpha = im.getchannel('A')
            low, _high = alpha.getextrema()
            return low < 255
        except Exception:
            return True
    info = getattr(im, 'info', {}) or {}
    if info.get('transparency') is not None:
        # Palette/index transparency is meaningful even without an A band.
        return im.mode in ('P', 'L', 'RGB', '1')
    return False


image_has_transparency = pil_has_transparency


def _flatten_pil_on_color(im: Image.Image, color=(255, 255, 255)) -> Image.Image:
    """Composite a Pillow image over an opaque colour and return RGB."""
    rgba = im.convert('RGBA')
    values = list(color[:3])
    if any(isinstance(v, float) and v <= 1.0 for v in values):
        values = [round(v * 255) for v in values]
    values = [max(0, min(255, int(round(v)))) for v in values]
    background = Image.new('RGBA', rgba.size, tuple(values) + (255,))
    return Image.alpha_composite(background, rgba).convert('RGB')


def rgb_to_float(rgb) -> tuple[float, float, float]:
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def rgba_to_hex(rgba) -> str:
    return "#%02X%02X%02X" % (int(rgba[0]), int(rgba[1]), int(rgba[2]))


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip('#')
    if len(value) == 3:
        value = ''.join(c * 2 for c in value)
    if len(value) != 6:
        raise ValueError(value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


@dataclass
class Selection:
    """A selection region in image coordinates.

    Rectangular selections use *rect* only.  Free-form selections carry a
    polygon path.  ``inverted`` means the selected region is the image minus
    the shape.  ``floating`` is true while the selected pixels are lifted.
    """
    x: int
    y: int
    w: int
    h: int
    polygon: list[tuple[float, float]] | None = None
    inverted: bool = False
    mask: cairo.ImageSurface | None = None
    floating: cairo.ImageSurface | None = None
    floating_origin: tuple[int, int] | None = None

    @property
    def rect(self):
        return (int(self.x), int(self.y), int(self.w), int(self.h))

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h

    @property
    def empty(self):
        return self.w <= 0 or self.h <= 0

    def contains(self, x: float, y: float) -> bool:
        x, y = float(x), float(y)
        if self.floating is not None and self.floating_origin is not None:
            bx, by = self.floating_origin
            bw, bh = self.floating.get_width(), self.floating.get_height()
        else:
            bx, by = self.x, self.y
            bw, bh = self.w, self.h
        in_bounds = bx <= x < bx + bw and by <= y < by + bh
        if self.polygon:
            if self.floating is not None and self.floating_origin is not None:
                dx, dy = bx - self.x, by - self.y
                poly = [(px + dx, py + dy) for px, py in self.polygon]
            else:
                poly = self.polygon
            inside_shape = _point_in_polygon(x, y, poly) and in_bounds
        else:
            inside_shape = in_bounds
        if not self.inverted and not in_bounds:
            return False
        return (not inside_shape) if self.inverted else inside_shape

    def clone(self) -> 'Selection':
        return copy.copy(self)

    def mask_surface(self, width: int, height: int) -> cairo.ImageSurface:
        """Return an A8 mask covering the whole image."""
        mask = cairo.ImageSurface(cairo.FORMAT_A8, width, height)
        ctx = cairo.Context(mask)
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()
        ctx.set_source_rgba(0, 0, 0, 1)
        if self.polygon:
            ctx.new_path()
            for i, (px, py) in enumerate(self.polygon):
                if i == 0:
                    ctx.move_to(px, py)
                else:
                    ctx.line_to(px, py)
            ctx.close_path()
            ctx.fill()
        else:
            ctx.rectangle(self.x, self.y, self.w, self.h)
            ctx.fill()
        if self.inverted:
            invert = cairo.ImageSurface(cairo.FORMAT_A8, width, height)
            ictx = cairo.Context(invert)
            ictx.set_source_rgba(0, 0, 0, 1)
            ictx.paint()
            ictx.set_operator(cairo.OPERATOR_DEST_OUT)
            ictx.set_source_surface(mask, 0, 0)
            ictx.paint()
            mask = invert
        return mask


def _point_in_polygon(x, y, points):
    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


@dataclass
class Snapshot:
    surface: cairo.ImageSurface
    width: int
    height: int
    selection: Selection | None
    label: str = ''
    background: tuple = (1.0, 1.0, 1.0, 1.0)


class Document:
    """A Paint document with undo/redo and selection operations."""

    def __init__(self, width=768, height=432, *, background=(1, 1, 1, 1), dpi=96,
                 transparent=False):
        self.width = int(width)
        self.height = int(height)
        self.dpi = dpi
        self.background = normalize_rgba(background)
        if transparent:
            self.background = self.background[:3] + (0.0,)
        self.surface = new_surface(self.width, self.height, self.background)
        self.filename: str | None = None
        self.format: str | None = None
        self.dirty = False
        self.selection: Selection | None = None
        self.undo_stack: list[Snapshot] = []
        self.redo_stack: list[Snapshot] = []
        self.max_undo = 50
        self.metadata: dict = {'transparent': self.transparent}
        self.palette: list[str] = []

    # ------------------------------------------------------------------
    # Transparency state
    @property
    def transparent(self) -> bool:
        """Whether new/cleared pixels use a transparent background."""
        return self.background[3] <= 0.0

    @transparent.setter
    def transparent(self, value: bool) -> None:
        value = bool(value)
        if hasattr(self, 'surface'):
            if value != self.transparent:
                self.set_transparency(value)
            return
        r, g, b, _a = self.background
        self.background = (r, g, b, 0.0 if value else 1.0)

    @property
    def is_transparent(self) -> bool:
        return self.transparent

    @is_transparent.setter
    def is_transparent(self, value: bool) -> None:
        self.transparent = value

    @property
    def transparent_background(self) -> bool:
        return self.transparent

    @transparent_background.setter
    def transparent_background(self, value: bool) -> None:
        self.transparent = value

    @property
    def has_alpha(self) -> bool:
        """Whether the image currently contains any non-opaque pixels."""
        return self.transparent or surface_has_transparency(self.surface)

    @property
    def has_transparency(self) -> bool:
        return self.has_alpha

    # ------------------------------------------------------------------
    # History
    def snapshot(self, label='') -> Snapshot:
        return Snapshot(_copy_surface(self.surface), self.width, self.height,
                        self.selection.clone() if self.selection else None, label,
                        self.background)

    def push_undo(self, label='') -> None:
        self.undo_stack.append(self.snapshot(label))
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.dirty = True

    def can_undo(self):
        return bool(self.undo_stack)

    def can_redo(self):
        return bool(self.redo_stack)

    def undo(self):
        if not self.undo_stack:
            return False
        current = self.snapshot('redo')
        snap = self.undo_stack.pop()
        self._restore(snap)
        self.redo_stack.append(current)
        self.dirty = True
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        current = self.snapshot('undo')
        snap = self.redo_stack.pop()
        self._restore(snap)
        self.undo_stack.append(current)
        self.dirty = True
        return True

    def _restore(self, snap: Snapshot):
        self.surface = _copy_surface(snap.surface)
        self.width, self.height = snap.width, snap.height
        self.selection = snap.selection.clone() if snap.selection else None
        self.background = normalize_rgba(snap.background)
        self.metadata['transparent'] = self.transparent

    # ------------------------------------------------------------------
    # Transparency operations
    def _make_color_transparent(self, color: tuple[float, float, float], tolerance: int = 0) -> None:
        """Turn opaque pixels matching *color* into fully transparent pixels."""
        self.surface.flush()
        width, height = self.surface.get_width(), self.surface.get_height()
        stride = self.surface.get_stride()
        data = self.surface.get_data()
        target = tuple(int(round(v * 255)) for v in color[:3])
        for y in range(height):
            base = y * stride
            for x in range(width):
                off = base + x * 4
                alpha = data[off + 3]
                if alpha == 0:
                    continue
                if alpha == 255:
                    r, g, b = data[off + 2], data[off + 1], data[off]
                else:
                    # Compare straight (un-premultiplied) colours so the
                    # anti-aliased fringe around letters and shapes disappears
                    # together with the background.
                    r = min(255, (data[off + 2] * 255 + alpha // 2) // alpha)
                    g = min(255, (data[off + 1] * 255 + alpha // 2) // alpha)
                    b = min(255, (data[off] * 255 + alpha // 2) // alpha)
                if (abs(r - target[0]) <= tolerance
                        and abs(g - target[1]) <= tolerance
                        and abs(b - target[2]) <= tolerance):
                    data[off] = data[off + 1] = data[off + 2] = data[off + 3] = 0
        self.surface.mark_dirty()

    def flatten_alpha(self, color=None) -> None:
        """Composite the image over an opaque background colour."""
        if color is None:
            r, g, b, _a = self.background
            color = (r, g, b, 1.0)
        color = normalize_rgba(color)
        if color[3] <= 0:
            return
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
        ctx = cairo.Context(out)
        ctx.set_source_rgba(*color)
        ctx.paint()
        ctx.set_source_surface(self.surface, 0, 0)
        ctx.paint()
        self.surface = out
        self.dirty = True

    def set_transparency(self, enabled: bool, *, background=None, clear=True,
                         label='透明背景') -> bool:
        """Enable/disable a transparent background.

        When enabling, opaque pixels matching the current background colour are
        punched out (so clearing a white canvas produces a transparent image).
        Disabling composites the image over an opaque background.
        """
        enabled = bool(enabled)
        if enabled == self.transparent:
            return False
        self.push_undo(label)
        if enabled:
            old = self.background
            target_rgb = (old[0], old[1], old[2])
            self.background = target_rgb + (0.0,)
            if clear:
                self._make_color_transparent(target_rgb)
        else:
            self.background = self.background[:3] + (1.0,)
            if background is not None:
                self.background = normalize_rgba(background)
            self.flatten_alpha(self.background)
        self.metadata['transparent'] = self.transparent
        self.dirty = True
        return True

    # ------------------------------------------------------------------
    # Geometry and whole-image operations
    def replace_surface(self, surface, *, push=True, label=''):
        if push:
            self.push_undo(label or '替换图像')
        self.surface = surface
        self.width = surface.get_width()
        self.height = surface.get_height()
        self.dirty = True

    def resize(self, width, height, *, interpolation='good', label='调整大小'):
        width, height = max(1, int(round(width))), max(1, int(round(height)))
        if width == self.width and height == self.height:
            return False
        self.push_undo(label)
        if self.selection:
            self._resize_selection(width, height, interpolation)
        else:
            out = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
            ctx = cairo.Context(out)
            ctx.scale(width / self.width, height / self.height)
            if interpolation == 'nearest':
                ctx.get_target()
                pattern = cairo.SurfacePattern(self.surface)
                pattern.set_filter(cairo.FILTER_NEAREST)
                pattern.set_extend(cairo.EXTEND_NONE)
                ctx.set_source(pattern)
            else:
                pattern = cairo.SurfacePattern(self.surface)
                pattern.set_filter(cairo.FILTER_GOOD)
                pattern.set_extend(cairo.EXTEND_NONE)
                ctx.set_source(pattern)
            ctx.paint()
            self.surface = out
            self.width, self.height = width, height
        self.dirty = True
        return True

    def _resize_selection(self, new_w, new_h, interpolation):
        sel = self.selection
        if not sel:
            return
        sx, sy, sw, sh = sel.rect
        if sw <= 0 or sh <= 0:
            return
        target = cairo.ImageSurface(cairo.FORMAT_ARGB32, new_w, new_h)
        tctx = cairo.Context(target)
        # resize the whole image, then restore the transformed selection.
        full = cairo.ImageSurface(cairo.FORMAT_ARGB32, new_w, new_h)
        fctx = cairo.Context(full)
        nw = max(1, round(self.width * new_w / self.width))
        # Actually keep document dimensions and scale only the selected region.
        fctx.scale(1, 1)
        fctx.set_source_surface(self.surface, 0, 0)
        fctx.paint()
        if sw and sh:
            piece = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
            pctx = cairo.Context(piece)
            pctx.set_source_surface(self.surface, -sx, -sy)
            pctx.paint()
            # mask according to selection shape
            if sel.polygon or sel.inverted:
                mask = sel.mask_surface(self.width, self.height)
                crop = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
                cctx = cairo.Context(crop)
                cctx.set_source_surface(piece, 0, 0)
                cctx.paint()
                cctx.set_operator(cairo.OPERATOR_DEST_IN)
                cctx.set_source_surface(mask, -sx, -sy)
                cctx.paint()
                piece = crop
            nsw, nsh = max(1, round(new_w)), max(1, round(new_h))
            ctx = cairo.Context(full)
            if self.transparent:
                ctx.set_operator(cairo.OPERATOR_CLEAR)
                ctx.rectangle(sx, sy, sw, sh)
                ctx.fill()
            else:
                ctx.set_operator(cairo.OPERATOR_SOURCE)
                ctx.set_source_rgba(*self.background)
                ctx.rectangle(sx, sy, sw, sh)
                ctx.fill()
            ctx.set_operator(cairo.OPERATOR_OVER)
            ctx.save()
            ctx.rectangle(sx, sy, nsw, nsh)
            ctx.clip()
            ctx.translate(sx, sy)
            ctx.scale(nsw / sw, nsh / sh)
            pat = cairo.SurfacePattern(piece)
            pat.set_filter(cairo.FILTER_GOOD if interpolation != 'nearest' else cairo.FILTER_NEAREST)
            ctx.set_source(pat)
            ctx.paint()
            ctx.restore()
            self.surface = full
            self.width, self.height = new_w, new_h
            self.selection = Selection(sx, sy, nsw, nsh)

    def resize_canvas(self, width, height, *, label='属性'):
        width, height = max(1, int(width)), max(1, int(height))
        if width == self.width and height == self.height:
            return False
        self.push_undo(label)
        out = new_surface(width, height, self.background)
        ctx = cairo.Context(out)
        ctx.set_source_surface(self.surface, 0, 0)
        ctx.paint()
        self.surface = out
        self.width, self.height = width, height
        self.selection = None
        self.dirty = True
        return True

    def crop(self):
        sel = self.selection
        if not sel or sel.empty:
            return False
        x, y, w, h = sel.rect
        x = max(0, x); y = max(0, y)
        w = min(w, self.width - x); h = min(h, self.height - y)
        if w <= 0 or h <= 0:
            return False
        self.push_undo('裁剪')
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(out)
        ctx.set_source_surface(self.surface, -x, -y)
        ctx.paint()
        self.surface = out
        self.width, self.height = w, h
        self.selection = None
        self.dirty = True
        return True

    def rotate(self, mode: str):
        """mode: right, left, 180, flip_v, flip_h. Applies to selection if present."""
        if mode not in ('right', 'left', '180', 'flip_v', 'flip_h'):
            raise ValueError(mode)
        self.push_undo('旋转或翻转')
        if self.selection and not self.selection.empty:
            sel = self.selection
            x, y, w, h = sel.rect
            x, y = max(0, x), max(0, y)
            w, h = min(w, self.width - x), min(h, self.height - y)
            piece = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            pctx = cairo.Context(piece)
            pctx.set_source_surface(self.surface, -x, -y)
            pctx.paint()
            transformed = self._transform_surface(piece, mode)
            tw, th = transformed.get_width(), transformed.get_height()
            ctx = cairo.Context(self.surface)
            ctx.save()
            if self.transparent:
                ctx.set_operator(cairo.OPERATOR_CLEAR)
                ctx.rectangle(x, y, w, h)
                ctx.fill()
            else:
                ctx.set_operator(cairo.OPERATOR_SOURCE)
                ctx.set_source_rgba(*self.background)
                ctx.rectangle(x, y, w, h)
                ctx.fill()
            ctx.restore()
            if self.selection.polygon or self.selection.inverted:
                mask = sel.mask_surface(self.width, self.height)
                masked = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
                mctx = cairo.Context(masked)
                mctx.set_source_surface(piece, 0, 0)
                mctx.paint()
                mctx.set_operator(cairo.OPERATOR_DEST_IN)
                mctx.set_source_surface(mask, -x, -y)
                mctx.paint()
                piece = masked
                transformed = self._transform_surface(piece, mode)
            ctx.set_source_surface(transformed, x, y)
            ctx.paint()
            self.selection = Selection(x, y, tw, th)
        else:
            self.surface = self._transform_surface(self.surface, mode)
            self.width, self.height = self.surface.get_width(), self.surface.get_height()
            self.selection = None
        self.dirty = True

    @staticmethod
    def _transform_surface(src, mode):
        w, h = src.get_width(), src.get_height()
        if mode in ('right', 'left'):
            out = cairo.ImageSurface(cairo.FORMAT_ARGB32, h, w)
        else:
            out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(out)
        if mode == 'right':
            ctx.translate(h, 0); ctx.rotate(math.pi / 2)
        elif mode == 'left':
            ctx.translate(0, w); ctx.rotate(-math.pi / 2)
        elif mode == '180':
            ctx.translate(w, h); ctx.rotate(math.pi)
        elif mode == 'flip_v':
            ctx.translate(0, h); ctx.scale(1, -1)
        elif mode == 'flip_h':
            ctx.translate(w, 0); ctx.scale(-1, 1)
        ctx.set_source_surface(src, 0, 0)
        ctx.paint()
        return out

    def skew(self, horizontal=0.0, vertical=0.0, *, label='倾斜'):
        if abs(horizontal) < 1e-9 and abs(vertical) < 1e-9:
            return False
        self.push_undo(label)
        hx = math.tan(math.radians(horizontal))
        vy = math.tan(math.radians(vertical))
        extra_w = abs(hx) * self.height
        extra_h = abs(vy) * self.width
        nw = int(math.ceil(self.width + extra_w))
        nh = int(math.ceil(self.height + extra_h))
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, nw, nh)
        ctx = cairo.Context(out)
        if not self.transparent:
            ctx.set_source_rgba(*self.background)
            ctx.paint()
        # translate so all content remains visible
        if hx >= 0:
            ctx.translate(0, extra_h if vy >= 0 else 0)
            ctx.transform(cairo.Matrix(1, vy, hx, 1, 0, 0))
        else:
            ctx.translate(extra_w, extra_h if vy >= 0 else 0)
            ctx.transform(cairo.Matrix(1, vy, hx, 1, 0, 0))
        ctx.set_source_surface(self.surface, 0, 0)
        ctx.paint()
        self.surface = out
        self.width, self.height = nw, nh
        self.selection = None
        self.dirty = True
        return True

    def invert_colors(self):
        self.push_undo('反色')
        data = self.surface.get_data()
        # ARGB32 little-endian byte order: B G R A
        mv = bytearray(data)
        for i in range(0, len(mv), 4):
            mv[i] = 255 - mv[i]
            mv[i + 1] = 255 - mv[i + 1]
            mv[i + 2] = 255 - mv[i + 2]
        out = cairo.ImageSurface.create_for_data(mv, cairo.FORMAT_ARGB32, self.width, self.height,
                                                 self.surface.get_stride())
        self.surface = _copy_surface(out)
        self.dirty = True

    def clear_image(self, color=None):
        self.push_undo('清除图像')
        clear_surface(self.surface, self.background if color is None else color)
        self.selection = None
        self.dirty = True

    def flatten_selection(self):
        """Commit a floating selection into the image."""
        sel = self.selection
        if not sel or sel.floating is None or sel.floating_origin is None:
            return
        x, y = sel.floating_origin
        ctx = cairo.Context(self.surface)
        if sel.inverted:
            # inverted floating regions are unusual; paint with mask
            ctx.save()
            mask = sel.mask_surface(self.width, self.height)
            ctx.push_group()
            ctx.set_source_surface(sel.floating, x, y)
            ctx.paint()
            group = ctx.pop_group()
            ctx.set_source(group)
            ctx.mask(cairo.SurfacePattern(mask))
            ctx.restore()
        else:
            if sel.polygon:
                ctx.save()
                ctx.set_source_surface(sel.floating, x, y)
                ctx.paint()
                ctx.restore()
            else:
                ctx.set_source_surface(sel.floating, x, y)
                ctx.paint()
        sel.x, sel.y = int(round(x)), int(round(y))
        sel.w, sel.h = sel.floating.get_width(), sel.floating.get_height()
        sel.floating = None
        sel.floating_origin = None

    def get_selection_surface(self, include_alpha=True):
        sel = self.selection
        if not sel or sel.empty:
            return None
        x, y, w, h = sel.rect
        x = max(0, x); y = max(0, y)
        w = min(w, self.width - x); h = min(h, self.height - y)
        if w <= 0 or h <= 0:
            return None
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(surface)
        ctx.set_source_surface(self.surface, -x, -y)
        ctx.paint()
        if sel.inverted or sel.polygon:
            mask = sel.mask_surface(self.width, self.height)
            ctx.set_operator(cairo.OPERATOR_DEST_IN)
            ctx.set_source_surface(mask, -x, -y)
            ctx.paint()
        return surface

    def delete_selection(self, background=None):
        sel = self.selection
        if not sel:
            return False
        if sel.floating is not None:
            sel.floating = None
            sel.floating_origin = None
            self.selection = None
            self.dirty = True
            return True
        if background is None:
            background = self.background
        background = normalize_rgba(background)
        self.push_undo('删除')
        ctx = cairo.Context(self.surface)
        if sel.inverted or sel.polygon:
            mask = sel.mask_surface(self.width, self.height)
            if background[3] <= 0:
                # DEST_OUT is the only reliable way to punch a transparent
                # hole through an arbitrary (polygon/inverted) mask.
                ctx.save()
                ctx.set_operator(cairo.OPERATOR_DEST_OUT)
                ctx.set_source_surface(mask, 0, 0)
                ctx.paint()
                ctx.restore()
            else:
                group = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
                gctx = cairo.Context(group)
                gctx.set_source_rgba(*background)
                gctx.paint()
                gctx.set_operator(cairo.OPERATOR_DEST_IN)
                gctx.set_source_surface(mask, 0, 0)
                gctx.paint()
                ctx.set_source_surface(group, 0, 0)
                ctx.paint()
        else:
            x, y, w, h = sel.rect
            ctx.set_operator(cairo.OPERATOR_SOURCE)
            ctx.set_source_rgba(*background)
            ctx.rectangle(x, y, w, h)
            ctx.fill()
        self.selection = None
        self.dirty = True
        return True

    def select_all(self):
        self.flatten_selection()
        self.selection = Selection(0, 0, self.width, self.height)
        return self.selection

    def invert_selection(self):
        if not self.selection:
            self.select_all()
            return
        self.selection.inverted = not self.selection.inverted

    def lift_selection(self):
        """Lift selected pixels into a floating surface and clear the source."""
        sel = self.selection
        if not sel or sel.empty:
            return None
        if sel.floating is not None:
            return sel.floating
        x, y, w, h = sel.rect
        x = max(0, x); y = max(0, y)
        w = min(w, self.width - x); h = min(h, self.height - y)
        if w <= 0 or h <= 0:
            return None
        surface = self.get_selection_surface()
        if surface is None:
            return None
        self.push_undo('移动选区')
        ctx = cairo.Context(self.surface)
        ctx.save()
        if sel.inverted or sel.polygon:
            mask = sel.mask_surface(self.width, self.height)
            if self.background[3] <= 0:
                # Remove precisely the selected shape without touching the
                # rest of the image.
                ctx.set_operator(cairo.OPERATOR_DEST_OUT)
                ctx.set_source_surface(mask, 0, 0)
                ctx.paint()
            else:
                # Paint the background colour only through the selection mask.
                cutter = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
                cctx = cairo.Context(cutter)
                cctx.set_source_rgba(*self.background)
                cctx.paint()
                cctx.set_operator(cairo.OPERATOR_DEST_IN)
                cctx.set_source_surface(mask, 0, 0)
                cctx.paint()
                ctx.set_source_surface(cutter, 0, 0)
                ctx.paint()
        else:
            ctx.set_operator(cairo.OPERATOR_SOURCE)
            ctx.set_source_rgba(*self.background)
            ctx.rectangle(x, y, w, h)
            ctx.fill()
        ctx.restore()
        sel.floating = surface
        sel.floating_origin = (x, y)
        return surface

    # ------------------------------------------------------------------
    # File I/O
    @classmethod
    def open(cls, path: str) -> 'Document':
        with Image.open(path) as im:
            im.load()
            im = ImageOps.exif_transpose(im)
            transparent = pil_has_transparency(im)
            if im.mode not in ('RGBA', 'RGB', 'L', 'P', 'LA'):
                im = im.convert('RGBA')
            width, height = im.size
            background = (1.0, 1.0, 1.0, 0.0) if transparent else (1.0, 1.0, 1.0, 1.0)
            doc = cls(width, height, background=background)
            doc.surface = pil_to_surface(im)
            doc.filename = path
            doc.format = os.path.splitext(path)[1].lower().lstrip('.')
            doc.dirty = False
            doc.selection = None
            doc.undo_stack.clear(); doc.redo_stack.clear()
            try:
                dpi = im.info.get('dpi', (96, 96))[0] or 96
            except Exception:
                dpi = 96
            doc.metadata['dpi'] = dpi
            doc.metadata['transparent'] = transparent
            doc.dpi = int(round(dpi))
            return doc

    def to_pil(self, *, with_alpha=False):
        return surface_to_pil(self.surface, with_alpha=with_alpha)

    def save(self, path: str | None = None, fmt: str | None = None, **options) -> str:
        path = path or self.filename
        if not path:
            raise ValueError('没有文件名')
        fmt = (fmt or os.path.splitext(path)[1].lstrip('.') or self.format or 'png').lower()
        if fmt == 'jpeg':
            fmt = 'jpg'
        alpha_formats = ('png', 'gif', 'webp', 'tif', 'tiff')
        with_alpha = bool(options.get('with_alpha', fmt in alpha_formats))
        img = self.to_pil(with_alpha=with_alpha)
        if fmt == 'jpg':
            if img.mode == 'RGBA':
                img = _flatten_pil_on_color(img, options.get('background', (255, 255, 255)))
            else:
                img = img.convert('RGB')
            img.save(path, 'JPEG', quality=options.get('quality', 92))
        elif fmt == 'bmp':
            bits = int(options.get('bits', 24))
            if img.mode == 'RGBA':
                img = _flatten_pil_on_color(img, options.get('background', (255, 255, 255)))
            if bits == 1:
                img = img.convert('1')
            elif bits == 4:
                img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=16)
            elif bits == 8:
                img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=256)
            elif bits == 16:
                # Pillow does not write 16-bit BMP; save a 24-bit BMP.
                img = img.convert('RGB')
            else:
                img = img.convert('RGB')
            img.save(path, 'BMP')
        elif fmt == 'dib':
            if img.mode == 'RGBA':
                img = _flatten_pil_on_color(img, options.get('background', (255, 255, 255)))
            img.save(path, 'BMP')
        elif fmt == 'gif':
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            _save_gif_with_alpha(img, path)
        elif fmt == 'png':
            if not with_alpha and img.mode == 'RGBA':
                img = _flatten_pil_on_color(img, options.get('background', (255, 255, 255)))
            img.save(path, 'PNG', dpi=(self.dpi, self.dpi))
        elif fmt in ('webp', 'tif', 'tiff'):
            fmt_name = 'WEBP' if fmt == 'webp' else 'TIFF'
            kwargs = {}
            if fmt == 'webp':
                kwargs['lossless'] = bool(options.get('lossless', True))
                kwargs['quality'] = options.get('quality', 95)
            img.save(path, fmt_name, **kwargs)
        else:
            # Let Pillow infer from the extension for less common formats.
            img.save(path)
        self.filename = path
        self.format = fmt
        self.dirty = False
        return path

    def duplicate(self) -> 'Document':
        doc = Document(self.width, self.height, background=self.background)
        doc.surface = _copy_surface(self.surface)
        doc.filename = self.filename
        doc.format = self.format
        doc.dirty = self.dirty
        doc.selection = self.selection.clone() if self.selection else None
        doc.dpi = self.dpi
        return doc


# ----------------------------------------------------------------------
# Pixel / image conversion helpers
def surface_to_pil(surface: cairo.ImageSurface, *, with_alpha=False) -> Image.Image:
    surface.flush()
    w, h = surface.get_width(), surface.get_height()
    stride = surface.get_stride()
    # Cairo's ARGB32 is native-endian, premultiplied BGRA on x86.
    raw = bytes(surface.get_data())
    im = Image.frombuffer('RGBA', (w, h), raw, 'raw', 'BGRA', stride, 1)
    pixels = bytearray(im.tobytes())
    # Un-premultiply so saved files use straight alpha.
    for i in range(0, len(pixels), 4):
        a = pixels[i + 3]
        if 0 < a < 255:
            pixels[i] = min(255, (pixels[i] * 255 + a // 2) // a)
            pixels[i + 1] = min(255, (pixels[i + 1] * 255 + a // 2) // a)
            pixels[i + 2] = min(255, (pixels[i + 2] * 255 + a // 2) // a)
        elif a == 0:
            pixels[i] = pixels[i + 1] = pixels[i + 2] = 0
    im = Image.frombytes('RGBA', (w, h), bytes(pixels))
    if with_alpha:
        return im
    # Formats without alpha (JPEG/BMP/printing) should see the image on an
    # opaque white background instead of black/undefined transparent pixels.
    return _flatten_pil_on_color(im, (255, 255, 255))


def _save_gif_with_alpha(im: Image.Image, path: str) -> None:
    """Save an RGBA image as a GIF, preserving binary transparency."""
    if im.mode != 'RGBA':
        im = im.convert('RGBA')
    alpha = im.getchannel('A')
    rgb = im.convert('RGB')
    palette = rgb.convert('P', palette=Image.Palette.ADAPTIVE, colors=255)
    transparent_mask = alpha.point(lambda a: 255 if a < 128 else 0)
    if transparent_mask.getbbox() is None:
        palette.save(path, 'GIF')
        return
    # Reserve palette index 255 for fully transparent pixels.
    palette.paste(255, mask=transparent_mask)
    palette.info['transparency'] = 255
    palette.save(path, 'GIF', transparency=255)


def pil_to_surface(im: Image.Image) -> cairo.ImageSurface:
    im = im.convert('RGBA')
    w, h = im.size
    data = bytearray(im.tobytes())  # RGBA, straight alpha
    # Convert to native BGRA and premultiply for Cairo ARGB32.
    for i in range(0, len(data), 4):
        r, g, b, a = data[i], data[i + 1], data[i + 2], data[i + 3]
        if a != 255:
            r = (r * a + 127) // 255
            g = (g * a + 127) // 255
            b = (b * a + 127) // 255
        data[i] = b
        data[i + 1] = g
        data[i + 2] = r
        data[i + 3] = a
    surface = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h, w * 4)
    return _copy_surface(surface)


def png_bytes_to_surface(data: bytes) -> cairo.ImageSurface:
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        return pil_to_surface(im)


def surface_to_png_bytes(surface: cairo.ImageSurface, with_alpha=True) -> bytes:
    buf = io.BytesIO()
    surface_to_pil(surface, with_alpha=with_alpha).save(buf, 'PNG')
    return buf.getvalue()
