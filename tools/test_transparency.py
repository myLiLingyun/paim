# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression tests for transparent-image editing and alpha-preserving I/O."""
from __future__ import annotations

import os
import sys
import tempfile

import cairo
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mspaint.app import PaintWindow
from mspaint.dialogs import AttributesDialog
from mspaint.document import Document, Selection, surface_to_pil
from mspaint.raster import draw_eraser

results = []


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)


def pix(surface, x, y):
    surface.flush()
    data = surface.get_data()
    stride = surface.get_stride()
    off = int(y) * stride + int(x) * 4
    return (data[off + 2], data[off + 1], data[off], data[off + 3])


def make_transparent_png():
    im = Image.new('RGBA', (40, 30), (0, 0, 0, 0))
    for y in range(10):
        for x in range(10):
            im.putpixel((x, y), (255, 0, 0, 255))
    path = os.path.join(tempfile.mkdtemp(), 'transparent.png')
    im.save(path)
    return path


def test_document():
    d = Document(32, 24, transparent=True)
    check('new transparent document', d.transparent and pix(d.surface, 5, 5)[3] == 0,
          f'{d.background} {pix(d.surface, 5, 5)}')
    d.clear_image()
    check('clear transparent image', pix(d.surface, 5, 5)[3] == 0, pix(d.surface, 5, 5))

    path = make_transparent_png()
    d = Document.open(path)
    check('open detects transparency', d.transparent and d.has_alpha, f'{d.background}')
    check('open preserves alpha', pix(d.surface, 5, 5) == (255, 0, 0, 255)
          and pix(d.surface, 30, 20)[3] == 0,
          f'{pix(d.surface, 5, 5)} {pix(d.surface, 30, 20)}')
    check('opaque export flattens to white',
          d.to_pil(with_alpha=False).getpixel((30, 20)) == (255, 255, 255),
          str(d.to_pil(with_alpha=False).getpixel((30, 20))))

    out = os.path.join(tempfile.mkdtemp(), 'out.png')
    d.save(out)
    im = Image.open(out)
    check('png save preserves alpha',
          im.mode == 'RGBA' and im.getpixel((5, 5))[3] == 255 and im.getpixel((30, 20))[3] == 0,
          f'{im.mode} {im.getpixel((5, 5))} {im.getpixel((30, 20))}')

    for fmt, ext in (('gif', 'gif'), ('webp', 'webp')):
        out = os.path.join(tempfile.mkdtemp(), f'out.{ext}')
        d.save(out, fmt=fmt)
        im = Image.open(out).convert('RGBA')
        check(f'{fmt} save preserves alpha',
              im.getpixel((5, 5))[3] == 255 and im.getpixel((30, 20))[3] == 0,
              f'{im.getpixel((5, 5))} {im.getpixel((30, 20))}')

    # Alpha-aware clearing / selection operations.
    d = Document(30, 30, transparent=True)
    ctx = cairo.Context(d.surface)
    ctx.set_source_rgba(0, 0, 1, 1)
    ctx.rectangle(0, 0, 30, 30)
    ctx.fill()
    d.selection = Selection(5, 5, 10, 10)
    d.delete_selection()
    check('delete selection clears alpha', pix(d.surface, 8, 8)[3] == 0,
          pix(d.surface, 8, 8))
    check('delete selection keeps outside', pix(d.surface, 20, 20) == (0, 0, 255, 255),
          pix(d.surface, 20, 20))

    d = Document(30, 30, transparent=True)
    ctx = cairo.Context(d.surface)
    ctx.set_source_rgba(0, 0, 1, 1)
    ctx.rectangle(0, 0, 30, 30)
    ctx.fill()
    d.selection = Selection(0, 0, 10, 10, polygon=[(2, 2), (8, 2), (8, 8), (2, 8)])
    d.delete_selection()
    check('polygon delete clears alpha', pix(d.surface, 5, 5)[3] == 0, pix(d.surface, 5, 5))
    check('polygon delete keeps outside', pix(d.surface, 20, 20)[3] == 255,
          pix(d.surface, 20, 20))

    d = Document(30, 30, transparent=True)
    ctx = cairo.Context(d.surface)
    ctx.set_source_rgba(0, 0, 1, 1)
    ctx.rectangle(0, 0, 30, 30)
    ctx.fill()
    d.selection = Selection(5, 5, 10, 10)
    d.lift_selection()
    check('lifting selection leaves transparent hole', pix(d.surface, 8, 8)[3] == 0,
          pix(d.surface, 8, 8))
    check('lifting selection keeps outside', pix(d.surface, 20, 20)[3] == 255,
          pix(d.surface, 20, 20))

    d = Document(20, 20, transparent=True)
    ctx = cairo.Context(d.surface)
    ctx.set_source_rgba(1, 0, 0, 1)
    ctx.rectangle(0, 0, 20, 20)
    ctx.fill()
    draw_eraser(ctx, 10, 10, 6, (1, 1, 1), clear=True)
    check('transparent eraser', pix(d.surface, 10, 10)[3] == 0, pix(d.surface, 10, 10))

    d.resize_canvas(40, 40)
    check('resize canvas fills transparent background', pix(d.surface, 35, 35)[3] == 0,
          pix(d.surface, 35, 35))

    d = Document(20, 20)
    ctx = cairo.Context(d.surface)
    ctx.set_source_rgba(1, 0, 0, 1)
    ctx.rectangle(0, 0, 20, 20)
    ctx.fill()
    draw_eraser(ctx, 10, 10, 6, (1, 1, 1))
    check('opaque eraser keeps classic behaviour', pix(d.surface, 10, 10) == (255, 255, 255, 255),
          pix(d.surface, 10, 10))


def test_ui(win):
    path = make_transparent_png()
    win.load_path(path)
    d = win.doc
    check('UI loads transparent image', d.transparent and d.has_alpha, str(d.background))

    dialog = AttributesDialog(win, d, lambda *a: None)
    check('properties dialog reflects transparency', dialog.transparent.get_active())
    dialog.destroy()

    # Checkerboard should be visible through fully transparent pixels.
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 160, 140)
    ctx = cairo.Context(surface)
    win.canvas._draw(None, ctx, 160, 140)
    surface.flush()
    data = surface.get_data()
    stride = surface.get_stride()
    ox, oy = win.canvas.image_origin()
    shades = set()
    for x in range(1, 20):
        off = (oy + 1) * stride + (ox + x) * 4
        shades.add((data[off + 2], data[off + 1], data[off]))
    check('transparent pixels show checkerboard', len(shades) > 1, str(shades))

    class FakeGesture:
        def get_current_button(self):
            return 1

    win.canvas.set_tool('eraser')
    win.canvas.line_width = 4
    g = FakeGesture()
    win.canvas._on_drag_begin(g, *win.canvas.image_to_view(20, 20))
    win.canvas._on_drag_end(g, 0, 0)
    check('UI eraser clears alpha', pix(d.surface, 20, 20)[3] == 0,
          pix(d.surface, 20, 20))

    win.canvas.select_all()
    win._on_window_key(None, Gdk.KEY_Delete, 0, 0)
    check('UI delete clears to transparency', pix(d.surface, 20, 20)[3] == 0,
          pix(d.surface, 20, 20))

    out = os.path.join(tempfile.mkdtemp(), 'ui.png')
    win._save_to_path(out, fmt='png')
    im = Image.open(out)
    check('UI save preserves transparency',
          im.mode == 'RGBA' and im.getpixel((20, 20))[3] == 0,
          f'{im.mode} {im.getpixel((20, 20))}')


def main():
    test_document()
    app = Gtk.Application(application_id='io.github.paim.TransparencyTest')
    app.register(None)
    win = PaintWindow(app)
    win.present()
    loop = GLib.MainLoop()

    def run():
        try:
            test_ui(win)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            check('transparency UI exception', False, repr(exc))
        print('RESULTS', sum(1 for _, ok, *_ in results if ok), '/', len(results))
        loop.quit()
        return False

    GLib.timeout_add(500, run)
    GLib.timeout_add(15000, loop.quit)
    loop.run()
    return 0 if all(ok for _, ok, *_ in results) else 1


if __name__ == '__main__':
    sys.exit(main())
