# SPDX-License-Identifier: GPL-3.0-or-later
"""Text-tool rendering using Pango/Cairo."""
from __future__ import annotations

import gi
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Pango, PangoCairo


def make_layout(ctx, text, family, size_pt, bold=False, italic=False, underline=False,
                alignment='left'):
    layout = PangoCairo.create_layout(ctx)
    desc = Pango.FontDescription()
    desc.set_family(family or 'Sans')
    desc.set_size(int(round(size_pt * Pango.SCALE)))
    desc.set_weight(Pango.Weight.BOLD if bold else Pango.Weight.NORMAL)
    desc.set_style(Pango.Style.ITALIC if italic else Pango.Style.NORMAL)
    layout.set_font_description(desc)
    attrs = Pango.AttrList()
    if underline:
        attrs.insert(Pango.attr_underline_new(Pango.Underline.SINGLE))
        layout.set_attributes(attrs)
    layout.set_text(text, -1)
    layout.set_width(-1)
    if alignment == 'center':
        layout.set_alignment(Pango.Alignment.CENTER)
    elif alignment == 'right':
        layout.set_alignment(Pango.Alignment.RIGHT)
    else:
        layout.set_alignment(Pango.Alignment.LEFT)
    return layout


def text_extents(ctx, text, family, size_pt, bold=False, italic=False, underline=False):
    layout = make_layout(ctx, text, family, size_pt, bold, italic, underline)
    ink, logical = layout.get_pixel_extents()
    return logical.width, logical.height


def draw_text(ctx, text, x, y, family, size_pt, bold=False, italic=False,
              underline=False, color=(0, 0, 0), background=None, opaque=False,
              alignment='left'):
    """Render text; returns (width, height) in pixels.

    ``color`` and ``background`` are (r,g,b) floats.  The caller has already
    positioned the context in image coordinates.
    """
    layout = make_layout(ctx, text or ' ', family, size_pt, bold, italic, underline, alignment)
    ink, logical = layout.get_pixel_extents()
    w = max(1, logical.width)
    h = max(1, logical.height)
    if opaque and background is not None:
        ctx.save()
        ctx.set_source_rgb(*background)
        ctx.rectangle(x, y, w, h)
        ctx.fill()
        ctx.restore()
    ctx.save()
    ctx.set_source_rgb(*color)
    ctx.move_to(x, y)
    PangoCairo.show_layout(ctx, layout)
    ctx.restore()
    return w, h
