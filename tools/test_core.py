# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless tests for raster/document behaviour."""
import os, sys, tempfile, traceback
import cairo
sys.path.insert(0, '.')

from mspaint.document import Document, Selection, surface_to_pil, pil_to_surface
from mspaint.raster import (bucket_fill, draw_freehand, fill_shape, stroke_segment,
                            draw_eraser, pick_color)
from mspaint.shapes import SHAPE_ORDER
from mspaint.text import draw_text
from PIL import Image

results=[]
def check(name, cond, extra=''):
    results.append((name,bool(cond),extra)); print(('PASS' if cond else 'FAIL'), name, extra)

def pix(surface,x,y):
    surface.flush(); d=surface.get_data(); s=surface.get_stride(); o=y*s+x*4
    return (d[o+2],d[o+1],d[o],d[o+3])

def main():
    # raster basics
    d=Document(320,240)
    check('new document white', pix(d.surface,0,0)==(255,255,255,255), pix(d.surface,0,0))
    d.push_undo('pencil'); ctx=cairo.Context(d.surface)
    ctx.set_source_rgb(0,0,0); ctx.set_line_width(1); ctx.move_to(10,10); ctx.line_to(100,100); ctx.stroke()
    d.dirty=True
    check('draw pixel', pix(d.surface,10,10)[:3] != (255,255,255), pix(d.surface,10,10))
    check('undo stack', d.can_undo())
    d.undo(); check('undo restores', pix(d.surface,10,10)==(255,255,255,255), pix(d.surface,10,10))
    d.redo(); check('redo restores', pix(d.surface,10,10)[:3] != (255,255,255), pix(d.surface,10,10))
    d.undo()

    # brushes
    for brush in ['brush','calligraphy1','calligraphy2','airbrush','paintbrush','crayon','marker','pencil','watercolor']:
        d2=Document(160,120)
        try:
            c=cairo.Context(d2.surface)
            draw_freehand(c, [(10,10),(30,40),(80,80),(120,30)], (0,0,0), 8, brush, seed=1)
            check('brush '+brush, True)
        except Exception as e:
            check('brush '+brush, False, repr(e))

    # every shape
    for shape in SHAPE_ORDER:
        d2=Document(200,160)
        try:
            c=cairo.Context(d2.surface)
            if shape=='curve':
                from mspaint.raster import draw_curve
                draw_curve(c,(10,10),(180,140),(50,120),(140,20),(0,0,0),2)
            else:
                fill_shape(c, shape, 10, 10, 170, 130, 'solid', (1,0,0), 'solid', (0,0,0), 2)
            check('shape '+shape, True)
        except Exception as e:
            check('shape '+shape, False, repr(e))

    # bucket fill
    d2=Document(80,80)
    bucket_fill(d2.surface, 20,20, (1,0,0))
    check('flood fill', pix(d2.surface,40,40)==(255,0,0,255), pix(d2.surface,40,40))
    check('picker', pick_color(d2.surface,40,40)==(255,0,0,255), pick_color(d2.surface,40,40))

    # transformations and selection
    d2=Document(120,90); c=cairo.Context(d2.surface)
    c.set_source_rgb(0,0,1); c.rectangle(10,10,30,20); c.fill()
    d2.selection=Selection(10,10,30,20)
    d2.rotate('right')
    check('rotate selection dims', (d2.width,d2.height)==(120,90), (d2.width,d2.height))
    check('selection rotated', d2.selection.rect==(10,10,20,30), d2.selection.rect)
    d2.undo()
    d2.selection=Selection(10,10,30,20)
    s=d2.get_selection_surface(); check('selection surface', s is not None and s.get_width()==30)
    d2.delete_selection((1,1,1,1))
    check('delete selection white', pix(d2.surface,20,20)==(255,255,255,255), pix(d2.surface,20,20))
    d2.selection=Selection(0,0,d2.width,d2.height)
    d2.crop(); check('crop', (d2.width,d2.height)==(120,90))
    d2.resize(240,180); check('resize', (d2.width,d2.height)==(240,180), (d2.width,d2.height))
    d2.skew(10,5); check('skew', d2.width>240 and d2.height>180, (d2.width,d2.height))

    # format round trips
    d3=Document(64,48); c=cairo.Context(d3.surface)
    c.set_source_rgb(1,0,0); c.rectangle(0,0,32,48); c.fill()
    tmp=tempfile.mkdtemp()
    for fmt, ext in [('png','png'),('jpg','jpg'),('bmp','bmp'),('gif','gif'),('dib','dib')]:
        p=os.path.join(tmp,'test.'+ext)
        try:
            d3.save(p, fmt=fmt)
            opened=Document.open(p)
            check('format '+fmt, opened.width==64 and opened.height==48, f'{opened.width}x{opened.height}')
            # JPEG tolerance
            r,g,b,a = pix(opened.surface, 8, 8)
            check('format pixel '+fmt, r>200 and g<80, (r,g,b,a))
        except Exception as e:
            check('format '+fmt, False, repr(e))
    for bits in (1,4,8,24):
        p=os.path.join(tmp,f'test{bits}.bmp')
        try:
            d3.save(p, fmt='bmp', bits=bits)
            check(f'bmp {bits}bit', os.path.getsize(p)>0, os.path.getsize(p))
        except Exception as e:
            check(f'bmp {bits}bit', False, repr(e))

    # text
    d4=Document(300,100)
    try:
        c=cairo.Context(d4.surface)
        w,h=draw_text(c,'Hello 你好',10,10,'Sans',16,True,False,False,(0,0,0),(1,1,1),True)
        check('text extents', w>10 and h>5, (w,h))
    except Exception as e:
        check('text render', False, repr(e))

    # paste/floating
    d5=Document(100,100); d5.selection=Selection(0,0,20,20)
    c=cairo.Context(d5.surface); c.set_source_rgb(0,1,0); c.rectangle(0,0,20,20); c.fill()
    sf=d5.get_selection_surface(); d5.lift_selection()
    check('lift selection', d5.selection.floating is not None)
    d5.selection.floating_origin=(30,40)
    d5.flatten_selection()
    check('flatten at origin', pix(d5.surface,35,45)[:3]==(0,255,0), pix(d5.surface,35,45))
    check('flatten geometry', (d5.selection.x,d5.selection.y)==(30,40), d5.selection.rect)

    print('RESULTS', sum(1 for _,ok,_ in results if ok), '/', len(results))
    fails=[n for n,ok,_ in results if not ok]
    print('FAILED', fails)
    return 0 if not fails else 1

if __name__=='__main__':
    sys.exit(main())
