# SPDX-License-Identifier: GPL-3.0-or-later
"""Test full mouse/tool flows using the canvas event entry points."""
import os,sys
import gi
gi.require_version('Gtk','4.0'); gi.require_version('Gdk','4.0')
from gi.repository import Gtk, Gdk, GLib
sys.path.insert(0,'.')
from mspaint.app import PaintWindow

results=[]
def check(n,c,e=''):
    results.append((n,bool(c),e)); print(('PASS' if c else 'FAIL'),n,e)

class FakeGesture:
    def __init__(self, button=1): self.button=button
    def get_current_button(self): return self.button

def pix(d,x,y):
    d.surface.flush(); data=d.surface.get_data(); s=d.surface.get_stride(); o=int(y)*s+int(x)*4
    return (data[o+2],data[o+1],data[o],data[o+3])

def drag(canvas,x0,y0,x1,y1,button=1):
    g=FakeGesture(button)
    canvas._on_drag_begin(g,*canvas.image_to_view(x0,y0))
    canvas._on_drag_update(g,x1-x0,y1-y0)
    canvas._on_drag_end(g,x1-x0,y1-y0)

def main():
    app=Gtk.Application(application_id='io.github.mspaint_linux.InteractionTest'); app.register(None)
    win=PaintWindow(app); win.present(); loop=GLib.MainLoop()
    def run():
        try:
            cv=win.canvas; d=win.doc
            # 1 px pencil: a single click must change exactly one pixel
            cv.set_tool('pencil')
            cv.line_width = 1
            win._clear_image()
            g0=FakeGesture()
            cv._on_drag_begin(g0, *cv.image_to_view(20.7, 30.3))
            cv._on_drag_end(g0, 0, 0)
            changed = 0
            for yy in range(d.height):
                for xx in range(d.width):
                    if pix(d, xx, yy) != (255, 255, 255, 255):
                        changed += 1
            check('1px pencil click changes one pixel', changed == 1, f'{changed} pixels')
            # pencil drag
            cv.set_tool('pencil')
            drag(cv,10,10,100,100)
            check('pencil stroke', pix(d,50,50)[:3] != (255,255,255), str(pix(d,50,50)))
            check('modified after stroke', d.dirty)
            win._undo()
            check('undo after stroke', pix(d,50,50)==(255,255,255,255), str(pix(d,50,50)))
            # line
            cv.set_tool('line'); cv.line_width=3
            drag(cv,20,30,120,80)
            check('line drawn', any(pix(d,x,y)[:3]!=(255,255,255) for x in range(20,121) for y in range(30,81)))
            win._undo()
            # rectangle shape filled
            cv.set_tool('rectangle'); cv.fill_style='solid'; cv.outline_style='solid'
            cv.set_colors(color1=(0,0,0),color2=(255,0,0))
            drag(cv,10,10,100,80)
            check('shape fill red', pix(d,50,40)[:3]==(255,0,0), str(pix(d,50,40)))
            win._undo()
            # flood fill
            cv.set_tool('fill'); cv.set_colors(color1=(0,255,0))
            drag(cv,10,10,10,10)
            check('bucket fill', pix(d,10,10)[:3]==(0,255,0), str(pix(d,10,10)))
            win._undo()
            # selection create
            cv.set_tool('select')
            drag(cv,20,20,120,100)
            check('selection exists', d.selection is not None and d.selection.rect==(20,20,100,80), str(d.selection))
            # draw something inside selection to move
            cv.set_colors(color1=(0,0,255))
            cv.set_tool('pencil'); drag(cv,40,40,60,60)
            cv.set_tool('select')
            # selection should still exist
            check('selection preserved on tool change', d.selection is not None, str(d.selection))
            g=FakeGesture()
            sx,sy=cv.image_to_view(50,50)
            cv._on_drag_begin(g,sx,sy)
            check('selection lifted for move', d.selection.floating is not None, str(d.selection))
            cv._on_drag_update(g,30,20)
            check('floating origin updated', d.selection.floating_origin==(50,40), str(d.selection.floating_origin))
            cv._on_drag_end(g,30,20)
            cv.commit_floating()
            check('selection frame follows moved content', d.selection.rect==(50,40,100,80), str(d.selection.rect))
            # delete via window key controller (Paint fills with colour 2)
            cv.set_colors(color2=(255,255,255))
            handled=win._on_window_key(None,Gdk.KEY_Delete,0,0)
            check('delete key through window', handled and d.selection is None)
            check('delete clears to white', pix(d,60,80)==(255,255,255,255), str(pix(d,60,80)))
            # free select with multiple motion samples
            cv.set_tool('free_select')
            g=FakeGesture()
            cv._on_drag_begin(g,*cv.image_to_view(10,10))
            for i in range(1,9):
                cv._on_drag_update(g, i*8, i*5)
            cv._on_drag_end(g,80,40)
            check('free selection exists', d.selection is not None and bool(d.selection.polygon), str(d.selection))
            # selection handle resize
            cv.set_tool('select')
            drag(cv,10,10,110,90)
            check('selection for resize', d.selection is not None and d.selection.rect==(10,10,100,80), str(d.selection))
            g=FakeGesture()
            cv._on_drag_begin(g,*cv.image_to_view(110,90))
            check('resize handle hit', cv._mode=='resize_selection', cv._mode)
            cv._on_drag_update(g,40,30)
            cv._on_drag_end(g,40,30)
            check('selection resized from handle', d.selection is not None and d.selection.w==140 and d.selection.h==110, str(d.selection))
            # clear
            win._clear_image(); check('clear image', pix(d,10,10)==(255,255,255,255))
        except Exception as e:
            import traceback; traceback.print_exc(); check('exception',False,repr(e))
        print('RESULTS',sum(1 for _,ok,_ in results if ok),'/',len(results))
        loop.quit(); return False
    GLib.timeout_add(600,run); GLib.timeout_add(10000,loop.quit); loop.run()
if __name__=='__main__': main()
