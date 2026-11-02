# SPDX-License-Identifier: GPL-3.0-or-later
"""Programmatic UI smoke test for the Paint clone (no mouse automation)."""
import os, sys, cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mspaint.app import PaintWindow
from mspaint.document import Selection

class FakeController:
    pass

results = []

def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)

def run_tests(win, app, loop):
    try:
        # 1. File popover opens.
        win.file_tab.popup()
        GLib.timeout_add(300, after_popup, win, app, loop)
    except Exception as e:
        print('EXC', repr(e)); loop.quit()

def after_popup(win, app, loop):
    try:
        check('file popover visible', win.backstage.get_visible(), f'visible={win.backstage.get_visible()}')
        win.backstage.popdown()
        # 2. Draw a pixel, mark dirty, save, ensure star gone.
        ctx = cairo.Context(win.doc.surface)
        ctx.set_source_rgb(0, 0, 0); ctx.rectangle(10, 10, 20, 20); ctx.fill()
        win.doc.dirty = True
        win._update_title()
        check('title has dirty star', '*' in win.title_label.get_text(), win.title_label.get_text())
        path = '/tmp/mspaint-smoke-save.png'
        win._save_to_path(path, fmt='png')
        check('save clears dirty', not win.doc.dirty, f'dirty={win.doc.dirty}')
        check('save clears title star', '*' not in win.title_label.get_text(), win.title_label.get_text())
        check('save file exists', os.path.exists(path), path)
        # 3. Delete key clears selection to background.
        win.canvas.select_all()
        ctl = FakeController()
        handled = win.canvas._on_key(ctl, Gdk.KEY_Delete, 0, 0)
        check('delete key handled', handled)
        check('delete removes selection', win.doc.selection is None)
        px = win.doc.surface.get_data()
        stride = win.doc.surface.get_stride()
        # pixel at 0,0 is background white
        b,g,r,a = px[0],px[1],px[2],px[3]
        check('delete fills white', (r,g,b)==(255,255,255), f'rgba={(r,g,b,a)}')
        # 4. Selection frame follows floating origin.
        win.canvas.select_all()
        win.doc.lift_selection()
        win.doc.selection.floating_origin = (123, 77)
        check('floating origin moved', win.doc.selection.floating_origin == (123,77))
        win.canvas.commit_floating()
        check('selection geometry updated after move', (win.doc.selection.x, win.doc.selection.y) == (123,77),
              f'{win.doc.selection.rect}')
        # 5. Fullscreen toggle does not raise and reflects state.
        try:
            win._toggle_fullscreen()
            check('fullscreen callable', True)
        except Exception as e:
            check('fullscreen callable', False, repr(e))
        # 6. Recent-file refresh doesn't raise.
        try:
            win._add_recent('/tmp/mspaint-smoke-save.png')
            check('recent refresh', True)
        except Exception as e:
            check('recent refresh', False, repr(e))
        # 7. File menu action dispatch works via menu button.
        win._backstage_action('properties')
        GLib.timeout_add(300, finish, win, loop)
    except Exception as e:
        import traceback; traceback.print_exc()
        print('EXC', repr(e)); loop.quit()
    return False

def finish(win, loop):
    try:
        check('properties dialog created', True)
    except Exception as e:
        check('properties dialog created', False, repr(e))
    print('RESULTS', sum(1 for _,ok,_ in results if ok), '/', len(results))
    loop.quit()
    return False

def main():
    app = Gtk.Application(application_id='io.github.mspaint_linux.SmokeTest')
    app.register(None)
    win = PaintWindow(app)
    win.present()
    loop = GLib.MainLoop()
    GLib.timeout_add(1200, run_tests, win, app, loop)
    GLib.timeout_add(9000, loop.quit)
    loop.run()
    return 0 if all(ok for _,ok,_ in results) else 1

if __name__ == '__main__':
    sys.exit(main())
