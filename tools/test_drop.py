# SPDX-License-Identifier: GPL-3.0-or-later
import sys, os, gi, tempfile
gi.require_version('Gtk','4.0'); gi.require_version('Gdk','4.0')
from gi.repository import Gtk, Gdk, Gio, GLib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mspaint.app import PaintWindow
from PIL import Image
results=[]
def check(n,c,e=''): results.append((n,bool(c))); print(('PASS' if c else 'FAIL'),n,e)
def main():
    td=tempfile.mkdtemp(); p=os.path.join(td,'drop.png')
    Image.new('RGB',(123,77),(255,0,0)).save(p)
    app=Gtk.Application(application_id='io.github.paim.DropTest'); app.register(None)
    win=PaintWindow(app); win.present(); loop=GLib.MainLoop()
    def run():
        try:
            check('drop target exists', hasattr(win,'_file_drop_target'))
            fl=Gdk.FileList.new_from_list([Gio.File.new_for_path(p)])
            ok=win._on_drop(None, fl, 0, 0)
            check('drop accepted', ok)
            check('drop loaded', win.doc.filename==p and (win.doc.width,win.doc.height)==(123,77), f'{win.doc.filename} {win.doc.width}x{win.doc.height}')
            # non-image
            q=os.path.join(td,'x.txt'); open(q,'w').write('hello')
            fl2=Gdk.FileList.new_from_list([Gio.File.new_for_path(q)])
            # find last dialog child; just verify return False and no crash
            ok2=win._on_drop(None, fl2, 0, 0)
            check('non-image rejected', ok2 is False)
            check('drop hint hidden', not win.drop_hint.get_visible())
        except Exception as e:
            import traceback; traceback.print_exc(); check('drop exception',False,repr(e))
        print('RESULTS',sum(1 for _,ok in results if ok),'/',len(results))
        loop.quit(); return False
    GLib.timeout_add(500,run); GLib.timeout_add(8000,loop.quit); loop.run()
if __name__=='__main__': main()
