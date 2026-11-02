# SPDX-License-Identifier: GPL-3.0-or-later
"""The interactive canvas widget for the Paint clone."""
from __future__ import annotations

import math

import cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk

from .document import Document, Selection, png_bytes_to_surface, surface_to_png_bytes
from .raster import (BRUSH_ORDER, DEFAULT_PALETTE, bucket_fill, draw_curve,
                     draw_eraser, draw_freehand, draw_pixel_line, fill_shape,
                     pick_color, stroke_segment)
from .shapes import SHAPE_ORDER, build_shape_path
from .text import draw_text


PAD = 12

_CHECKER_CACHE: dict[tuple[bool, int], cairo.SurfacePattern] = {}


def checker_pattern(dark: bool = False, cell: int = 8) -> cairo.SurfacePattern:
    """A repeating checkerboard pattern used behind transparent pixels."""
    key = (bool(dark), int(cell))
    pattern = _CHECKER_CACHE.get(key)
    if pattern is None:
        cell = max(2, int(cell))
        tile = cairo.ImageSurface(cairo.FORMAT_ARGB32, cell * 2, cell * 2)
        ctx = cairo.Context(tile)
        if dark:
            light, shade = (0.30, 0.31, 0.34), (0.22, 0.23, 0.26)
        else:
            light, shade = (1.0, 1.0, 1.0), (0.82, 0.82, 0.82)
        ctx.set_source_rgb(*light)
        ctx.paint()
        ctx.set_source_rgb(*shade)
        ctx.rectangle(0, 0, cell, cell)
        ctx.fill()
        ctx.rectangle(cell, cell, cell, cell)
        ctx.fill()
        pattern = cairo.SurfacePattern(tile)
        pattern.set_extend(cairo.EXTEND_REPEAT)
        _CHECKER_CACHE[key] = pattern
    return pattern


class PaintCanvas(Gtk.Overlay):
    """Canvas, input handling, selection overlay and text editing."""

    def __init__(self, document: Document, *, language='zh'):
        super().__init__()
        self.doc = document
        self.language = language
        self.drawing = Gtk.DrawingArea()
        self.drawing.set_hexpand(True)
        self.drawing.set_vexpand(True)
        self.set_child(self.drawing)
        self.set_focusable(True)
        self.drawing.set_can_focus(True)
        self.set_can_focus(True)

        self.zoom = 1.0
        self.dark = False
        self.grid = False
        self.rulers = False
        self.thumbnail = False
        self.tool = 'pencil'
        self.previous_tool = 'pencil'
        self.brush = 'brush'
        self.line_width = 1
        self.outline_style = 'solid'
        self.fill_style = 'solid'
        self.opaque_selection = True
        self.color1 = (0, 0, 0)
        self.color2 = (255, 255, 255)
        self.palette = list(DEFAULT_PALETTE)
        self.text_family = 'Sans'
        self.text_size = 12
        self.text_bold = False
        self.text_italic = False
        self.text_underline = False
        self.text_opaque = False

        # callbacks
        self.on_status = None
        self.on_zoom_changed = None
        self.on_selection_changed = None
        self.on_modified = None
        self.on_pointer = None
        self.on_color_picked = None

        # input state
        self._button = 1
        self._start = (0, 0)
        self._last = (0, 0)
        self._points = []
        self._mode = None
        self._preview = None
        self._action_undo_pushed = False
        self._move_origin = None
        self._move_start = None
        self._resize_handle = None
        self._resize_rect0 = None
        self._resize_start = None
        self._resize_base = None
        self._new_selection = None
        self._free_points = []
        self._curve = None  # dict(ends, control points, steps)
        self._space_pan = False
        self._text_editor = None
        self._text_pos = None
        self._text_fixed = None
        self._text_css = None

        self._setup_input()
        self.reset_document(document)

    # ------------------------------------------------------------------
    # Setup
    def _setup_input(self):
        drag = Gtk.GestureDrag()
        drag.set_button(1)
        drag.connect('drag-begin', self._on_drag_begin)
        drag.connect('drag-update', self._on_drag_update)
        drag.connect('drag-end', self._on_drag_end)
        self.drawing.add_controller(drag)
        self._drag = drag

        # A click gesture would compete with the drag gesture for the same
        # button sequence.  Clicks are handled by drag-begin/drag-end instead.

        motion = Gtk.EventControllerMotion()
        motion.connect('motion', self._on_motion)
        motion.connect('leave', lambda *a: self._emit_pointer(None))
        self.drawing.add_controller(motion)

        key = Gtk.EventControllerKey()
        key.connect('key-pressed', self._on_key)
        self.add_controller(key)

        scroll = Gtk.EventControllerScroll()
        scroll.set_flags(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll.connect('scroll', self._on_scroll)
        self.drawing.add_controller(scroll)

    def reset_document(self, document: Document):
        if self._text_editor is not None:
            self._discard_text()
        self.doc = document
        self._preview = None
        self._mode = None
        self._points = []
        self._curve = None
        self._update_size()
        self.drawing.queue_draw()
        self._notify_modified()

    def _update_size(self):
        w = self.doc.width * self.zoom + PAD * 2
        h = self.doc.height * self.zoom + PAD * 2
        self.drawing.set_size_request(max(32, int(math.ceil(w))), max(32, int(math.ceil(h))))
        self.set_size_request(max(32, int(math.ceil(w))), max(32, int(math.ceil(h))))
        self.queue_draw()

    # ------------------------------------------------------------------
    # Geometry helpers
    def image_origin(self):
        return PAD, PAD

    def view_to_image(self, vx, vy):
        ox, oy = self.image_origin()
        return (vx - ox) / self.zoom, (vy - oy) / self.zoom

    def image_to_view(self, ix, iy):
        ox, oy = self.image_origin()
        return ox + ix * self.zoom, oy + iy * self.zoom

    def _clamp_point(self, x, y):
        return (max(0, min(self.doc.width - 1e-6, x)),
                max(0, min(self.doc.height - 1e-6, y)))

    # ------------------------------------------------------------------
    # Public state
    def set_tool(self, tool):
        if self._text_editor is not None and tool != 'text':
            self._commit_text()
        self.commit_floating()
        self.previous_tool = self.tool
        self.tool = tool
        self._preview = None
        self.drawing.queue_draw()
        self._update_status()

    def set_brush(self, brush):
        self.brush = brush
        self.set_tool('brush')

    def set_zoom(self, zoom, anchor=None):
        zoom = max(0.1, min(8.0, zoom))
        if abs(zoom - self.zoom) < 1e-9:
            return
        self.zoom = zoom
        self._update_size()
        if self.on_zoom_changed:
            self.on_zoom_changed(zoom)
        self._update_status()

    def zoom_in(self):
        levels = [0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0]
        for z in levels:
            if z > self.zoom + 1e-6:
                self.set_zoom(z)
                return
        self.set_zoom(8.0)

    def zoom_out(self):
        levels = [0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0]
        for z in reversed(levels):
            if z < self.zoom - 1e-6:
                self.set_zoom(z)
                return
        self.set_zoom(0.1)

    def set_colors(self, color1=None, color2=None):
        if color1 is not None:
            self.color1 = tuple(int(v) for v in color1[:3])
        if color2 is not None:
            self.color2 = tuple(int(v) for v in color2[:3])
        self.drawing.queue_draw()
        if self.on_color_picked:
            self.on_color_picked(self.color1, self.color2)

    def set_palette(self, palette):
        self.palette = list(palette)
        self.drawing.queue_draw()

    # ------------------------------------------------------------------
    # Status / notifications
    def _update_status(self, vx=None, vy=None):
        if self.on_status is None:
            return
        pos = None
        if vx is not None and vy is not None:
            ix, iy = self.view_to_image(vx, vy)
            if 0 <= ix < self.doc.width and 0 <= iy < self.doc.height:
                pos = (int(ix), int(iy))
        sel = self.doc.selection
        sel_info = None
        if sel and not sel.empty:
            sel_info = sel.rect
        self.on_status(pos, sel_info, self.doc.width, self.doc.height, self.zoom)

    def _emit_pointer(self, point):
        if self.on_pointer:
            self.on_pointer(point)

    def _notify_modified(self):
        if self.on_modified:
            self.on_modified()

    def _notify_selection(self):
        if self.on_selection_changed:
            self.on_selection_changed(self.doc.selection)

    # ------------------------------------------------------------------
    # Drawing
    def _draw(self, area, ctx, width, height):
        # workspace (the canvas itself stays white in both themes)
        if self.dark:
            ctx.set_source_rgb(0.09, 0.10, 0.12)
        else:
            ctx.set_source_rgb(0.66, 0.72, 0.82)
        ctx.paint()
        ox, oy = self.image_origin()
        z = self.zoom
        iw = self.doc.width * z
        ih = self.doc.height * z
        # drop shadow / border around the canvas
        ctx.set_source_rgba(0, 0, 0, 0.45 if self.dark else 0.20)
        ctx.rectangle(ox + 2, oy + 2, iw, ih)
        ctx.fill()
        ctx.save()
        ctx.rectangle(ox, oy, iw, ih)
        ctx.clip()
        # A checkerboard makes transparent pixels distinguishable from white
        # pixels.  Opaque images cover it completely.
        ctx.save()
        ctx.translate(ox, oy)
        ctx.set_source(checker_pattern(self.dark))
        ctx.paint()
        ctx.restore()
        ctx.translate(ox, oy)
        ctx.scale(z, z)
        pattern = cairo.SurfacePattern(self.doc.surface)
        pattern.set_filter(cairo.FILTER_NEAREST if z >= 2.0 else cairo.FILTER_GOOD)
        ctx.set_source(pattern)
        ctx.paint()
        # floating selection
        sel = self.doc.selection
        if sel and sel.floating is not None and sel.floating_origin is not None:
            fx, fy = sel.floating_origin
            ctx.save()
            if sel.polygon:
                ctx.new_path()
                pts = sel.polygon
                if len(pts):
                    ctx.move_to(pts[0][0] - sel.x + fx, pts[0][1] - sel.y + fy)
                    for p in pts[1:]:
                        ctx.line_to(p[0] - sel.x + fx, p[1] - sel.y + fy)
                    ctx.close_path()
                    ctx.clip()
            ctx.set_source_surface(sel.floating, fx, fy)
            if self.opaque_selection:
                ctx.paint()
            else:
                # transparent selection: background colour becomes transparent
                tmp = cairo.ImageSurface(cairo.FORMAT_ARGB32, sel.floating.get_width(),
                                         sel.floating.get_height())
                tctx = cairo.Context(tmp)
                tctx.set_source_surface(sel.floating, 0, 0)
                tctx.paint()
                bg = self.color2
                tctx.set_operator(cairo.OPERATOR_DEST_OUT)
                # Remove pixels close to background without alpha-sensitive mask.
                _replace_color_alpha(tmp, bg)
                ctx.set_source_surface(tmp, fx, fy)
                ctx.paint()
            ctx.restore()
        ctx.restore()

        # grid
        if self.grid:
            ctx.save()
            ctx.rectangle(ox, oy, iw, ih)
            ctx.clip()
            step = 1 if z >= 4 else (5 if z >= 2 else 10)
            ctx.set_line_width(0.7)
            if self.dark:
                ctx.set_source_rgba(0.65, 0.72, 0.82, 0.28)
            else:
                ctx.set_source_rgba(0.2, 0.3, 0.45, 0.25)
            x = 0
            while x <= self.doc.width:
                px = ox + x * z
                ctx.move_to(px + 0.5, oy)
                ctx.line_to(px + 0.5, oy + ih)
                x += step
            y = 0
            while y <= self.doc.height:
                py = oy + y * z
                ctx.move_to(ox, py + 0.5)
                ctx.line_to(ox + iw, py + 0.5)
                y += step
            ctx.stroke()
            ctx.restore()

        # selection outline / handles
        if sel and not sel.empty:
            ctx.save()
            self._draw_selection(ctx, sel)
            ctx.restore()

        # live preview for shapes / line / selection
        if self._preview:
            ctx.save()
            ctx.translate(ox, oy)
            ctx.scale(z, z)
            self._draw_preview(ctx)
            ctx.restore()

        # canvas border
        ctx.set_source_rgba(0.55, 0.60, 0.68, 0.65) if self.dark else ctx.set_source_rgba(0.1, 0.12, 0.16, 0.55)
        ctx.set_line_width(1)
        ctx.rectangle(ox + 0.5, oy + 0.5, iw - 1, ih - 1)
        ctx.stroke()

        # text editor selection border
        if self._text_editor is not None and self._text_pos:
            tx, ty = self._text_pos
            ctx.save()
            ctx.set_source_rgba(0.15, 0.35, 0.75, 0.8)
            ctx.set_line_width(1)
            ctx.set_dash([4, 3])
            ctx.rectangle(ox + tx * z - 1, oy + ty * z - 1,
                          self._text_editor.get_width() + 2,
                          self._text_editor.get_height() + 2)
            ctx.stroke()
            ctx.restore()

    def _draw_selection(self, ctx, sel):
        ox, oy = self.image_origin()
        z = self.zoom
        x, y, w, h = sel.rect
        if sel.floating is not None and sel.floating_origin is not None:
            x, y = sel.floating_origin
            w, h = sel.floating.get_width(), sel.floating.get_height()
        if sel.polygon:
            pts = sel.polygon
            if len(pts) > 1:
                ctx.new_path()
                ctx.move_to(ox + pts[0][0] * z, oy + pts[0][1] * z)
                for px, py in pts[1:]:
                    ctx.line_to(ox + px * z, oy + py * z)
                ctx.close_path()
        else:
            ctx.rectangle(ox + x * z - 0.5, oy + y * z - 0.5, w * z + 1, h * z + 1)
        ctx.set_line_width(1)
        ctx.set_dash([4, 4])
        ctx.set_source_rgba(0, 0, 0, 0.85)
        ctx.stroke_preserve()
        ctx.set_dash([4, 4], 4)
        ctx.set_source_rgba(1, 1, 1, 0.9)
        ctx.stroke()
        ctx.set_dash([])
        # handles
        if not sel.polygon and not sel.inverted:
            hs = 5
            corners = [(x, y), (x + w / 2, y), (x + w, y),
                       (x, y + h / 2), (x + w, y + h / 2),
                       (x, y + h), (x + w / 2, y + h), (x + w, y + h)]
            for cx, cy in corners:
                px, py = ox + cx * z, oy + cy * z
                ctx.rectangle(px - hs, py - hs, hs * 2, hs * 2)
                ctx.set_source_rgb(1, 1, 1)
                ctx.fill_preserve()
                ctx.set_source_rgb(0.15, 0.15, 0.15)
                ctx.set_line_width(1)
                ctx.stroke()

    def _draw_preview(self, ctx):
        p = self._preview
        if not p:
            return
        kind = p.get('kind')
        if kind == 'rect_selection':
            x, y, w, h = p['rect']
            ctx.set_line_width(1 / self.zoom)
            ctx.set_dash([4 / self.zoom, 3 / self.zoom])
            ctx.set_source_rgba(0, 0, 0, 0.8)
            ctx.rectangle(x, y, w, h)
            ctx.stroke()
            ctx.set_dash([])
        elif kind == 'free_selection':
            pts = p['points']
            if len(pts) > 1:
                ctx.set_line_width(1 / self.zoom)
                ctx.set_dash([4 / self.zoom, 3 / self.zoom])
                ctx.set_source_rgba(0, 0, 0, 0.8)
                ctx.new_path(); ctx.move_to(*pts[0])
                for q in pts[1:]: ctx.line_to(*q)
                ctx.stroke()
                ctx.set_dash([])
        elif kind == 'shape':
            self._render_shape(ctx, p['shape'], p['x'], p['y'], p['w'], p['h'], preview=True)
        elif kind == 'line':
            ctx.set_line_width(max(0.8, self.line_width))
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.set_source_rgba(*self._stroke_color(), 1)
            ctx.move_to(*p['p0']); ctx.line_to(*p['p1']); ctx.stroke()
        elif kind == 'curve':
            p0, p1, c1, c2 = p['p0'], p['p1'], p['c1'], p['c2']
            ctx.set_line_width(max(0.8, self.line_width))
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.set_source_rgba(*self._stroke_color(), 1)
            ctx.move_to(*p0); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p1[0], p1[1]); ctx.stroke()
            for c in (c1, c2):
                ctx.arc(c[0], c[1], 3 / self.zoom, 0, 2 * math.pi)
                ctx.set_source_rgba(0.2, 0.4, 0.9, 0.8)
                ctx.fill()
        elif kind == 'move':
            pass

    def _render_shape(self, ctx, shape, x, y, w, h, preview=False):
        if w == 0 or h == 0:
            return
        outline = self.outline_style
        fill = self.fill_style
        oc = self._stroke_color()
        fc = self._fill_color()
        fill_shape(ctx, shape, x, y, w, h, fill, fc, outline, oc,
                   self.line_width, alpha=0.85 if preview else 1.0)

    def _stroke_color(self):
        return tuple(v / 255 for v in self.color1)

    def _fill_color(self):
        return tuple(v / 255 for v in self.color2)

    # ------------------------------------------------------------------
    # Event handling
    def _on_motion(self, controller, x, y):
        ix, iy = self.view_to_image(x, y)
        if 0 <= ix < self.doc.width and 0 <= iy < self.doc.height:
            self._emit_pointer((int(ix), int(iy)))
        else:
            self._emit_pointer((int(ix), int(iy)))
        self._update_status(x, y)

    def _on_click(self, gesture, n_press, x, y):
        if n_press == 2 and self.tool in ('select', 'free_select'):
            # double-click selects all, mirroring Paint's selection convention
            self.doc.select_all()
            self._notify_selection(); self.drawing.queue_draw()
            return
        # Fill and picker act on press via click too.  Drag-begin handles the
        # main path; this is a fallback for clicks that do not start a drag.
        pass

    def _on_drag_begin(self, gesture, start_x, start_y):
        self._start = (start_x, start_y)
        self._last = (start_x, start_y)
        self._button = gesture.get_current_button() or 1
        self._points = []
        self._free_points = []
        self._preview = None
        self._action_undo_pushed = False
        self._new_selection = None
        if self._text_editor is not None and self.tool != 'text':
            self._commit_text()
        ix, iy = self.view_to_image(start_x, start_y)
        if not (0 <= ix <= self.doc.width and 0 <= iy <= self.doc.height):
            self._mode = None
            return
        ix, iy = self._clamp_point(ix, iy)
        # Commit a previous floating selection when interacting outside it.
        sel = self.doc.selection
        if sel and sel.floating is not None:
            inside = sel.contains(ix, iy)
            if not inside or self.tool not in ('select', 'free_select'):
                self.commit_floating()
        self._mode = None
        if self.tool == 'select':
            self._begin_select(ix, iy, freeform=False)
        elif self.tool == 'free_select':
            self._begin_select(ix, iy, freeform=True)
        elif self.tool == 'text':
            self._begin_text(ix, iy)
        elif self.tool == 'magnifier':
            if self._button == 3:
                self.zoom_out()
            else:
                self.zoom_in()
        elif self.tool == 'picker':
            self._pick(ix, iy)
        elif self.tool == 'fill':
            self._do_fill(ix, iy)
        elif self.tool == 'eraser':
            self._begin_stroke(ix, iy)
        elif self.tool == 'pencil':
            self._begin_stroke(ix, iy)
        elif self.tool == 'brush':
            self._begin_stroke(ix, iy)
        elif self.tool in SHAPE_ORDER:
            if self.tool == 'line':
                self._mode = 'line'
                self.doc.push_undo('直线')
                self._preview = {'kind': 'line', 'p0': (ix, iy), 'p1': (ix, iy)}
            elif self.tool == 'curve':
                if self._curve is None:
                    self._mode = 'curve_draw'
                    self.doc.push_undo('曲线')
                    self._preview = {'kind': 'line', 'p0': (ix, iy), 'p1': (ix, iy)}
                else:
                    self._mode = 'curve_adjust'
                    self._curve_adjust_start(ix, iy)
            else:
                self._mode = 'shape'
                self.doc.push_undo(self.tool)
                self._preview = {'kind': 'shape', 'shape': self.tool,
                                 'x': ix, 'y': iy, 'w': 0, 'h': 0}
        self._update_status(start_x, start_y)
        self.drawing.queue_draw()

    def _begin_stroke(self, ix, iy):
        self._mode = 'stroke'
        self.doc.push_undo('绘图')
        self._action_undo_pushed = True
        self._points = [(ix, iy)]
        ctx = cairo.Context(self.doc.surface)
        color = tuple(v / 255 for v in (self.color2 if self._button == 3 else self.color1))
        if self.tool == 'eraser':
            size = max(4, self.line_width * 2)
            draw_eraser(ctx, ix, iy, size,
                        tuple(v / 255 for v in self.color2),
                        clear=self.doc.transparent)
        elif self.tool == 'pencil':
            if self.line_width <= 1:
                draw_pixel_line(self.doc.surface, ix, iy, ix, iy, color)
            else:
                ctx.set_line_width(max(1, self.line_width * 0.5))
                ctx.set_source_rgb(*color)
                ctx.arc(ix, iy, max(0.5, self.line_width * 0.25), 0, 2 * math.pi)
                ctx.fill()
        elif self.tool == 'brush':
            stroke_segment(ctx, (ix, iy), (ix + 0.01, iy + 0.01), color,
                           self.line_width, self.brush, seed=1)
        self._notify_modified()
        self.drawing.queue_draw()

    def _on_drag_update(self, gesture, offset_x, offset_y):
        if not self._mode:
            return
        sx, sy = self._start
        x, y = sx + offset_x, sy + offset_y
        ix, iy = self.view_to_image(x, y)
        ix, iy = self._clamp_point(ix, iy)
        self._last = (x, y)
        if self._mode == 'stroke':
            self._continue_stroke(ix, iy)
        elif self._mode == 'move':
            if self._move_origin is not None:
                dx = ix - self._move_start[0]
                dy = iy - self._move_start[1]
                self.doc.selection.floating_origin = (
                    int(round(self._move_origin[0] + dx)),
                    int(round(self._move_origin[1] + dy)))
                self.drawing.queue_draw()
        elif self._mode == 'resize_selection':
            self._resize_selection_update(ix, iy)
            self.drawing.queue_draw()
        elif self._mode == 'select_rect':
            x0, y0 = self._sel_start
            nx, ny = min(x0, ix), min(y0, iy)
            nw, nh = abs(ix - x0), abs(iy - y0)
            self._preview = {'kind': 'rect_selection', 'rect': (nx, ny, nw, nh)}
            self._new_selection = (nx, ny, nw, nh)
            self.drawing.queue_draw()
        elif self._mode == 'select_free':
            if not self._free_points or math.hypot(ix - self._free_points[-1][0],
                                                   iy - self._free_points[-1][1]) >= 1.0 / self.zoom:
                self._free_points.append((ix, iy))
            self._preview = {'kind': 'free_selection', 'points': self._free_points}
            self.drawing.queue_draw()
        elif self._mode == 'line':
            self._preview = {'kind': 'line', 'p0': self._preview['p0'], 'p1': (ix, iy)}
            self.drawing.queue_draw()
        elif self._mode == 'curve_draw':
            self._preview = {'kind': 'line', 'p0': self._preview['p0'], 'p1': (ix, iy)}
            self.drawing.queue_draw()
        elif self._mode == 'curve_adjust':
            self._curve_drag(ix, iy)
            self.drawing.queue_draw()
        elif self._mode == 'shape':
            p = self._preview
            nx, ny = min(p['x'], ix), min(p['y'], iy)
            nw, nh = abs(ix - p['x']), abs(iy - p['y'])
            # Keep the origin fixed at the anchor but update bounds.
            self._preview = {'kind': 'shape', 'shape': p['shape'],
                             'x': nx, 'y': ny, 'w': nw, 'h': nh}
            self.drawing.queue_draw()
        self._update_status(x, y)

    def _on_drag_end(self, gesture, offset_x, offset_y):
        mode = self._mode
        sx, sy = self._start
        self._mode = None
        if mode == 'stroke':
            self._commit_stroke()
        elif mode == 'line':
            if self._preview:
                p0, p1 = self._preview['p0'], self._preview['p1']
                if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) >= 0.5:
                    ctx = cairo.Context(self.doc.surface)
                    ctx.set_line_width(max(0.8, self.line_width))
                    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
                    ctx.set_source_rgb(*self._stroke_color())
                    ctx.move_to(*p0); ctx.line_to(*p1); ctx.stroke()
            self._preview = None
            self._notify_modified()
        elif mode == 'curve_draw':
            if self._preview:
                p0, p1 = self._preview['p0'], self._preview['p1']
                if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) >= 1:
                    c1 = (p0[0] + (p1[0] - p0[0]) / 3, p0[1] + (p1[1] - p0[1]) / 3)
                    c2 = (p0[0] + (p1[0] - p0[0]) * 2 / 3, p0[1] + (p1[1] - p0[1]) * 2 / 3)
                    self._curve = {'p0': p0, 'p1': p1, 'c1': c1, 'c2': c2, 'steps': 0}
                    self._preview = {'kind': 'curve', 'p0': p0, 'p1': p1, 'c1': c1, 'c2': c2}
                else:
                    self._preview = None
        elif mode == 'shape':
            if self._preview:
                p = self._preview
                if p['w'] >= 0.5 and p['h'] >= 0.5:
                    ctx = cairo.Context(self.doc.surface)
                    self._render_shape(ctx, p['shape'], p['x'], p['y'], p['w'], p['h'])
                    self._notify_modified()
                self._preview = None
        elif mode == 'select_rect':
            if self._new_selection:
                x, y, w, h = self._new_selection
                if w < 1 or h < 1:
                    self.doc.selection = None
                else:
                    self.doc.selection = Selection(int(x), int(y), int(round(w)), int(round(h)))
                    if self.on_selection_changed:
                        self.on_selection_changed(self.doc.selection)
            else:
                self.doc.selection = None
            self._preview = None
            self._new_selection = None
            self._notify_selection()
        elif mode == 'select_free':
            if self._free_points and len(self._free_points) >= 3:
                xs = [p[0] for p in self._free_points]
                ys = [p[1] for p in self._free_points]
                x, y = min(xs), min(ys)
                w, h = max(xs) - x, max(ys) - y
                if w >= 1 and h >= 1:
                    self.doc.selection = Selection(int(x), int(y), int(math.ceil(w)),
                                                   int(math.ceil(h)),
                                                   polygon=list(self._free_points))
            else:
                self.doc.selection = None
            self._preview = None
            self._free_points = []
            self._notify_selection()
        elif mode == 'move':
            self._move_origin = None
            self._move_start = None
            self._notify_selection()
            self._notify_modified()
        elif mode == 'resize_selection':
            self._resize_handle = None
            self._notify_selection()
            self._notify_modified()
        self.drawing.queue_draw()
        self._update_status(sx + offset_x, sy + offset_y)

    def _continue_stroke(self, ix, iy):
        last = self._points[-1]
        if abs(ix - last[0]) < 0.1 and abs(iy - last[1]) < 0.1 and self.tool != 'brush':
            return
        ctx = cairo.Context(self.doc.surface)
        color = tuple(v / 255 for v in (self.color2 if self._button == 3 else self.color1))
        if self.tool == 'eraser':
            size = max(4, self.line_width * 2)
            # interpolate for fast movement
            dist = math.hypot(ix - last[0], iy - last[1])
            steps = max(1, int(dist / max(1, size * 0.35)))
            for i in range(1, steps + 1):
                t = i / steps
                draw_eraser(ctx, last[0] + (ix - last[0]) * t,
                            last[1] + (iy - last[1]) * t, size,
                            tuple(v / 255 for v in self.color2),
                            clear=self.doc.transparent)
        elif self.tool == 'pencil':
            if self.line_width <= 1:
                draw_pixel_line(self.doc.surface, last[0], last[1], ix, iy, color)
            else:
                ctx.set_line_width(max(1, self.line_width * 0.5))
                ctx.set_source_rgb(*color)
                ctx.move_to(*last); ctx.line_to(ix, iy); ctx.stroke()
        elif self.tool == 'brush':
            stroke_segment(ctx, last, (ix, iy), color, self.line_width, self.brush,
                           seed=len(self._points))
        self._points.append((ix, iy))
        self._update_status(*self.image_to_view(ix, iy))
        self.drawing.queue_draw()

    def _commit_stroke(self):
        if self._points:
            self._notify_modified()
        self._points = []

    def _delete_background(self):
        """Colour used when clearing a selection.

        Transparent images must keep their alpha channel; opaque images keep
        Paint's classic "fill with Colour 2" behaviour.
        """
        if self.doc.transparent:
            return (1.0, 1.0, 1.0, 0.0)
        return tuple(v / 255 for v in self.color2)

    def _do_fill(self, ix, iy):
        self.doc.push_undo('用颜色填充')
        color = self.color2 if self._button == 3 else self.color1
        bucket_fill(self.doc.surface, int(ix), int(iy), tuple(v / 255 for v in color))
        self._notify_modified()
        self.drawing.queue_draw()

    def _pick(self, ix, iy):
        c = pick_color(self.doc.surface, int(ix), int(iy))
        if c:
            if self._button == 3:
                self.set_colors(color2=c[:3])
            else:
                self.set_colors(color1=c[:3])
            self._update_status(*self.image_to_view(ix, iy))

    def _begin_select(self, ix, iy, freeform=False):
        sel = self.doc.selection
        handle = self._selection_handle_at(ix, iy) if sel and not freeform else None
        if handle:
            if sel.floating is None:
                self.doc.lift_selection()
                self._transparentize_floating()
            self._mode = 'resize_selection'
            self._resize_handle = handle
            self._resize_rect0 = (sel.x, sel.y, sel.w, sel.h)
            self._resize_start = (ix, iy)
            self._resize_base = _copy_surface(sel.floating) if sel.floating else None
            self._notify_selection()
            return
        if sel and not sel.empty and sel.contains(ix, iy):
            # Move the selected content.
            if sel.floating is None:
                self.doc.lift_selection()
                self._transparentize_floating()
            self._mode = 'move'
            self._move_origin = sel.floating_origin or sel.rect[:2]
            self._move_start = (ix, iy)
            self._notify_selection()
            return
        # A click outside commits a floating selection and starts a new one.
        self.doc.selection = None
        self._sel_start = (ix, iy)
        self._free_points = [(ix, iy)] if freeform else []
        self._mode = 'select_free' if freeform else 'select_rect'
        self._preview = ({'kind': 'free_selection', 'points': self._free_points}
                         if freeform else {'kind': 'rect_selection', 'rect': (ix, iy, 0, 0)})
        self._notify_selection()
        self.drawing.queue_draw()

    def _selection_handle_at(self, ix, iy):
        sel = self.doc.selection
        if not sel or sel.empty or sel.polygon or sel.inverted:
            return None
        x, y, w, h = sel.rect
        if sel.floating is not None and sel.floating_origin is not None:
            x, y = sel.floating_origin
            w, h = sel.floating.get_width(), sel.floating.get_height()
        tol = max(5.0, 7.0 / self.zoom)
        points = {
            'nw': (x, y), 'n': (x + w / 2, y), 'ne': (x + w, y),
            'w': (x, y + h / 2), 'e': (x + w, y + h / 2),
            'sw': (x, y + h), 's': (x + w / 2, y + h), 'se': (x + w, y + h),
        }
        for name, (px, py) in points.items():
            if abs(ix - px) <= tol and abs(iy - py) <= tol:
                return name
        return None

    def _resize_selection_update(self, ix, iy):
        sel = self.doc.selection
        if not sel or self._resize_base is None or self._resize_rect0 is None:
            return
        x0, y0, w0, h0 = self._resize_rect0
        dx = ix - self._resize_start[0]
        dy = iy - self._resize_start[1]
        x, y, w, h = x0, y0, w0, h0
        handle = self._resize_handle or 'se'
        if 'w' in handle:
            x = x0 + dx
            w = w0 - dx
        if 'e' in handle:
            w = w0 + dx
        if 'n' in handle:
            y = y0 + dy
            h = h0 - dy
        if 's' in handle:
            h = h0 + dy
        if w < 1:
            if 'w' in handle:
                x = x0 + w0 - 1
            w = 1
        if h < 1:
            if 'n' in handle:
                y = y0 + h0 - 1
            h = 1
        nw, nh = max(1, int(round(w))), max(1, int(round(h)))
        scaled = _scale_surface(self._resize_base, nw, nh)
        sel.floating = scaled
        sel.floating_origin = (int(round(x)), int(round(y)))
        sel.x, sel.y, sel.w, sel.h = int(round(x)), int(round(y)), nw, nh

    # ------------------------------------------------------------------
    # Curve tool
    def _curve_adjust_start(self, ix, iy):
        curve = self._curve
        if not curve:
            return
        # Pick the closest of the two control points.
        d1 = math.hypot(ix - curve['c1'][0], iy - curve['c1'][1])
        d2 = math.hypot(ix - curve['c2'][0], iy - curve['c2'][1])
        curve['active'] = 'c1' if d1 <= d2 else 'c2'
        curve['offset'] = (ix - curve[curve['active']][0], iy - curve[curve['active']][1])
        self._preview = {'kind': 'curve', 'p0': curve['p0'], 'p1': curve['p1'],
                         'c1': curve['c1'], 'c2': curve['c2']}

    def _curve_drag(self, ix, iy):
        curve = self._curve
        if not curve:
            return
        key = curve.get('active', 'c1')
        ox, oy = curve.get('offset', (0, 0))
        curve[key] = (ix - ox, iy - oy)
        self._preview = {'kind': 'curve', 'p0': curve['p0'], 'p1': curve['p1'],
                         'c1': curve['c1'], 'c2': curve['c2']}

    def finish_curve(self):
        if not self._curve:
            return
        c = self._curve
        ctx = cairo.Context(self.doc.surface)
        draw_curve(ctx, c['p0'], c['p1'], c['c1'], c['c2'],
                   self._stroke_color(), self.line_width, self.outline_style)
        self._curve = None
        self._preview = None
        self.doc.push_undo('曲线') if not self.doc.can_undo() else None
        self._notify_modified()
        self.drawing.queue_draw()

    # ------------------------------------------------------------------
    # Text tool
    def _begin_text(self, ix, iy):
        if self._text_editor is not None:
            self._commit_text()
        self._text_pos = (ix, iy)
        self._create_text_editor(ix, iy)

    def _create_text_editor(self, ix, iy):
        if self._text_fixed is not None:
            self.remove_overlay(self._text_fixed)
        fixed = Gtk.Fixed()
        fixed.set_hexpand(True)
        fixed.set_vexpand(True)
        fixed.set_can_target(False)
        tv = Gtk.TextView()
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_accepts_tab(False)
        tv.set_size_request(max(120, int(220 * self.zoom)), max(40, int(70 * self.zoom)))
        tv.add_css_class('paint-text-editor')
        css = Gtk.CssProvider()
        color = '#%02x%02x%02x' % self.color1
        bg = '#%02x%02x%02x' % self.color2
        family = self.text_family.replace("'", "")
        font_px = max(6, int(round(self.text_size * 96 / 72 * self.zoom)))
        weight = 'bold' if self.text_bold else 'normal'
        style = 'italic' if self.text_italic else 'normal'
        decoration = 'underline' if self.text_underline else 'none'
        background = bg if self.text_opaque else 'transparent'
        css.load_from_data(
            f"textview.paint-text-editor {{ background-color: {background}; color: {color}; "
            f"font-family: '{family}'; font-size: {font_px}px; font-weight: {weight}; "
            f"font-style: {style}; text-decoration: {decoration}; padding: 0; border: 1px solid #4a90e2; }}"
            f"textview.paint-text-editor text {{ background-color: {background}; }}".encode())
        tv.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._text_css = css
        px, py = self.image_to_view(ix, iy)
        fixed.put(tv, int(px), int(py))
        self.add_overlay(fixed)
        self._text_fixed = fixed
        self._text_editor = tv
        tv.grab_focus()
        focus = Gtk.EventControllerFocus()
        focus.connect('leave', self._on_text_focus_leave)
        tv.add_controller(focus)
        key = Gtk.EventControllerKey()
        key.connect('key-pressed', self._on_text_key)
        tv.add_controller(key)
        tv.get_buffer().connect('changed', lambda *a: self.drawing.queue_draw())

    def _on_text_focus_leave(self, *args):
        if self._text_editor is not None:
            GLib.idle_add(self._deferred_text_commit)

    def _deferred_text_commit(self):
        if self._text_editor is not None:
            self._commit_text()
        return False

    def _on_text_key(self, controller, keyval, keycode, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if keyval == Gdk.KEY_Escape:
            self._discard_text()
            return True
        if ctrl and keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._commit_text()
            return True
        return False

    def _commit_text(self):
        tv = self._text_editor
        if tv is None:
            return
        buf = tv.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        pos = self._text_pos
        self._text_editor = None
        self._text_pos = None
        if self._text_fixed is not None:
            self.remove_overlay(self._text_fixed)
            self._text_fixed = None
        if text.strip() and pos:
            self.doc.push_undo('文本')
            ctx = cairo.Context(self.doc.surface)
            draw_text(ctx, text, pos[0], pos[1], self.text_family, self.text_size,
                      self.text_bold, self.text_italic, self.text_underline,
                      tuple(v / 255 for v in self.color1),
                      tuple(v / 255 for v in self.color2), self.text_opaque)
            self._notify_modified()
        self.drawing.queue_draw()
        self.grab_focus()

    def _discard_text(self):
        if self._text_fixed is not None:
            self.remove_overlay(self._text_fixed)
            self._text_fixed = None
        self._text_editor = None
        self._text_pos = None
        self.drawing.queue_draw()

    def update_text_style(self):
        if self._text_editor is not None and self._text_pos:
            ix, iy = self._text_pos
            # Preserve current contents while rebuilding the editor.
            buf = self._text_editor.get_buffer()
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
            self._discard_text()
            self._text_pos = (ix, iy)
            self._create_text_editor(ix, iy)
            self._text_editor.get_buffer().set_text(text)
            end = self._text_editor.get_buffer().get_end_iter()
            self._text_editor.get_buffer().place_cursor(end)
            self._text_editor.grab_focus()

    # ------------------------------------------------------------------
    # Scroll / keys
    def _on_scroll(self, controller, dx, dy):
        state = controller.get_current_event_state()
        if state & Gdk.ModifierType.CONTROL_MASK:
            if dy < 0:
                self.zoom_in()
            elif dy > 0:
                self.zoom_out()
            return True
        return False

    def _on_key(self, controller, keyval, keycode, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if keyval == Gdk.KEY_Escape:
            if self._text_editor is not None:
                self._discard_text()
            elif self._curve is not None:
                self._curve = None; self._preview = None; self.drawing.queue_draw()
            elif self.doc.selection is not None:
                self.doc.selection = None
                self._notify_selection(); self.drawing.queue_draw()
            return True
        if keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace):
            if self.doc.selection is not None:
                self.doc.delete_selection(self._delete_background())
                self._notify_selection(); self._notify_modified(); self.drawing.queue_draw()
                return True
        if self.doc.selection and self.doc.selection.floating is not None and keyval in (
                Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down):
            step = 10 if shift else 1
            sel = self.doc.selection
            ox, oy = sel.floating_origin or (0, 0)
            if keyval == Gdk.KEY_Left: ox -= step
            if keyval == Gdk.KEY_Right: ox += step
            if keyval == Gdk.KEY_Up: oy -= step
            if keyval == Gdk.KEY_Down: oy += step
            sel.floating_origin = (ox, oy)
            self.drawing.queue_draw()
            return True
        return False

    # ------------------------------------------------------------------
    # Clipboard / selection API
    def _apply_transparent_selection(self, surface):
        """Drop Colour 2 pixels when Paint's transparent-selection mode is on."""
        if surface is None or self.opaque_selection:
            return surface
        out = _copy_surface(surface)
        _replace_color_alpha(out, self.color2)
        return out

    def _transparentize_floating(self):
        sel = self.doc.selection
        if sel and sel.floating is not None and not self.opaque_selection:
            sel.floating = self._apply_transparent_selection(sel.floating)

    def get_clipboard_surface(self):
        if self.doc.selection:
            if self.doc.selection.floating is not None:
                s = self.doc.selection.floating
                out = cairo.ImageSurface(cairo.FORMAT_ARGB32, s.get_width(), s.get_height())
                c = cairo.Context(out); c.set_source_surface(s, 0, 0); c.paint()
                return self._apply_transparent_selection(out)
            return self._apply_transparent_selection(self.doc.get_selection_surface())
        return None

    def paste_surface(self, surface, *, origin=(0, 0)):
        # Select the Selection tool first: set_tool() deliberately commits any
        # previous floating selection, so the new paste must be created after it.
        self.set_tool('select')
        surface = self._apply_transparent_selection(surface)
        self.doc.push_undo('粘贴')
        self.doc.selection = Selection(int(origin[0]), int(origin[1]),
                                       surface.get_width(), surface.get_height(),
                                       floating=surface,
                                       floating_origin=(int(origin[0]), int(origin[1])))
        self._notify_selection()
        self._notify_modified()
        self._update_size()
        self.drawing.queue_draw()

    def paste_png_bytes(self, data: bytes):
        self.paste_surface(png_bytes_to_surface(data))

    def commit_floating(self):
        sel = self.doc.selection
        if sel and sel.floating is not None:
            self._transparentize_floating()
            self.doc.flatten_selection()
            self.doc.dirty = True
            self._notify_modified()
            self.drawing.queue_draw()

    def copy_selection(self):
        self.commit_floating()
        s = self.get_clipboard_surface()
        return s

    def cut_selection(self):
        s = self.copy_selection()
        if s is not None:
            self.doc.delete_selection(self._delete_background())
            self._notify_selection(); self._notify_modified(); self.drawing.queue_draw()
        return s

    def delete_selection(self):
        if self.doc.selection is not None:
            self.doc.delete_selection(self._delete_background())
            self._notify_selection(); self._notify_modified(); self.drawing.queue_draw()
            return True
        return False

    def select_all(self):
        self.commit_floating()
        self.doc.select_all()
        self._notify_selection(); self.drawing.queue_draw()

    def crop(self):
        self.commit_floating()
        if self.doc.crop():
            self._notify_selection(); self._notify_modified(); self._update_size()
            return True
        return False

    def update_after_image_change(self):
        self._update_size(); self.drawing.queue_draw(); self._notify_modified()
        self._notify_selection()
        self._update_status()

    def png_for_clipboard(self):
        s = self.get_clipboard_surface()
        return surface_to_png_bytes(s, with_alpha=True) if s else None


def _replace_color_alpha(surface, bg_rgb, tolerance=18):
    """Make pixels matching the Paint background colour transparent."""
    surface.flush()
    w, h = surface.get_width(), surface.get_height()
    stride = surface.get_stride()
    data = surface.get_data()
    br, bg, bb = bg_rgb
    for y in range(h):
        off = y * stride
        for x in range(w):
            o = off + x * 4
            b, g, r, a = data[o], data[o + 1], data[o + 2], data[o + 3]
            if a and abs(r - br) <= tolerance and abs(g - bg) <= tolerance and abs(b - bb) <= tolerance:
                data[o] = data[o + 1] = data[o + 2] = data[o + 3] = 0
    surface.mark_dirty()


def _copy_surface(surface):
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, surface.get_width(), surface.get_height())
    ctx = cairo.Context(out)
    ctx.set_source_surface(surface, 0, 0)
    ctx.paint()
    return out


def _scale_surface(surface, w, h):
    w = max(1, int(w)); h = max(1, int(h))
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(out)
    ctx.scale(w / surface.get_width(), h / surface.get_height())
    pattern = cairo.SurfacePattern(surface)
    pattern.set_filter(cairo.FILTER_GOOD)
    ctx.set_source(pattern)
    ctx.paint()
    return out
