# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression test: English UI must not leak unlocalised Chinese strings."""
import os
import re
import sys
import tempfile

os.environ['XDG_CONFIG_HOME'] = tempfile.mkdtemp(prefix='paim-i18n-')
os.environ.setdefault('PAIM_LANG', 'en')
os.environ.setdefault('LANG', 'en_US.UTF-8')
os.environ.setdefault('LANGUAGE', 'en')

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mspaint.app import PaintWindow
from mspaint.dialogs import (ResizeDialog, AttributesDialog, ColorDialog,
                             SaveOptionsDialog, PageSetupDialog)

CJK = re.compile('[\u4e00-\u9fff]')
results = []


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)


def collect(widget, out):
    if isinstance(widget, Gtk.Label):
        text = widget.get_text()
        if text:
            out.append(text)
    if isinstance(widget, Gtk.Button) and widget.get_label():
        out.append(widget.get_label())
    if isinstance(widget, Gtk.CheckButton) and widget.get_label():
        out.append(widget.get_label())
    if isinstance(widget, Gtk.DropDown):
        model = widget.get_model()
        if model:
            for i in range(model.get_n_items()):
                try:
                    out.append(model.get_item_string(i) or '')
                except Exception:
                    pass
    child = widget.get_first_child()
    while child:
        collect(child, out)
        child = child.get_next_sibling()


def main():
    app = Gtk.Application(application_id='io.github.paim.I18nTest')
    app.register(None)
    win = PaintWindow(app)
    win.present()
    dialogs = [
        ResizeDialog(win, 100, 100, lambda *a: None),
        AttributesDialog(win, win.doc, lambda *a: None),
        ColorDialog(win, (0, 0, 0), lambda *a: None),
        SaveOptionsDialog(win, 'bmp', lambda *a: None),
        PageSetupDialog(win, win.page_settings, lambda *a: None),
    ]
    for dialog in dialogs:
        dialog.present()
    ctx = GLib.MainContext.default()
    for _ in range(30):
        ctx.iteration(False)
    out = []
    collect(win, out)
    for dialog in dialogs:
        collect(dialog, out)
        if dialog.get_title():
            out.append(dialog.get_title())
    # QAT menu popovers and customize list must be localised too.
    win._quick_customize()
    if win._qat_customize_popover:
        collect(win._qat_customize_popover, out)
        win._qat_customize_popover.popdown()
        win._qat_customize_popover.unparent()
    for kind in ('shapes', 'rotate', 'outline', 'fill', 'size', 'colors', 'theme'):
        pop = win._build_qat_menu(kind)
        collect(pop, out)
        pop.unparent()
    win._show_qat_context(win.paste_btn, 'paste')
    if win._qat_context_popover:
        collect(win._qat_context_popover, out)
        win._qat_context_popover.popdown()
        win._qat_context_popover.unparent()
    chinese = [text for text in out if CJK.search(text)]
    check('language is English', not win.lang_zh, 'lang_zh=%s' % win.lang_zh)
    check('theme menu localised', win.theme_mode_label.get_text() == 'Theme: System',
          win.theme_mode_label.get_text())
    check('no Chinese visible labels', not chinese, str(chinese[:8]))
    check('Untitled default filename', win.tr('无标题', 'Untitled') + '.png' == 'Untitled.png')
    for dialog in dialogs:
        dialog.destroy()
    win.destroy()
    app.quit()
    print('RESULTS', sum(1 for _, ok, *_ in results if ok), '/', len(results))
    return 0 if all(ok for _, ok, *_ in results) else 1


if __name__ == '__main__':
    sys.exit(main())
