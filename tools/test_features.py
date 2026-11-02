# SPDX-License-Identifier: GPL-3.0-or-later
"""Test paim-specific features: theme preference and Quick Access Toolbar."""
import json
import os
import sys
import tempfile

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mspaint.app import PaintWindow

results = []
def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS' if cond else 'FAIL'), name, extra)


def main():
    app = Gtk.Application(application_id='io.github.paim.FeatureTest')
    app.register(None)
    win = PaintWindow(app)
    win.present()
    loop = GLib.MainLoop()

    def run():
        try:
            check('default theme mode auto', win.theme_mode == 'auto', win.theme_mode)
            check('default QAT', win.qat_pinned[:3] == ['save', 'undo', 'redo'], str(win.qat_pinned))

            win._set_theme_mode('dark')
            check('manual dark', win.dark_mode is True and win.theme_mode == 'dark')
            win.theme_mode_buttons['light'].set_active(True)
            check('theme menu drives mode', win.theme_mode == 'light' and win.dark_mode is False,
                  f'{win.theme_mode}/{win.dark_mode}')
            win._set_theme_mode('dark')
            win._set_theme_mode('light')
            check('manual light', win.dark_mode is False and win.theme_mode == 'light')
            win._set_theme_mode('auto')
            check('auto theme restored', win.theme_mode == 'auto')

            win._toggle_qat_pin('pencil', True)
            check('QAT pin adds button', 'pencil' in win.qat_buttons and 'pencil' in win.qat_pinned,
                  str(win.qat_pinned))
            win._toggle_qat_pin('pencil', False)
            check('QAT unpin removes button', 'pencil' not in win.qat_buttons)

            new_keys = ['rotate', 'shapes', 'outline', 'fill-style', 'size', 'colors',
                        'zoom-100', 'ruler', 'grid', 'statusbar', 'thumbnail', 'theme']
            for key in new_keys:
                win._toggle_qat_pin(key, True)
            check('extended QAT commands pinned', all(k in win.qat_buttons for k in new_keys),
                  str(win.qat_pinned))
            menus_ok = True
            for key in new_keys:
                spec = win.qat_registry.get(key, {})
                if spec.get('menu'):
                    p = win._build_qat_menu(spec['menu'])
                    if p is None:
                        menus_ok = False
                    p.unparent()
            check('QAT menus construct', menus_ok)
            for key in new_keys:
                win._toggle_qat_pin(key, False)

            # Context menu / customize popover can be opened and closed.
            win._show_qat_context(win.paste_btn, 'paste')
            check('QAT context popover', win._qat_context_popover is not None)
            if win._qat_context_popover:
                win._qat_context_popover.popdown()
                win._qat_context_popover.unparent()
            win._quick_customize()
            check('QAT customize popover', win._qat_customize_popover is not None)
            if win._qat_customize_popover:
                win._qat_customize_popover.popdown()
                win._qat_customize_popover.unparent()

            # Settings persist to the XDG config directory.
            win._set_theme_mode('dark')
            win._toggle_qat_pin('brush', True)
            path = win._settings_path()
            data = json.loads(path.read_text())
            check('theme preference persisted', data.get('theme_mode') == 'dark', str(data))
            check('QAT English labels available', win.qat_registry['save']['en'] == 'Save')
            check('QAT persisted', 'brush' in data.get('qat', []), str(data.get('qat')))
            win._set_theme_mode('auto')
            win._toggle_qat_pin('brush', False)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            check('feature test exception', False, repr(exc))
        print('RESULTS', sum(1 for _, ok, *_ in results if ok), '/', len(results))
        loop.quit()
        return False

    GLib.timeout_add(500, run)
    GLib.timeout_add(8000, loop.quit)
    loop.run()
    return 0 if all(ok for _, ok, *_ in results) else 1


if __name__ == '__main__':
    sys.exit(main())
