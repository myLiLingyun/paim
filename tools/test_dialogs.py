# SPDX-License-Identifier: GPL-3.0-or-later
import os,sys
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk, GLib, Gdk
sys.path.insert(0,'.')
from mspaint.app import PaintWindow
from mspaint.dialogs import (ResizeDialog, AttributesDialog, ColorDialog, SaveOptionsDialog,
                             PageSetupDialog, AboutDialog, MessageDialog)

results=[]
def check(n,c,e=''): results.append((n,bool(c))); print(('PASS' if c else 'FAIL'),n,e)

def main():
    app=Gtk.Application(application_id='io.github.mspaint_linux.DialogTest'); app.register(None)
    win=PaintWindow(app); win.present()
    loop=GLib.MainLoop()
    def step1():
        try:
            # ResizeDialog creates + apply callback
            got={}
            d=ResizeDialog(win,100,50,lambda *a: got.setdefault('resize',a)); d.present()
            d.hspin.set_value(200); d.apply(); d.destroy()
            check('resize dialog callback', got.get('resize',(None,))[0]==200, got)
            d=AttributesDialog(win,win.doc,lambda *a: got.setdefault('attr',a)); d.present(); d.apply(); d.destroy()
            check('attributes dialog', 'attr' in got, got)
            d=ColorDialog(win,(0,0,0),lambda c: got.setdefault('color',c)); d.present(); d.apply(); d.destroy()
            check('color dialog', 'color' in got, got)
            d=SaveOptionsDialog(win,'bmp',lambda f,b: got.setdefault('save',(f,b))); d.present(); d.apply(); d.destroy()
            check('save options', got.get('save')==('bmp',24), got.get('save'))
            d=PageSetupDialog(win,win.page_settings,lambda s: got.setdefault('page',s)); d.present(); d.apply(); d.destroy()
            check('page setup', 'page' in got, got)
            d=AboutDialog(win); d.present(); d.destroy()
            check('about dialog', True)
            d=MessageDialog(win,'test','secondary',Gtk.MessageType.ERROR); d.present(); d.destroy()
            check('message dialog', True)
            # text render through view's method not needed
        except Exception as e:
            import traceback; traceback.print_exc(); check('dialogs',False,repr(e))
        print('RESULTS',sum(1 for _,ok in results if ok),'/',len(results)); loop.quit(); return False
    GLib.timeout_add(800,step1); GLib.timeout_add(9000,loop.quit); loop.run()
if __name__=='__main__': main()
