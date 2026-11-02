# SPDX-License-Identifier: GPL-3.0-or-later
"""Small Cairo-drawn icon set used by the Paint ribbon."""
from __future__ import annotations

import math

import cairo
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


BLUE = (0.18, 0.42, 0.70)
DARK = (0.18, 0.18, 0.20)
ORANGE = (0.88, 0.42, 0.12)
RED = (0.80, 0.18, 0.18)
GREEN = (0.20, 0.58, 0.30)
YELLOW = (0.95, 0.72, 0.12)
GREY = (0.45, 0.48, 0.52)
WHITE = (1, 1, 1)

# Light theme palette (module globals are updated by set_dark_theme()).
_LIGHT_COLORS = {
    'DARK': (0.18, 0.18, 0.20),
    'BLUE': (0.18, 0.42, 0.70),
    'GREY': (0.45, 0.48, 0.52),
}
_DARK_COLORS = {
    'DARK': (0.88, 0.89, 0.91),
    'BLUE': (0.44, 0.70, 0.98),
    'GREY': (0.68, 0.71, 0.76),
}
_THEME_DARK = False

def set_dark_theme(dark: bool):
    """Switch icon stroke colours and redraw existing PaintIcon widgets."""
    global _THEME_DARK, DARK, BLUE, GREY
    _THEME_DARK = bool(dark)
    values = _DARK_COLORS if _THEME_DARK else _LIGHT_COLORS
    DARK = values['DARK']
    BLUE = values['BLUE']
    GREY = values['GREY']
    for window in Gtk.Window.list_toplevels():
        window.queue_draw()


def is_dark_theme():
    return _THEME_DARK


def _sp(ctx, pts, close=False):
    for i, p in enumerate(pts):
        if i == 0: ctx.move_to(*p)
        else: ctx.line_to(*p)
    if close: ctx.close_path()


def draw_icon(ctx, name, size):
    """Draw a 32x32 logical icon, scaled to *size*."""
    s = size / 32.0
    ctx.save()
    ctx.scale(s, s)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_width(1.8)
    ctx.set_source_rgb(*DARK)
    n = name
    if n == 'save':
        ctx.set_source_rgb(*BLUE)
        ctx.rectangle(5, 3, 22, 26); ctx.fill()
        ctx.set_source_rgb(*WHITE); ctx.rectangle(9, 5, 14, 8); ctx.fill()
        ctx.set_source_rgb(0.85, 0.9, 0.95); ctx.rectangle(9, 18, 14, 9); ctx.fill()
        ctx.set_source_rgb(*DARK); ctx.rectangle(9, 18, 14, 9); ctx.stroke()
    elif n in ('undo', 'redo'):
        ctx.set_source_rgb(*BLUE)
        ctx.set_line_width(2.6)
        if n == 'undo':
            ctx.arc(17, 18, 8, math.pi, 2 * math.pi)
            ctx.stroke()
            _sp(ctx, [(5, 16), (8, 21), (13, 17)], True); ctx.fill()
        else:
            ctx.arc(15, 18, 8, 0, math.pi)
            ctx.stroke()
            _sp(ctx, [(27, 16), (24, 21), (19, 17)], True); ctx.fill()
    elif n == 'paste':
        ctx.set_source_rgb(0.80, 0.64, 0.35)
        ctx.rectangle(8, 6, 17, 23); ctx.fill()
        ctx.set_source_rgb(0.95, 0.90, 0.78)
        ctx.rectangle(10, 10, 13, 16); ctx.fill()
        ctx.set_source_rgb(*DARK); ctx.rectangle(8, 6, 17, 23); ctx.stroke()
        ctx.set_source_rgb(0.6, 0.62, 0.65); ctx.rectangle(12, 3, 9, 6); ctx.fill()
        ctx.set_source_rgb(*DARK); ctx.rectangle(12, 3, 9, 6); ctx.stroke()
    elif n == 'cut':
        ctx.set_source_rgb(*GREY); ctx.set_line_width(2)
        ctx.move_to(10, 5); ctx.line_to(21, 20); ctx.stroke()
        ctx.move_to(22, 5); ctx.line_to(11, 20); ctx.stroke()
        ctx.set_source_rgb(*BLUE)
        ctx.arc(9, 24, 4, 0, 2 * math.pi); ctx.stroke()
        ctx.arc(23, 24, 4, 0, 2 * math.pi); ctx.stroke()
    elif n == 'copy':
        ctx.set_source_rgb(*BLUE); ctx.set_line_width(1.5)
        ctx.rectangle(5, 8, 16, 19); ctx.stroke()
        ctx.set_source_rgb(*WHITE); ctx.rectangle(10, 4, 17, 20); ctx.fill()
        ctx.set_source_rgb(*BLUE); ctx.rectangle(10, 4, 17, 20); ctx.stroke()
    elif n in ('select_rect', 'crop'):
        ctx.set_line_width(1.4)
        for x, y in [(4, 8), (8, 4), (24, 4), (28, 8), (28, 24), (24, 28), (8, 28), (4, 24)]:
            ctx.move_to(x, y); ctx.line_to(x, y)
        if n == 'select_rect':
            ctx.set_dash([3, 2]); ctx.rectangle(4, 4, 24, 24); ctx.stroke()
        else:
            ctx.set_source_rgb(*BLUE); ctx.set_dash([3, 2])
            ctx.rectangle(8, 8, 16, 16); ctx.stroke(); ctx.set_dash([])
            ctx.set_source_rgb(*DARK)
            ctx.move_to(4, 4); ctx.line_to(11, 4); ctx.move_to(4, 4); ctx.line_to(4, 11); ctx.stroke()
            ctx.move_to(28, 28); ctx.line_to(21, 28); ctx.move_to(28, 28); ctx.line_to(28, 21); ctx.stroke()
    elif n == 'select_free':
        ctx.set_dash([3, 2])
        ctx.set_source_rgb(*BLUE)
        _sp(ctx, [(6, 22), (8, 10), (16, 5), (26, 9), (25, 19), (17, 27), (8, 25)], True)
        ctx.stroke(); ctx.set_dash([])
    elif n == 'resize':
        ctx.set_source_rgb(*BLUE)
        ctx.rectangle(4, 18, 11, 10); ctx.stroke()
        ctx.rectangle(17, 4, 11, 11); ctx.stroke()
        ctx.move_to(15, 17); ctx.line_to(22, 10); ctx.stroke()
        _sp(ctx, [(22, 8), (24, 12), (19, 12)], True); ctx.fill()
    elif n == 'rotate':
        ctx.set_source_rgb(*BLUE); ctx.set_line_width(2)
        ctx.arc(16, 16, 9, -0.3, math.pi * 1.5); ctx.stroke()
        _sp(ctx, [(22, 3), (28, 8), (21, 10)], True); ctx.fill()
    elif n == 'pencil':
        ctx.set_source_rgb(0.95, 0.72, 0.10)
        _sp(ctx, [(5, 26), (9, 15), (21, 3), (29, 10), (17, 22)], True); ctx.fill()
        ctx.set_source_rgb(*DARK)
        _sp(ctx, [(5, 26), (9, 15), (21, 3), (29, 10), (17, 22)], True); ctx.stroke()
        _sp(ctx, [(5, 26), (9, 15), (13, 19)], True); ctx.set_source_rgb(0.9, 0.75, 0.55); ctx.fill()
        _sp(ctx, [(5, 26), (7, 21), (10, 24)], True); ctx.set_source_rgb(0.2, 0.2, 0.2); ctx.fill()
    elif n == 'fill':
        ctx.set_source_rgb(*BLUE)
        _sp(ctx, [(5, 6), (18, 18), (23, 13), (10, 4), (5, 6)], False)
        ctx.save()
        ctx.translate(18, 20); ctx.rotate(-0.7)
        ctx.scale(1, 0.6); ctx.arc(0, 0, 10, -1.2, 1.4)
        ctx.restore()
        ctx.set_line_width(1.8); ctx.stroke()
        ctx.set_source_rgba(0.2, 0.45, 0.75, 0.35)
        ctx.arc(24, 9, 4, 0, 2 * math.pi); ctx.fill()
    elif n == 'text':
        ctx.set_source_rgb(*BLUE)
        ctx.rectangle(4, 4, 24, 24); ctx.fill()
        ctx.set_source_rgb(*WHITE)
        ctx.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(21)
        ctx.move_to(9, 24); ctx.show_text('A')
    elif n == 'eraser':
        ctx.set_source_rgb(0.94, 0.70, 0.70)
        _sp(ctx, [(5, 22), (17, 6), (27, 14), (15, 28)], True); ctx.fill()
        ctx.set_source_rgb(*DARK)
        _sp(ctx, [(5, 22), (17, 6), (27, 14), (15, 28)], True); ctx.stroke()
        ctx.set_source_rgb(0.40, 0.68, 0.90); ctx.rectangle(4, 24, 24, 5); ctx.fill()
    elif n == 'picker':
        ctx.set_source_rgb(*DARK); ctx.set_line_width(2)
        ctx.move_to(6, 26); ctx.line_to(21, 10); ctx.stroke()
        ctx.set_source_rgb(*BLUE)
        _sp(ctx, [(18, 5), (29, 5), (29, 16), (25, 13), (18, 5)], True); ctx.fill()
        ctx.set_source_rgb(0.95, 0.75, 0.2); ctx.arc(5, 27, 3, 0, 2 * math.pi); ctx.fill()
    elif n == 'magnifier':
        ctx.set_source_rgb(*BLUE); ctx.set_line_width(3)
        ctx.arc(13, 13, 8, 0, 2 * math.pi); ctx.stroke()
        ctx.set_line_width(4); ctx.move_to(19, 19); ctx.line_to(28, 28); ctx.stroke()
        ctx.set_line_width(1); ctx.set_source_rgba(1,1,1,0.8)
        ctx.arc(11, 11, 3, 0, 2*math.pi); ctx.stroke()
    elif n == 'brush':
        ctx.set_source_rgb(0.82, 0.56, 0.30)
        _sp(ctx, [(6, 26), (14, 16), (22, 8), (27, 12), (18, 23), (9, 29)], True); ctx.fill()
        ctx.set_source_rgb(0.68, 0.42, 0.20)
        _sp(ctx, [(6, 26), (14, 16), (17, 20), (9, 29)], True); ctx.fill()
        ctx.set_source_rgb(0.25, 0.25, 0.25)
        ctx.move_to(21, 4); ctx.line_to(29, 12); ctx.set_line_width(4); ctx.stroke()
    elif n == 'line':
        ctx.set_source_rgb(*BLUE); ctx.set_line_width(2)
        ctx.move_to(5, 26); ctx.line_to(27, 6); ctx.stroke()
        ctx.set_source_rgb(*DARK)
        ctx.arc(5, 26, 2, 0, 2 * math.pi); ctx.fill(); ctx.arc(27, 6, 2, 0, 2 * math.pi); ctx.fill()
    elif n == 'curve':
        ctx.set_source_rgb(*BLUE); ctx.set_line_width(2)
        ctx.move_to(4, 25); ctx.curve_to(12, 2, 22, 30, 28, 7); ctx.stroke()
        ctx.set_source_rgb(*DARK)
        ctx.arc(4, 25, 2, 0, 2 * math.pi); ctx.fill(); ctx.arc(28, 7, 2, 0, 2 * math.pi); ctx.fill()
    elif n == 'shapes':
        ctx.set_source_rgb(*BLUE)
        ctx.rectangle(4, 5, 15, 12); ctx.stroke()
        ctx.arc(22, 22, 7, 0, 2 * math.pi); ctx.stroke()
        _sp(ctx, [(4, 29), (11, 17), (18, 29)], True); ctx.stroke()
    elif n == 'outline':
        ctx.set_source_rgb(*BLUE); ctx.set_line_width(1.5)
        ctx.rectangle(4, 6, 24, 20); ctx.stroke()
    elif n == 'fill_style':
        ctx.set_source_rgb(*BLUE)
        ctx.rectangle(4, 6, 24, 20); ctx.fill_preserve(); ctx.stroke()
        ctx.set_source_rgba(1,1,1,0.45); ctx.rectangle(8, 10, 8, 6); ctx.fill()
    elif n == 'color1':
        ctx.set_source_rgb(0, 0, 0); ctx.rectangle(4, 4, 24, 24); ctx.fill()
        ctx.set_source_rgb(0.7, 0.7, 0.7); ctx.set_line_width(1); ctx.rectangle(4.5, 4.5, 23, 23); ctx.stroke()
    elif n == 'color2':
        ctx.set_source_rgb(1, 1, 1); ctx.rectangle(4, 4, 24, 24); ctx.fill()
        ctx.set_source_rgb(0.55, 0.55, 0.55); ctx.set_line_width(1); ctx.rectangle(4.5, 4.5, 23, 23); ctx.stroke()
    elif n == 'edit_colors':
        for i, c in enumerate([RED, ORANGE, YELLOW, GREEN, BLUE, (0.55, 0.25, 0.7)]):
            ctx.set_source_rgb(*c)
            ctx.rectangle(3 + (i % 3) * 9, 7 + (i // 3) * 10, 8, 8); ctx.fill()
    elif n == 'paint3d':
        ctx.set_source_rgb(0.25, 0.55, 0.85)
        ctx.arc(16, 16, 10, 0, 2 * math.pi); ctx.fill()
        ctx.set_source_rgb(1, 1, 1); ctx.set_line_width(1.5)
        ctx.arc(16, 16, 5, 0, 2 * math.pi); ctx.stroke()
    elif n in ('plus', 'minus'):
        ctx.set_source_rgb(*DARK); ctx.set_line_width(2)
        ctx.move_to(8, 16); ctx.line_to(24, 16); ctx.stroke()
        if n == 'plus':
            ctx.move_to(16, 8); ctx.line_to(16, 24); ctx.stroke()
    elif n == 'new':
        ctx.set_source_rgb(*WHITE); ctx.rectangle(6, 5, 20, 23); ctx.fill()
        ctx.set_source_rgb(*GREY); ctx.rectangle(6, 5, 20, 23); ctx.stroke()
        ctx.set_source_rgb(*BLUE); ctx.set_line_width(2)
        ctx.move_to(16, 10); ctx.line_to(16, 22); ctx.move_to(10, 16); ctx.line_to(22, 16); ctx.stroke()
    elif n == 'open':
        ctx.set_source_rgb(0.95, 0.78, 0.30)
        _sp(ctx, [(3, 9), (13, 9), (16, 13), (29, 13), (26, 27), (5, 27)], True); ctx.fill()
        ctx.set_source_rgb(*DARK); ctx.stroke()
    elif n == 'print':
        ctx.set_source_rgb(*GREY); ctx.rectangle(7, 12, 18, 10); ctx.fill()
        ctx.set_source_rgb(1, 1, 1); ctx.rectangle(9, 4, 14, 9); ctx.fill()
        ctx.set_source_rgb(*DARK); ctx.rectangle(9, 4, 14, 9); ctx.stroke()
        ctx.set_source_rgb(1, 1, 1); ctx.rectangle(9, 22, 14, 6); ctx.fill()
        ctx.set_source_rgb(*DARK); ctx.rectangle(9, 22, 14, 6); ctx.stroke()
    elif n == 'home':
        ctx.set_source_rgb(*BLUE)
        _sp(ctx, [(3, 15), (16, 3), (29, 15), (25, 15), (25, 29), (7, 29), (7, 15)], True); ctx.fill()
        ctx.set_source_rgb(*WHITE); ctx.rectangle(13, 19, 6, 10); ctx.fill()
    elif n == 'grid':
        ctx.set_source_rgb(*BLUE); ctx.set_line_width(1.2)
        for i in range(4):
            x = 5 + i * 7.3
            ctx.move_to(x, 5); ctx.line_to(x, 27); ctx.stroke()
            ctx.move_to(5, x); ctx.line_to(27, x); ctx.stroke()
    elif n == 'ruler':
        ctx.set_source_rgb(0.95, 0.85, 0.45); ctx.rectangle(3, 11, 26, 10); ctx.fill()
        ctx.set_source_rgb(*DARK); ctx.rectangle(3, 11, 26, 10); ctx.stroke()
        for i in range(1, 6):
            ctx.move_to(3 + i * 4, 11); ctx.line_to(3 + i * 4, 11 + (5 if i % 2 else 8)); ctx.stroke()
    elif n == 'statusbar':
        ctx.set_source_rgb(*GREY); ctx.rectangle(3, 22, 26, 5); ctx.fill()
        ctx.set_source_rgb(*DARK); ctx.rectangle(3, 22, 26, 5); ctx.stroke()
    elif n == 'fullscreen':
        ctx.set_source_rgb(*DARK); ctx.set_line_width(2)
        _sp(ctx, [(4, 12), (4, 4), (12, 4)], False); ctx.stroke()
        _sp(ctx, [(20, 4), (28, 4), (28, 12)], False); ctx.stroke()
        _sp(ctx, [(28, 20), (28, 28), (20, 28)], False); ctx.stroke()
        _sp(ctx, [(12, 28), (4, 28), (4, 20)], False); ctx.stroke()
    elif n == 'thumbnail':
        ctx.set_source_rgb(*BLUE); ctx.set_line_width(1.5)
        ctx.rectangle(4, 4, 24, 24); ctx.stroke()
        ctx.rectangle(7, 7, 18, 18); ctx.stroke()
        ctx.set_source_rgba(0.18, 0.42, 0.7, 0.25); ctx.rectangle(7, 7, 18, 18); ctx.fill()
    elif n == 'zoomin' or n == 'zoomout':
        ctx.set_source_rgb(*BLUE); ctx.set_line_width(2.5)
        ctx.arc(13, 13, 7, 0, 2 * math.pi); ctx.stroke()
        ctx.set_line_width(3); ctx.move_to(18, 18); ctx.line_to(27, 27); ctx.stroke()
        ctx.set_line_width(1.8); ctx.set_source_rgb(*DARK)
        ctx.move_to(9, 13); ctx.line_to(17, 13); ctx.stroke()
        if n == 'zoomin':
            ctx.move_to(13, 9); ctx.line_to(13, 17); ctx.stroke()
    elif n == 'shape_more':
        ctx.set_source_rgb(*DARK); ctx.set_line_width(1.5)
        _sp(ctx, [(11, 6), (21, 16), (11, 26)], False); ctx.stroke()
    elif n == 'chevron_up':
        ctx.set_source_rgb(*DARK); ctx.set_line_width(1.6)
        _sp(ctx, [(8, 20), (16, 11), (24, 20)], False); ctx.stroke()
    elif n == 'chevron_down':
        ctx.set_source_rgb(*DARK); ctx.set_line_width(1.6)
        _sp(ctx, [(8, 12), (16, 21), (24, 12)], False); ctx.stroke()
    elif n == 'dropdown':
        ctx.set_source_rgb(*DARK)
        _sp(ctx, [(11, 13), (16, 19), (21, 13)], False); ctx.set_line_width(1.4); ctx.stroke()
    elif n == 'app':
        ctx.set_source_rgb(1, 1, 1); ctx.rectangle(3, 3, 26, 26); ctx.fill()
        ctx.set_source_rgba(0.65, 0.80, 0.95, 0.8); ctx.rectangle(4, 4, 24, 24); ctx.fill()
        ctx.set_source_rgb(*BLUE)
        ctx.arc(18, 11, 4, 0, 2*math.pi); ctx.fill()
        ctx.set_line_width(3); ctx.move_to(8, 27); ctx.curve_to(8, 18, 28, 18, 28, 27); ctx.stroke()
        ctx.set_source_rgb(0.40, 0.55, 0.75)
        ctx.set_line_width(2); ctx.move_to(5, 25); ctx.line_to(26, 25); ctx.stroke()
    else:
        ctx.set_source_rgb(*DARK)
        ctx.rectangle(6, 6, 20, 20); ctx.stroke()
    ctx.restore()


class PaintIcon(Gtk.DrawingArea):
    def __init__(self, name, size=24):
        super().__init__()
        self.icon_name = name
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_draw_func(self._draw)

    def set_icon(self, name):
        self.icon_name = name
        self.queue_draw()

    def _draw(self, area, ctx, width, height):
        draw_icon(ctx, self.icon_name, min(width, height))


def image(name, size=16):
    """Return a snapshot-backed Gtk.Image for menus."""
    from gi.repository import Gdk
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    draw_icon(ctx, name, size)
    texture = Gdk.Texture.new_for_pixbuf(_surface_to_pixbuf(surface))
    img = Gtk.Image.new_from_paintable(texture)
    img.set_pixel_size(size)
    return img


def _surface_to_pixbuf(surface):
    from gi.repository import GdkPixbuf
    w, h = surface.get_width(), surface.get_height()
    surface.flush()
    data = bytes(surface.get_data())
    return GdkPixbuf.Pixbuf.new_from_data(bytearray(data), GdkPixbuf.Colorspace.RGB,
                                           True, 8, w, h, surface.get_stride())
