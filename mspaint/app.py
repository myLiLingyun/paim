# SPDX-License-Identifier: GPL-3.0-or-later
"""Main GTK4 application window for the Paint clone."""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

import cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gdk, Gio, GLib, Gtk, Pango, PangoCairo

from . import __version__
from .dialogs import (AboutDialog, AttributesDialog, ColorDialog, MessageDialog,
                      PageSetupDialog, ResizeDialog, SaveOptionsDialog)
from .document import Document, Selection, hex_to_rgb, rgba_to_hex, surface_to_png_bytes
from . import icons as icon_module
from .icons import PaintIcon, image as paint_image
from .i18n import language_is_zh
from .raster import (BRUSH_LABELS, BRUSH_ORDER, DEFAULT_PALETTE, LINE_WIDTHS,
                     SHAPE_FILL_STYLES, SHAPE_OUTLINE_STYLES)
from .shapes import (GALLERY_ROWS, SHAPE_LABELS_EN, SHAPE_LABELS_ZH,
                     SHAPE_ORDER, build_shape_path)
from .text import text_extents
from .view import PaintCanvas


APP_ID = 'io.github.paim.PaintImproved'
APP_NAME_ZH = 'paim'
APP_NAME_EN = 'paim'
APP_DESCRIPTION = 'paintImproved'


CSS = b"""
window { background: #f0f0f0; }
headerbar.paint-header { min-height: 34px; background: #f7f7f7; border-bottom: 1px solid #c8c8c8; padding: 1px 4px; }
headerbar.paint-header windowcontrols button { min-height: 22px; min-width: 30px; }
box.title-quick { background: transparent; }
button.quick { min-width: 24px; min-height: 24px; padding: 2px; margin: 0; background: transparent; border: 1px solid transparent; border-radius: 3px; }
button.quick:hover { background: #e3f0fb; border-color: #9dc4e8; }
menubutton.quick > button { min-width: 24px; min-height: 24px; padding: 2px; margin: 0; background: transparent; border: 1px solid transparent; border-radius: 3px; }
menubutton.quick > button:hover { background: #e3f0fb; border-color: #9dc4e8; }
.tabbar { background: #f4f4f4; border-bottom: 1px solid #b9b9b9; padding: 0 5px; }
button.ribbon-tab { min-height: 25px; padding: 3px 16px; margin: 0 1px; border: 1px solid transparent; border-radius: 3px 3px 0 0; background: transparent; font-size: 13px; }
button.ribbon-tab:hover { background: #e7f1fa; border-color: #b8d3ea; }
button.ribbon-tab.active-tab { background: #ffffff; border-color: #b9b9b9; border-bottom-color: #ffffff; }
button.file-tab { background: #1f6fb2; color: #ffffff; border-radius: 3px; padding: 3px 16px; min-height: 25px; }
button.file-tab:hover { background: #2b83c9; }
menubutton.file-tab > button { background: #1f6fb2; color: #ffffff; border: none; border-radius: 3px; padding: 3px 16px; min-height: 25px; }
menubutton.file-tab > button:hover { background: #2b83c9; }
menubutton.file-tab > button label { color: #ffffff; }
.backstage-left { background: #f7f7f7; border-right: 1px solid #cccccc; padding: 4px; }
button.backstage-item { border: none; background: transparent; padding: 7px 8px; border-radius: 3px; }
button.backstage-item:hover { background: #e6f1fb; }
button.recent-item { border: none; background: transparent; padding: 5px 8px; border-radius: 3px; }
button.recent-item:hover { background: #e6f1fb; }
.ribbon { background: #fafafa; border-bottom: 1px solid #bfbfbf; padding: 3px 4px 1px 4px; min-height: 100px; }
.ribbon-group { border-right: 1px solid #d7d7d7; padding: 1px 6px 0 6px; }
.ribbon-group-label { font-size: 10px; color: #444444; margin-top: 2px; }
.ribbon-big { min-width: 56px; min-height: 61px; padding: 2px 3px; border: 1px solid transparent; border-radius: 3px; background: transparent; }
.ribbon-big:hover { background: #e6f1fb; border-color: #a9c9e7; }
.ribbon-big:checked { background: #d5e9f8; border-color: #82b1dd; }
.ribbon-small { min-width: 25px; min-height: 24px; padding: 1px; border: 1px solid transparent; border-radius: 3px; background: transparent; }
.ribbon-small:hover { background: #e6f1fb; border-color: #a9c9e7; }
.ribbon-small:checked { background: #d5e9f8; border-color: #82b1dd; }
.ribbon-label { font-size: 10px; color: #1d1d1d; }
.ribbon-small-label { font-size: 11px; color: #1d1d1d; }
.group-title { font-weight: bold; font-size: 11px; color: #333333; }
.section-title { font-weight: bold; font-size: 12px; color: #222222; }
.hint { color: #666666; font-size: 11px; }
.palette-swatch { border-radius: 0; min-width: 17px; min-height: 17px; padding: 0; border: 1px solid #8a8a8a; }
.palette-swatch:hover { border: 1px solid #1a5fa0; }
.color-chip { border: 1px solid #555555; border-radius: 1px; min-width: 28px; min-height: 28px; padding: 0; }
.shapes-grid button { min-width: 24px; min-height: 22px; padding: 0; border: 1px solid transparent; border-radius: 2px; }
.shapes-grid button:hover { background: #e6f1fb; border-color: #a9c9e7; }
.shapes-grid button.active-shape { background: #d5e9f8; border-color: #7aacdb; }
.canvas-area { background: #a6b8cc; }
.statusbar { background: #f5f5f5; border-top: 1px solid #c4c4c4; padding: 1px 6px; min-height: 25px; }
.status-label { font-size: 11px; color: #333333; padding: 0 7px; }
.canvas-shadow { background: #a6b8cc; }
.zoom-scale trough { min-height: 4px; }
.textbar { background: #fbfbfb; border-bottom: 1px solid #c8c8c8; padding: 3px 8px; }
.toolbar-label { font-size: 11px; color: #444444; }
.ruler { background: #efefef; color: #555555; }
.ruler-h { border-bottom: 1px solid #b0b0b0; }
.ruler-v { border-right: 1px solid #b0b0b0; }
.checker { background: #ffffff; }
menubutton.flat > button { border: none; background: transparent; padding: 2px; min-width: 20px; min-height: 20px; }
menubutton.flat > button:hover { background: #e6f1fb; }
.tooltip { font-size: 11px; }
.drop-hint { background: rgba(10, 14, 20, 0.72); border: 3px dashed #62a9ef; border-radius: 10px; margin: 18px; }
.drop-hint label { font-size: 24px; font-weight: 700; color: #ffffff; }
.drop-hint image { color: #ffffff; }
"""


DARK_CSS = b"""
window { background: #1f2023; color: #e9e9ec; }
headerbar.paint-header { background: #292a2e; border-bottom-color: #3b3c41; color: #e9e9ec; }
headerbar.paint-header .title, headerbar.paint-header label { color: #f3f3f5; }
.tabbar { background: #25262a; border-bottom-color: #3a3b40; }
button.ribbon-tab { color: #e4e4e7; }
button.ribbon-tab:hover { background: #343a44; border-color: #4d5b69; }
button.ribbon-tab.active-tab { background: #303136; border-color: #4c4d52; border-bottom-color: #303136; color: #ffffff; }
menubutton.file-tab > button { background: #2b6fa9; color: #ffffff; }
menubutton.file-tab > button:hover { background: #357fbe; }
menubutton.quick > button { background: transparent; border-color: transparent; }
menubutton.quick > button:hover { background: #37414c; border-color: #526271; }
.ribbon { background: #292a2d; border-bottom-color: #3a3b3f; }
.ribbon-group { border-right-color: #3b3c40; }
.ribbon-group-label, .ribbon-label, .ribbon-small-label { color: #d9d9dc; }
.ribbon-big, .ribbon-small { color: #e9e9ec; }
.ribbon-big:hover, .ribbon-small:hover { background: #37414c; border-color: #526271; }
.ribbon-big:checked, .ribbon-small:checked { background: #31465c; border-color: #5b86b2; }
.shapes-grid button:hover { background: #37414c; border-color: #526271; }
.shapes-grid button.active-shape { background: #31465c; border-color: #5b86b2; }
.group-title, .section-title { color: #f0f0f2; }
.hint { color: #a1a3a9; }
.palette-swatch { border-color: #6d6e72; }
.canvas-area, .canvas-area viewport, .canvas-area > * { background-color: #181b20; }
.statusbar { background: #27282b; border-top-color: #3a3b3f; color: #e9e9ec; }
.status-label, .toolbar-label { color: #d2d3d6; }
.textbar { background: #292a2d; border-bottom-color: #3a3b3f; color: #e9e9ec; }
.ruler { background: #292a2d; color: #cfcfd2; }
.ruler-h { border-bottom-color: #47484c; }
.ruler-v { border-right-color: #47484c; }
.backstage { background: #292a2d; color: #e9e9ec; }
.backstage-left { background: #242528; border-right-color: #3d3e42; }
button.backstage-item { color: #e9e9ec; }
button.backstage-item:hover, button.recent-item:hover { background: #37414c; }
button.recent-item { color: #e9e9ec; }
popover.background { background-color: transparent; box-shadow: none; }
popover.background > contents { background-color: #292a2d; color: #e9e9ec; }
popover > arrow { background-color: #292a2d; }
popover button { color: #e9e9ec; }
popover button:hover { background: #37414c; }
entry, spinbutton, dropdown, combobox { background-color: #202124; color: #e9e9ec; border-color: #47484c; }
checkbutton, radiobutton, label { color: #e9e9ec; }
separator { background-color: #47484a; }
scale trough { background-color: #47484a; }
tooltip { background-color: #3a3b3f; color: #f4f4f6; }
window.dialog { background: #242528; }
headerbar, .titlebar { background-color: #292a2e; background-image: none; color: #e9e9ec; border-bottom: 1px solid #3b3c41; box-shadow: none; }
headerbar .title, headerbar label, .titlebar label { color: #f3f3f5; }
headerbar button, .titlebar button { color: #e9e9ec; }
headerbar button:hover, .titlebar button:hover { background-color: #37414c; }
"""

_CSS_PROVIDER = None


def _interface_settings():
    try:
        return Gio.Settings.new('org.gnome.desktop.interface')
    except Exception:
        return None


def _system_color_scheme():
    """Return 'prefer-dark', 'prefer-light', 'default', or None.

    GNOME's appearance toggle is written to color-scheme.  The legacy
    ``gtk-theme`` setting can keep pointing at a *-dark theme after the user
    switches to the light appearance, so color-scheme must win when present.
    """
    gs = _interface_settings()
    if gs is None:
        return None
    try:
        return gs.get_string('color-scheme')
    except Exception:
        return None


def detect_dark_theme():
    env = os.environ.get('GTK_THEME', '').lower()
    if env:
        # An explicit GTK_THEME is an intentional per-process override.
        return 'dark' in env
    scheme = _system_color_scheme()
    if scheme in ('prefer-dark', 'prefer-light', 'default'):
        return scheme == 'prefer-dark'
    settings = Gtk.Settings.get_default()
    if settings is not None:
        try:
            if settings.get_property('gtk-application-prefer-dark-theme'):
                return True
        except Exception:
            pass
        try:
            name = (settings.get_property('gtk-theme-name') or '').lower()
            if 'dark' in name:
                return True
        except Exception:
            pass
    return False


def _theme_available(name):
    if not name:
        return False
    if name in ('Adwaita', 'Adwaita-dark', 'HighContrast'):
        return True
    for root in (os.path.expanduser('~/.themes'),
                 os.path.expanduser('~/.local/share/themes'),
                 '/usr/share/themes', '/usr/local/share/themes'):
        if os.path.isdir(os.path.join(root, name)):
            return True
    return False


def apply_native_theme(dark):
    """Keep native GTK widgets (dialogs, popovers, choosers) in the same mode.

    A user may have a dark legacy GTK theme while GNOME's appearance setting
    is light.  In that case switch this process to the matching light variant
    so dialogs and menus do not stay dark while paim's own UI turns light.
    """
    settings = Gtk.Settings.get_default()
    if settings is None:
        return
    try:
        current = settings.get_property('gtk-theme-name') or ''
    except Exception:
        current = ''
    base = re.sub(r'[-_]dark$', '', current, flags=re.IGNORECASE)
    if dark:
        candidates = [current if 'dark' in current.lower() else '',
                      base + '-dark', 'Adwaita-dark', 'Adwaita']
    else:
        candidates = [base, 'Adwaita']
    target = None
    for candidate in candidates:
        if candidate and _theme_available(candidate):
            target = candidate
            break
    try:
        if target and target != current:
            settings.set_property('gtk-theme-name', target)
        try:
            scheme = (Gtk.InterfaceColorScheme.DARK if dark
                      else Gtk.InterfaceColorScheme.LIGHT)
            settings.set_property('gtk-interface-color-scheme', scheme)
        except Exception:
            # Older GTK releases only have the deprecated boolean property.
            settings.set_property('gtk-application-prefer-dark-theme', bool(dark))
    except Exception:
        pass


def install_css(dark=None):
    global _CSS_PROVIDER
    if dark is None:
        dark = detect_dark_theme()
    display = Gdk.Display.get_default()
    if display is None:
        return
    if _CSS_PROVIDER is not None:
        try:
            Gtk.StyleContext.remove_provider_for_display(display, _CSS_PROVIDER)
        except Exception:
            pass
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS + (DARK_CSS if dark else b''))
    Gtk.StyleContext.add_provider_for_display(display, provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _CSS_PROVIDER = provider



class PaintApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.window = None

    def do_activate(self):
        if self.window is None:
            self.window = PaintWindow(self)
        self.window.present()
        self.window.show_all_initial()

    def do_open(self, files, n_files, hint):
        self.do_activate()
        if n_files and files:
            self.window.load_path(files[0].get_path())


class PaintWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.app = app
        self.lang_zh = language_is_zh()
        self._load_preferences()
        self.qat_registry = {}
        self.qat_buttons = {}
        self._init_qat_registry()
        self.dark_mode = self._resolve_dark()
        self._applying_theme = False
        self._updating_theme_menu = False
        apply_native_theme(self.dark_mode)
        icon_module.set_dark_theme(self.dark_mode)
        install_css(self.dark_mode)
        self.set_default_size(1500, 900)
        self.doc = Document(768, 432)
        self.recent_files = []
        self.zoom = 1.0
        self.status_visible = True
        self.thumbnail_visible = False
        self._is_fullscreen = False
        self.page_settings = {'landscape': False, 'scale': 100, 'left': 0.5,
                              'top': 0.5, 'center': True}
        self._save_after = None
        self._quick_clipboard = None
        self._force_close = False
        self._load_recent()
        self._build_ui()
        self._build_actions()
        self._update_title()
        self._update_action_sensitivity()
        self.canvas.dark = self.dark_mode
        self.add_css_class('paint-dark' if self.dark_mode else 'paint-light')
        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.connect('notify::gtk-theme-name', self._on_system_theme_changed)
            settings.connect('notify::gtk-application-prefer-dark-theme', self._on_system_theme_changed)
        interface = _interface_settings()
        if interface is not None:
            interface.connect('changed::color-scheme', self._on_system_theme_changed)
            interface.connect('changed::gtk-theme', self._on_system_theme_changed)
            self._interface_settings = interface
        self.connect('close-request', self._on_close_request)

    # ------------------------------------------------------------------
    # Preferences
    def _settings_path(self):
        return Path(GLib.get_user_config_dir()) / 'paim' / 'settings.json'

    def _load_preferences(self):
        self.theme_mode = 'auto'
        self.qat_pinned = ['save', 'undo', 'redo']
        try:
            path = self._settings_path()
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                mode = data.get('theme_mode', 'auto')
                if mode in ('auto', 'light', 'dark'):
                    self.theme_mode = mode
                qat = data.get('qat')
                if isinstance(qat, list):
                    self.qat_pinned = [str(x) for x in qat if isinstance(x, str)]
        except Exception:
            pass
        # Remove duplicates but keep ordering.
        seen = set()
        self.qat_pinned = [x for x in self.qat_pinned if not (x in seen or seen.add(x))]

    def _save_preferences(self):
        try:
            path = self._settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps({
                'theme_mode': self.theme_mode,
                'qat': self.qat_pinned,
            }, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(tmp, path)
        except Exception:
            pass

    def _resolve_dark(self):
        if self.theme_mode == 'dark':
            return True
        if self.theme_mode == 'light':
            return False
        return detect_dark_theme()

    # ------------------------------------------------------------------
    # Translation helper
    def tr(self, zh, en):
        return zh if self.lang_zh else en

    # ------------------------------------------------------------------
    # UI construction
    def _build_ui(self):
        self.canvas = PaintCanvas(self.doc)
        self.header = Gtk.HeaderBar()
        self.header.add_css_class('paint-header')
        self.header.set_show_title_buttons(True)
        self.header.set_decoration_layout('menu:minimize,maximize,close')
        self.title_label = Gtk.Label(label=self.tr('无标题 - paim', 'Untitled - paim'))
        self.title_label.add_css_class('title')
        self.header.set_title_widget(self.title_label)

        self.quick_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        self.quick_box.add_css_class('title-quick')
        self.qat_items_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        self.quick_box.append(self.qat_items_box)
        self.btn_customize = self._quick_button(
            'dropdown',
            self.tr('自定义快速访问工具栏', 'Customize Quick Access Toolbar'),
            self._quick_customize)
        self.quick_box.append(self.btn_customize)
        self.header.pack_start(self.quick_box)
        self.set_titlebar(self.header)
        self._rebuild_qat()

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # tab bar + ribbon
        tabbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tabbar.add_css_class('tabbar')
        self.file_tab = Gtk.MenuButton()
        self.file_tab.set_always_show_arrow(False)
        self.file_tab.add_css_class('file-tab')
        self.file_tab.set_child(Gtk.Label(label=self.tr('文件', 'File')))
        self.file_tab.set_tooltip_text(self.tr('文件', 'File'))
        self.home_tab = Gtk.ToggleButton(label=self.tr('主页', 'Home'))
        self.home_tab.add_css_class('ribbon-tab')
        self.view_tab = Gtk.ToggleButton(label=self.tr('查看', 'View'))
        self.view_tab.add_css_class('ribbon-tab')
        self.home_tab.set_active(True)
        self.view_tab.set_group(self.home_tab)
        self.home_tab.connect('toggled', self._switch_ribbon, 'home')
        self.view_tab.connect('toggled', self._switch_ribbon, 'view')
        self.home_tab.add_css_class('active-tab')
        tabbar.append(self.file_tab)
        tabbar.append(self.home_tab)
        tabbar.append(self.view_tab)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        tabbar.append(spacer)
        helpbtn = Gtk.Button(label='?')
        helpbtn.add_css_class('ribbon-tab')
        helpbtn.set_tooltip_text(self.tr('paim 帮助 (F1)', 'paim help (F1)'))
        helpbtn.connect('clicked', lambda *a: self._help())
        tabbar.append(helpbtn)
        root.append(tabbar)

        self.ribbon_stack = Gtk.Stack()
        self.ribbon_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.home_ribbon = self._build_home_ribbon()
        self.view_ribbon = self._build_view_ribbon()
        self.ribbon_stack.add_named(self.home_ribbon, 'home')
        self.ribbon_stack.add_named(self.view_ribbon, 'view')
        root.append(self.ribbon_stack)

        self.textbar = self._build_text_bar()
        self.textbar_revealer = Gtk.Revealer()
        self.textbar_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.textbar_revealer.set_child(self.textbar)
        self.textbar_revealer.set_reveal_child(False)
        root.append(self.textbar_revealer)

        # central canvas with rulers / thumbnail
        self.canvas.on_status = self._on_canvas_status
        self.canvas.on_zoom_changed = self._on_canvas_zoom
        self.canvas.on_selection_changed = lambda sel: self._update_action_sensitivity()
        self.canvas.on_modified = self._on_canvas_modified
        self.canvas.on_pointer = self._on_canvas_pointer
        self.canvas.on_color_picked = self._on_colors_changed
        self.canvas.drawing.set_draw_func(self.canvas._draw)

        center = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        center.set_vexpand(True)

        grid = Gtk.Grid()
        grid.set_vexpand(True); grid.set_hexpand(True)
        self.ruler_corner = Gtk.DrawingArea()
        self.ruler_corner.set_content_width(16); self.ruler_corner.set_content_height(16)
        self.hruler = RulerWidget(self.canvas, Gtk.Orientation.HORIZONTAL)
        self.vruler = RulerWidget(self.canvas, Gtk.Orientation.VERTICAL)
        self.hruler.set_content_height(18)
        self.vruler.set_content_width(18)
        self.hruler.set_hexpand(True)
        self.vruler.set_vexpand(True)
        self.ruler_grid = grid
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_hexpand(True); self.scrolled.set_vexpand(True)
        self.scrolled.set_child(self.canvas)
        self.scrolled.add_css_class('canvas-area')
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_overlay_scrolling(False)
        if self.scrolled.get_hadjustment():
            self.scrolled.get_hadjustment().connect('value-changed', lambda *a: self.hruler.queue_draw())
            self.scrolled.get_vadjustment().connect('value-changed', lambda *a: self.vruler.queue_draw())
        grid.attach(self.ruler_corner, 0, 0, 1, 1)
        grid.attach(self.hruler, 1, 0, 1, 1)
        grid.attach(self.vruler, 0, 1, 1, 1)
        grid.attach(self.scrolled, 1, 1, 1, 1)
        self._set_rulers_visible(False)
        center.append(grid)
        grid.set_hexpand(True)

        self.thumb_revealer = Gtk.Revealer()
        self.thumb_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        thumb_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        thumb_box.set_margin_top(8); thumb_box.set_margin_bottom(8)
        thumb_box.set_margin_start(6); thumb_box.set_margin_end(6)
        thumb_box.set_size_request(170, -1)
        thumb_label = Gtk.Label(label=self.tr('缩略图', 'Thumbnail'))
        thumb_label.add_css_class('group-title')
        thumb_box.append(thumb_label)
        self.thumb_area = Gtk.DrawingArea()
        self.thumb_area.set_content_width(158)
        self.thumb_area.set_content_height(120)
        self.thumb_area.set_draw_func(self._draw_thumbnail)
        thumb_box.append(self.thumb_area)
        self.thumb_revealer.set_child(thumb_box)
        center.append(self.thumb_revealer)
        root.append(center)

        # status
        self.statusbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.statusbar.add_css_class('statusbar')
        self.pos_label = Gtk.Label(label='')
        self.pos_label.add_css_class('status-label')
        self.sel_label = Gtk.Label(label='')
        self.sel_label.add_css_class('status-label')
        self.size_label = Gtk.Label(label='')
        self.size_label.add_css_class('status-label')
        self.size_label.set_hexpand(True)
        self.size_label.set_xalign(0)
        self.statusbar.append(self.pos_label)
        self.statusbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.statusbar.append(self.sel_label)
        self.statusbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.statusbar.append(self.size_label)
        zoom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        zoom_box.set_margin_end(8)
        self.zoom_label = Gtk.Label(label='100%')
        self.zoom_label.add_css_class('status-label')
        zoom_out = Gtk.Button()
        zoom_out.set_child(PaintIcon('minus', 13))
        zoom_out.add_css_class('quick')
        zoom_out.connect('clicked', lambda *a: self.canvas.zoom_out())
        zoom_in = Gtk.Button()
        zoom_in.set_child(PaintIcon('plus', 13))
        zoom_in.add_css_class('quick')
        zoom_in.connect('clicked', lambda *a: self.canvas.zoom_in())
        self.zoom_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.1, 8.0, 0.1)
        self.zoom_scale.set_size_request(130, -1)
        self.zoom_scale.set_draw_value(False)
        self.zoom_scale.set_value(1.0)
        self.zoom_scale.connect('value-changed', self._on_zoom_scale)
        zoom_box.append(self.zoom_label)
        zoom_box.append(zoom_out)
        zoom_box.append(self.zoom_scale)
        zoom_box.append(zoom_in)
        self.statusbar.append(zoom_box)
        root.append(self.statusbar)

        self.overlay = Gtk.Overlay()
        self.overlay.set_child(root)
        self.set_child(self.overlay)
        self._build_drop_hint()
        self._setup_file_drop()
        self._build_backstage()
        keyctl = Gtk.EventControllerKey()
        keyctl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keyctl.connect('key-pressed', self._on_window_key)
        self.add_controller(keyctl)
        self.connect('notify::fullscreened', self._on_fullscreen_changed)
        self._sync_zoom_controls()
        self._sync_palette()
        self._update_quick_access()

    def show_all_initial(self):
        self.canvas.grab_focus()
        self._update_status_labels()

    def _quick_button(self, icon, tooltip, callback):
        b = Gtk.Button()
        b.add_css_class('quick')
        b.set_child(PaintIcon(icon, 18))
        b.set_tooltip_text(tooltip)
        b.connect('clicked', lambda *a: callback())
        return b

    # ------------------------------------------------------------------
    # Quick Access Toolbar
    def _init_qat_registry(self):
        def reg(key, zh, en, icon, callback, menu=None):
            self.qat_registry[key] = {'zh': zh, 'en': en, 'icon': icon,
                                      'callback': callback, 'menu': menu}
        reg('save', '保存', 'Save', 'save', self._save_clicked)
        reg('undo', '撤消', 'Undo', 'undo', self._undo)
        reg('redo', '重做', 'Redo', 'redo', self._redo)
        reg('new', '新建', 'New', 'new', self._new_clicked)
        reg('open', '打开', 'Open', 'open', self._open_clicked)
        reg('print', '打印', 'Print', 'print', lambda: self._print())
        reg('cut', '剪切', 'Cut', 'cut', self._cut_clicked)
        reg('copy', '复制', 'Copy', 'copy', self._copy_clicked)
        reg('paste', '粘贴', 'Paste', 'paste', self._paste_clicked)
        reg('select', '选择', 'Select', 'select_rect', lambda: self._qat_tool('select'))
        reg('crop', '裁剪', 'Crop', 'crop', self._crop)
        reg('resize', '调整大小', 'Resize', 'resize', self._resize_dialog)
        reg('invert', '反色', 'Invert colors', 'edit_colors', self._invert_colors)
        reg('pencil', '铅笔', 'Pencil', 'pencil', lambda: self._qat_tool('pencil'))
        reg('fill', '用颜色填充', 'Fill with color', 'fill', lambda: self._qat_tool('fill'))
        reg('text', '文本', 'Text', 'text', lambda: self._qat_tool('text'))
        reg('eraser', '橡皮擦', 'Eraser', 'eraser', lambda: self._qat_tool('eraser'))
        reg('picker', '颜色选取器', 'Color picker', 'picker', lambda: self._qat_tool('picker'))
        reg('magnifier', '放大镜', 'Magnifier', 'magnifier', lambda: self._qat_tool('magnifier'))
        reg('brush', '刷子', 'Brushes', 'brush', lambda: self._qat_tool('brush'))
        reg('zoom-in', '放大', 'Zoom in', 'zoomin', lambda: self.canvas.zoom_in())
        reg('zoom-out', '缩小', 'Zoom out', 'zoomout', lambda: self.canvas.zoom_out())
        reg('zoom-100', '100%', '100%', 'magnifier', lambda: self.canvas.set_zoom(1.0))
        reg('fullscreen', '全屏', 'Full screen', 'fullscreen', self._toggle_fullscreen)
        reg('rotate', '旋转', 'Rotate', 'rotate', None, menu='rotate')
        reg('shapes', '形状', 'Shapes', 'shapes', None, menu='shapes')
        reg('outline', '轮廓', 'Outline', 'outline', None, menu='outline')
        reg('fill-style', '填充', 'Fill', 'fill_style', None, menu='fill')
        reg('size', '粗细', 'Size', 'outline', None, menu='size')
        reg('colors', '颜色', 'Colors', 'edit_colors', None, menu='colors')
        reg('ruler', '标尺', 'Rulers', 'ruler',
            lambda: self.cb_ruler.set_active(not self.cb_ruler.get_active()))
        reg('grid', '网格线', 'Gridlines', 'grid',
            lambda: self.cb_grid.set_active(not self.cb_grid.get_active()))
        reg('statusbar', '状态栏', 'Status bar', 'statusbar',
            lambda: self.cb_status.set_active(not self.cb_status.get_active()))
        reg('thumbnail', '缩略图', 'Thumbnail', 'thumbnail', self._toggle_thumbnail)
        reg('theme', '主题', 'Theme', 'theme', None, menu='theme')

    def _noop(self):
        pass

    def _qat_tool(self, tool):
        self._commit_current_text()
        self.canvas.set_tool(tool)
        self._set_tool_button_state(tool)
        if hasattr(self, 'textbar_revealer'):
            self.textbar_revealer.set_reveal_child(tool == 'text')

    def _qat_label(self, spec):
        return spec['zh'] if self.lang_zh else spec['en']

    def _rebuild_qat(self):
        if not hasattr(self, 'qat_items_box'):
            return
        while self.qat_items_box.get_first_child():
            self.qat_items_box.remove(self.qat_items_box.get_first_child())
        self.qat_buttons = {}
        for key in list(self.qat_pinned):
            spec = self.qat_registry.get(key)
            if spec is None:
                continue
            if spec.get('menu'):
                btn = Gtk.MenuButton()
                btn.add_css_class('quick')
                btn.set_always_show_arrow(False)
                btn.set_child(PaintIcon(spec['icon'], 18))
                btn.set_tooltip_text(self._qat_label(spec))
                btn.set_popover(self._build_qat_menu(spec['menu']))
            else:
                btn = self._quick_button(spec['icon'], self._qat_label(spec), spec['callback'])
                btn.set_tooltip_text(self._qat_label(spec))
            self._attach_qat(btn, key)
            self.qat_items_box.append(btn)
            self.qat_buttons[key] = btn
        self._update_quick_access()

    def _build_qat_menu(self, kind):
        pop = Gtk.Popover()
        pop.set_has_arrow(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.set_margin_top(6); box.set_margin_bottom(6)
        box.set_margin_start(8); box.set_margin_end(8)

        def close_and(fn):
            pop.popdown()
            fn()

        if kind == 'shapes':
            grid = Gtk.Grid(column_spacing=2, row_spacing=2)
            for i, shape in enumerate(SHAPE_ORDER):
                b = Gtk.Button()
                b.add_css_class('shape-button')
                label = SHAPE_LABELS_ZH.get(shape, shape) if self.lang_zh else SHAPE_LABELS_EN.get(shape, shape)
                b.set_tooltip_text(label)
                b.set_child(ShapeIcon(shape, 24))
                b.connect('clicked', lambda x, s=shape: close_and(lambda: self._choose_shape(s)))
                grid.attach(b, i % 5, i // 5, 1, 1)
            box.append(grid)
        elif kind == 'rotate':
            options = [
                (self.tr('向右旋转 90 度', 'Rotate right 90°'), 'right'),
                (self.tr('向左旋转 90 度', 'Rotate left 90°'), 'left'),
                (self.tr('旋转 180 度', 'Rotate 180°'), '180'),
                (self.tr('垂直翻转', 'Flip vertical'), 'flip_v'),
                (self.tr('水平翻转', 'Flip horizontal'), 'flip_h'),
            ]
            for text, mode in options:
                b = Gtk.Button(label=text)
                b.set_halign(Gtk.Align.FILL)
                b.connect('clicked', lambda x, m=mode: close_and(lambda: self._rotate(m)))
                box.append(b)
        elif kind in ('outline', 'fill'):
            styles = SHAPE_OUTLINE_STYLES if kind == 'outline' else SHAPE_FILL_STYLES
            for key, (zh, en) in styles.items():
                b = Gtk.Button(label=zh if self.lang_zh else en)
                b.set_halign(Gtk.Align.FILL)
                b.connect('clicked', lambda x, k=key, kd=kind: close_and(lambda: self._set_style(kd, k)))
                box.append(b)
        elif kind == 'size':
            grid = Gtk.Grid(column_spacing=3, row_spacing=3)
            for i, width in enumerate(LINE_WIDTHS):
                b = Gtk.Button(label=f'{width} px')
                b.set_halign(Gtk.Align.FILL)
                b.connect('clicked', lambda x, w=width: close_and(lambda: self._set_line_width(w)))
                grid.attach(b, i % 3, i // 3, 1, 1)
            box.append(grid)
        elif kind == 'colors':
            from .document import hex_to_rgb
            head = Gtk.Grid(column_spacing=2, row_spacing=2)
            for i, color in enumerate(DEFAULT_PALETTE[:20]):
                b = Gtk.Button()
                b.add_css_class('palette-swatch')
                b.set_size_request(20, 20)
                p = Gtk.CssProvider()
                p.load_from_data(f'button {{ background: {color}; min-width: 18px; min-height: 18px; }}'.encode())
                b.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                b.set_tooltip_text(color)
                b.connect('clicked', lambda x, c=color: close_and(lambda: self._palette_left(c)))
                head.attach(b, i % 10, i // 10, 1, 1)
            box.append(head)
            edit = Gtk.Button(label=self.tr('编辑颜色...', 'Edit colors...'))
            edit.connect('clicked', lambda x: close_and(lambda: self._edit_color(1)))
            box.append(edit)
        elif kind == 'theme':
            group = None
            for mode, text in (('auto', self.tr('跟随系统', 'Follow system')),
                               ('light', self.tr('浅色', 'Light')),
                               ('dark', self.tr('深色', 'Dark'))):
                cb = Gtk.CheckButton(label=text)
                if group is not None:
                    cb.set_group(group)
                else:
                    group = cb
                cb.set_active(mode == self.theme_mode)
                cb.connect('toggled', lambda b, m=mode: close_and(lambda: self._set_theme_mode(m)) if b.get_active() else None)
                box.append(cb)
        pop.set_child(box)
        return pop

    def _attach_qat(self, widget, key):
        if key not in self.qat_registry:
            return
        gesture = Gtk.GestureClick()
        gesture.set_button(3)
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        gesture.connect('pressed', lambda g, n, x, y, w=widget, k=key:
                        self._show_qat_context(w, k))
        widget.add_controller(gesture)

    def _show_qat_context(self, widget, key):
        spec = self.qat_registry.get(key)
        if spec is None:
            return
        if getattr(self, '_qat_context_popover', None) is not None:
            try:
                self._qat_context_popover.popdown()
                self._qat_context_popover.unparent()
            except Exception:
                pass
        pop = Gtk.Popover()
        pop.set_has_arrow(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(6); box.set_margin_bottom(6)
        box.set_margin_start(8); box.set_margin_end(8)
        title = Gtk.Label(label=self._qat_label(spec))
        title.set_xalign(0)
        title.add_css_class('group-title')
        box.append(title)
        pinned = key in self.qat_pinned
        action = Gtk.Button(label=self.tr('从快速访问工具栏删除', 'Remove from Quick Access Toolbar')
                            if pinned else
                            self.tr('添加到快速访问工具栏', 'Add to Quick Access Toolbar'))
        def do_toggle():
            pop.popdown()
            pop.unparent()
            if pinned:
                GLib.idle_add(self._toggle_qat_pin, key, False)
            else:
                self._toggle_qat_pin(key, True)
        action.connect('clicked', lambda *a: do_toggle())
        box.append(action)
        pop.set_child(box)
        pop.set_parent(widget)
        self._qat_context_popover = pop
        pop.popup()

    def _toggle_qat_pin(self, key, pin):
        if pin:
            if key not in self.qat_pinned:
                self.qat_pinned.append(key)
        else:
            if key in self.qat_pinned:
                self.qat_pinned.remove(key)
        self._save_preferences()
        self._rebuild_qat()
        return False

    def _quick_customize(self):
        if getattr(self, '_qat_customize_popover', None) is not None:
            try:
                self._qat_customize_popover.popdown()
                self._qat_customize_popover.unparent()
            except Exception:
                pass
            self._qat_customize_popover = None
        pop = Gtk.Popover()
        pop.set_has_arrow(True)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.set_margin_top(8); outer.set_margin_bottom(8)
        outer.set_margin_start(10); outer.set_margin_end(10)
        title = Gtk.Label(label=self.tr('快速访问工具栏', 'Quick Access Toolbar'))
        title.set_xalign(0)
        title.add_css_class('section-title')
        outer.append(title)
        hint = Gtk.Label(label=self.tr('勾选要显示在标题栏的命令；也可以右键功能区命令直接添加。',
                                       'Check commands to show in the title bar, or right-click a ribbon command.'))
        hint.set_xalign(0); hint.set_wrap(True); hint.add_css_class('hint')
        hint.set_max_width_chars(40)
        outer.append(hint)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        for key, spec in self.qat_registry.items():
            cb = Gtk.CheckButton(label=self._qat_label(spec))
            cb.set_active(key in self.qat_pinned)
            cb.connect('toggled', lambda b, k=key: self._toggle_qat_pin(k, b.get_active()))
            inner.append(cb)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_size_request(300, 380)
        scroller.set_child(inner)
        outer.append(scroller)
        pop.set_child(outer)
        pop.set_parent(self.btn_customize)
        self._qat_customize_popover = pop
        pop.popup()

    def _ribbon_group(self, title, child, *, min_width=None):
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        group.add_css_class('ribbon-group')
        group.append(child)
        lab = Gtk.Label(label=title)
        lab.add_css_class('ribbon-group-label')
        group.append(lab)
        if min_width:
            group.set_size_request(min_width, -1)
        return group

    def _big_button(self, icon_name, label_text, tooltip, callback, *, toggle=False):
        cls = Gtk.ToggleButton if toggle else Gtk.Button
        b = cls()
        b.add_css_class('ribbon-big')
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        box.set_halign(Gtk.Align.CENTER)
        box.append(PaintIcon(icon_name, 30))
        if label_text:
            lab = Gtk.Label(label=label_text)
            lab.add_css_class('ribbon-label')
            lab.set_justify(Gtk.Justification.CENTER)
            lab.set_wrap(True)
            box.append(lab)
        b.set_child(box)
        b.set_tooltip_text(tooltip)
        b.connect('clicked', lambda *a: callback())
        return b

    def _small_button(self, icon_name, tooltip, callback, *, label_text=None, toggle=False):
        cls = Gtk.ToggleButton if toggle else Gtk.Button
        b = cls()
        b.add_css_class('ribbon-small')
        if label_text:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            box.append(PaintIcon(icon_name, 16))
            lab = Gtk.Label(label=label_text)
            lab.add_css_class('ribbon-small-label')
            box.append(lab)
            b.set_child(box)
        else:
            b.set_child(PaintIcon(icon_name, 18))
        b.set_tooltip_text(tooltip)
        b.connect('clicked', lambda *a: callback())
        return b

    def _stacked_button(self, icon_name, label_text, tooltip, callback):
        b = Gtk.Button()
        b.add_css_class('ribbon-small')
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_halign(Gtk.Align.CENTER)
        box.append(PaintIcon(icon_name, 17))
        lab = Gtk.Label(label=label_text)
        lab.add_css_class('ribbon-label')
        box.append(lab)
        b.set_child(box)
        b.set_tooltip_text(tooltip)
        b.connect('clicked', lambda *a: callback())
        return b

    def _small_tool_toggle(self, icon_name, tooltip, tool):
        b = Gtk.ToggleButton()
        b.add_css_class('ribbon-small')
        b.set_child(PaintIcon(icon_name, 18))
        b.set_tooltip_text(tooltip)
        b.connect('toggled', self._on_tool_toggled, tool)
        self.tool_buttons[tool] = b
        return b

    def _build_home_ribbon(self):
        ribbon = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        ribbon.add_css_class('ribbon')
        self.tool_buttons = {}

        # Clipboard group
        clip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        paste_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.paste_btn = self._big_button('paste', self.tr('粘贴', 'Paste'),
                                          self.tr('粘贴剪贴板的内容。', 'Paste the clipboard contents.'),
                                          self._paste_clicked)
        self._attach_qat(self.paste_btn, 'paste')
        paste_box.append(self.paste_btn)
        self.paste_menu = Gtk.MenuButton()
        self.paste_menu.add_css_class('flat')
        self.paste_menu.set_child(PaintIcon('dropdown', 13))
        pop = Gtk.Popover()
        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        pbox.set_margin_top(4); pbox.set_margin_bottom(4)
        pbox.set_margin_start(4); pbox.set_margin_end(4)
        b1 = Gtk.Button(label=self.tr('粘贴 (Ctrl+V)', 'Paste (Ctrl+V)'))
        b1.connect('clicked', lambda *a: (pop.popdown(), self._paste_clicked()))
        b2 = Gtk.Button(label=self.tr('粘贴来源...', 'Paste from...'))
        b2.connect('clicked', lambda *a: (pop.popdown(), self._paste_from_file()))
        pbox.append(b1); pbox.append(b2)
        pop.set_child(pbox)
        self.paste_menu.set_popover(pop)
        paste_box.append(self.paste_menu)
        clip.append(paste_box)
        cut_btn = self._big_button('cut', self.tr('剪切', 'Cut'),
                                   self.tr('从画布中剪切选定内容。', 'Cut the selection.'),
                                   self._cut_clicked)
        copy_btn = self._big_button('copy', self.tr('复制', 'Copy'),
                                    self.tr('复制选定内容。', 'Copy the selection.'),
                                    self._copy_clicked)
        self._attach_qat(cut_btn, 'cut')
        self._attach_qat(copy_btn, 'copy')
        clip.append(cut_btn)
        clip.append(copy_btn)
        ribbon.append(self._ribbon_group(self.tr('剪贴板', 'Clipboard'), clip))

        # Image group
        image_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        sel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sel_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.sel_button = self._big_button('select_rect', self.tr('选择', 'Select'),
                                           self.tr('选择图片的一部分。', 'Select part of the picture.'),
                                           lambda: self.canvas.set_tool('select'))
        self._attach_qat(self.sel_button, 'select')
        sel_row.append(self.sel_button)
        self.sel_menu = Gtk.MenuButton()
        self.sel_menu.add_css_class('flat')
        self.sel_menu.set_child(PaintIcon('dropdown', 12))
        spop = Gtk.Popover()
        sbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for text, tool in [(self.tr('矩形选择', 'Rectangular selection'), 'select'),
                           (self.tr('自由图形选择', 'Free-form selection'), 'free_select')]:
            bb = Gtk.Button(label=text)
            bb.connect('clicked', lambda b, t=tool, p=spop: (p.popdown(), self.canvas.set_tool(t), self._update_quick_access()))
            sbox.append(bb)
        sbox.append(Gtk.Separator())
        for text, cb in [
            (self.tr('全选 (Ctrl+A)', 'Select all (Ctrl+A)'), self._select_all),
            (self.tr('反向选择', 'Invert selection'), self._invert_selection),
            (self.tr('删除选定内容', 'Delete selection'), self._delete),
            (self.tr('裁剪 (Ctrl+Shift+X)', 'Crop (Ctrl+Shift+X)'), self._crop),
        ]:
            bb = Gtk.Button(label=text)
            bb.connect('clicked', lambda b, c=cb, p=spop: (p.popdown(), c()))
            sbox.append(bb)
        sbox.append(Gtk.Separator())
        trans = Gtk.CheckButton(label=self.tr('透明选择', 'Transparent selection'))
        trans.connect('toggled', lambda b: self._set_opaque_selection(not b.get_active()))
        sbox.append(trans)
        spop.set_child(sbox)
        self.sel_menu.set_popover(spop)
        sel_row.append(self.sel_menu)
        sel_box.append(sel_row)
        image_box.append(sel_box)

        img_grid = Gtk.Grid(column_spacing=2, row_spacing=2)
        crop = self._stacked_button('crop', self.tr('裁剪', 'Crop'),
                                    self.tr('裁剪 (Ctrl+Shift+X)', 'Crop (Ctrl+Shift+X)'), self._crop)
        self._attach_qat(crop, 'crop')
        invert = self._stacked_button('edit_colors', self.tr('反色', 'Invert'),
                                      self.tr('反色 (Ctrl+Shift+I)', 'Invert colors (Ctrl+Shift+I)'), self._invert_colors)
        self._attach_qat(invert, 'invert')
        resize = self._stacked_button('resize', self.tr('调整大小', 'Resize'),
                                      self.tr('调整大小 (Ctrl+W)', 'Resize (Ctrl+W)'), self._resize_dialog)
        self._attach_qat(resize, 'resize')
        rot = Gtk.MenuButton()
        rot.add_css_class('flat')
        rotbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        rotbox.set_halign(Gtk.Align.CENTER)
        rotbox.append(PaintIcon('rotate', 17))
        lab = Gtk.Label(label=self.tr('旋转', 'Rotate'))
        lab.add_css_class('ribbon-label')
        rotbox.append(lab)
        rot.set_child(rotbox)
        rot.set_tooltip_text(self.tr('旋转或翻转', 'Rotate or flip'))
        rpop = Gtk.Popover()
        rbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for text, mode in [(self.tr('向右旋转 90 度', 'Rotate right 90°'), 'right'),
                           (self.tr('向左旋转 90 度', 'Rotate left 90°'), 'left'),
                           (self.tr('旋转 180 度', 'Rotate 180°'), '180'),
                           (self.tr('垂直翻转', 'Flip vertical'), 'flip_v'),
                           (self.tr('水平翻转', 'Flip horizontal'), 'flip_h')]:
            bb = Gtk.Button(label=text)
            bb.connect('clicked', lambda b, m=mode, p=rpop: (p.popdown(), self._rotate(m)))
            rbox.append(bb)
        rpop.set_child(rbox)
        rot.set_popover(rpop)
        self._attach_qat(rot, 'rotate')
        img_grid.attach(crop, 0, 0, 1, 1)
        img_grid.attach(invert, 1, 0, 1, 1)
        img_grid.attach(resize, 0, 1, 1, 1)
        img_grid.attach(rot, 1, 1, 1, 1)
        image_box.append(img_grid)
        ribbon.append(self._ribbon_group(self.tr('图像', 'Image'), image_box))

        # Tools group
        tools = Gtk.Grid(column_spacing=1, row_spacing=1)
        tool_defs = [
            ('pencil', 'pencil', self.tr('铅笔', 'Pencil')),
            ('fill', 'fill', self.tr('用颜色填充', 'Fill with color')),
            ('text', 'text', self.tr('文本', 'Text')),
            ('eraser', 'eraser', self.tr('橡皮擦', 'Eraser')),
            ('picker', 'picker', self.tr('颜色选取器', 'Color picker')),
            ('magnifier', 'magnifier', self.tr('放大镜', 'Magnifier')),
        ]
        for i, (icon, tool, label) in enumerate(tool_defs):
            btn = self._small_tool_toggle(icon, label, tool)
            self._attach_qat(btn, tool)
            tools.attach(btn, i % 3, i // 3, 1, 1)
        ribbon.append(self._ribbon_group(self.tr('工具', 'Tools'), tools))

        # Brush group
        brush_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        brush_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.brush_btn = self._big_button('brush', self.tr('刷子', 'Brushes'),
                                          self.tr('用不同种类的刷子绘画。', 'Paint with different brushes.'),
                                          lambda: self.canvas.set_tool('brush'), toggle=True)
        self._attach_qat(self.brush_btn, 'brush')
        brush_top.append(self.brush_btn)
        self.brush_menu = Gtk.MenuButton()
        self.brush_menu.add_css_class('flat')
        self.brush_menu.set_child(PaintIcon('dropdown', 12))
        bpop = Gtk.Popover()
        bgrid = Gtk.Grid(column_spacing=3, row_spacing=3)
        bgrid.set_margin_top(5); bgrid.set_margin_bottom(5)
        bgrid.set_margin_start(5); bgrid.set_margin_end(5)
        for i, brush in enumerate(BRUSH_ORDER):
            b = Gtk.Button()
            b.set_tooltip_text(BRUSH_LABELS[brush][0 if self.lang_zh else 1])
            b.set_child(BrushIcon(brush, 36))
            b.add_css_class('shape-button')
            b.connect('clicked', lambda x, br=brush, p=bpop: (p.popdown(), self._set_brush(br)))
            bgrid.attach(b, i % 4, i // 4, 1, 1)
        bpop.set_child(bgrid)
        self.brush_menu.set_popover(bpop)
        brush_top.append(self.brush_menu)
        brush_box.append(brush_top)
        ribbon.append(self._ribbon_group(self.tr('刷子', 'Brushes'), brush_box))

        # Shapes gallery
        shapes_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.shapes_grid = Gtk.Grid(column_spacing=1, row_spacing=1)
        self.shapes_grid.add_css_class('shapes-grid')
        self.shape_buttons = {}
        self.shape_page = 0
        self._fill_shape_gallery()
        shapes_box.append(self.shapes_grid)
        arrows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        up = Gtk.Button()
        up.set_child(PaintIcon('chevron_up', 14))
        up.set_tooltip_text(self.tr('上一页形状', 'Previous shapes'))
        up.add_css_class('ribbon-small')
        up.connect('clicked', lambda *a: self._shape_page(-1))
        down = Gtk.Button()
        down.set_child(PaintIcon('chevron_down', 14))
        down.set_tooltip_text(self.tr('下一页形状', 'More shapes'))
        down.add_css_class('ribbon-small')
        down.connect('clicked', lambda *a: self._shape_page(1))
        # rotate down icon 90 deg
        arrows.append(up); arrows.append(down)
        shapes_box.append(arrows)
        ribbon.append(self._ribbon_group(self.tr('形状', 'Shapes'), shapes_box))

        # Outline / fill group
        opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.outline_menu = self._style_menu_button('outline', self.tr('轮廓', 'Outline'),
                                                    SHAPE_OUTLINE_STYLES, 'outline')
        self.fill_menu = self._style_menu_button('fill_style', self.tr('填充', 'Fill'),
                                                 SHAPE_FILL_STYLES, 'fill')
        self._attach_qat(self.outline_menu, 'outline')
        self._attach_qat(self.fill_menu, 'fill-style')
        opts.append(self.outline_menu)
        opts.append(self.fill_menu)
        ribbon.append(self._ribbon_group('', opts, min_width=78))

        # Size group
        size_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.size_menu = Gtk.MenuButton()
        self.size_menu.set_tooltip_text(self.tr('粗细', 'Size'))
        sbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        sbox.append(PaintIcon('outline', 30))
        sbox.append(Gtk.Label(label=self.tr('粗细', 'Size')))
        self.size_menu.set_child(sbox)
        spop2 = Gtk.Popover()
        widthbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for w in LINE_WIDTHS:
            bb = Gtk.Button(label=f'{w} px')
            bb.connect('clicked', lambda b, ww=w, p=spop2: (p.popdown(), self._set_line_width(ww)))
            widthbox.append(bb)
        spop2.set_child(widthbox)
        self.size_menu.set_popover(spop2)
        self._attach_qat(self.size_menu, 'size')
        size_box.append(self.size_menu)
        ribbon.append(self._ribbon_group('', size_box, min_width=55))

        # Colors group
        colors = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        c12 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        c1row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.color1_btn = Gtk.Button()
        self.color1_btn.add_css_class('color-chip')
        self.color1_btn.set_tooltip_text(self.tr('颜色 1 (前景色)', 'Color 1 (foreground)'))
        self.color1_btn.connect('clicked', lambda *a: self._edit_color(1))
        self._attach_qat(self.color1_btn, 'colors')
        lab1 = Gtk.Label(label=self.tr('颜色 1', 'Color 1')); lab1.add_css_class('ribbon-label')
        c1row.append(self.color1_btn); c1row.append(lab1)
        c2row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.color2_btn = Gtk.Button()
        self.color2_btn.add_css_class('color-chip')
        self.color2_btn.set_tooltip_text(self.tr('颜色 2 (背景色)', 'Color 2 (background)'))
        self.color2_btn.connect('clicked', lambda *a: self._edit_color(2))
        self._attach_qat(self.color2_btn, 'colors')
        lab2 = Gtk.Label(label=self.tr('颜色 2', 'Color 2')); lab2.add_css_class('ribbon-label')
        c2row.append(self.color2_btn); c2row.append(lab2)
        c12.append(c1row); c12.append(c2row)
        colors.append(c12)
        self.palette_grid = Gtk.Grid(column_spacing=1, row_spacing=1)
        colors.append(self.palette_grid)
        edit_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        eb = Gtk.Button()
        eb.add_css_class('ribbon-big')
        ebox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        ebox.append(PaintIcon('edit_colors', 30))
        elab = Gtk.Label(label=self.tr('编辑\n颜色', 'Edit\ncolors')); elab.add_css_class('ribbon-label')
        ebox.append(elab)
        eb.set_child(ebox)
        eb.set_tooltip_text(self.tr('编辑颜色', 'Edit colors'))
        eb.connect('clicked', lambda *a: self._edit_color(1))
        edit_col.append(eb)
        colors.append(edit_col)
        ribbon.append(self._ribbon_group(self.tr('颜色', 'Colors'), colors))
        self._build_palette()

        return ribbon

    def _style_menu_button(self, icon, label_text, styles, kind):
        mb = Gtk.MenuButton()
        mb.add_css_class('flat')
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        box.append(PaintIcon(icon, 18))
        lab = Gtk.Label(label=label_text)
        lab.add_css_class('ribbon-small-label')
        box.append(lab)
        mb.set_child(box)
        pop = Gtk.Popover()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for key, (zh, en) in styles.items():
            bb = Gtk.Button(label=zh if self.lang_zh else en)
            bb.connect('clicked', lambda b, k=key, p=pop: (p.popdown(), self._set_style(kind, k)))
            vbox.append(bb)
        pop.set_child(vbox)
        mb.set_popover(pop)
        return mb

    def _build_view_ribbon(self):
        ribbon = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        ribbon.add_css_class('ribbon')
        zoom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        zin = self._big_button('zoomin', self.tr('放大', 'Zoom in'),
                               self.tr('放大当前图片。 (Ctrl+PgUp)', 'Zoom in (Ctrl+PgUp)'),
                               self.canvas.zoom_in)
        zout = self._big_button('zoomout', self.tr('缩小', 'Zoom out'),
                                self.tr('缩小当前图片。 (Ctrl+PgDn)', 'Zoom out (Ctrl+PgDn)'),
                                self.canvas.zoom_out)
        self._attach_qat(zin, 'zoom-in')
        self._attach_qat(zout, 'zoom-out')
        zoom.append(zin)
        zoom.append(zout)
        z100 = self._big_button('magnifier', '100%', self.tr('缩放到 100%', 'Zoom to 100%'),
                                lambda: self.canvas.set_zoom(1.0))
        self._attach_qat(z100, 'zoom-100')
        zoom.append(z100)
        ribbon.append(self._ribbon_group(self.tr('缩放', 'Zoom'), zoom))

        show = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.cb_ruler = Gtk.CheckButton(label=self.tr('标尺 (Ctrl+R)', 'Rulers (Ctrl+R)'))
        self.cb_grid = Gtk.CheckButton(label=self.tr('网格线 (Ctrl+G)', 'Gridlines (Ctrl+G)'))
        self.cb_status = Gtk.CheckButton(label=self.tr('状态栏', 'Status bar'))
        self.cb_ruler.connect('toggled', lambda b: self._toggle_rulers(b.get_active()))
        self.cb_grid.connect('toggled', lambda b: self._toggle_grid(b.get_active()))
        self._attach_qat(self.cb_ruler, 'ruler')
        self._attach_qat(self.cb_grid, 'grid')
        self.cb_status.set_active(True)
        self.cb_status.connect('toggled', lambda b: self._toggle_status(b.get_active()))
        self._attach_qat(self.cb_status, 'statusbar')
        show.append(self.cb_ruler); show.append(self.cb_grid); show.append(self.cb_status)
        ribbon.append(self._ribbon_group(self.tr('显示或隐藏', 'Show or hide'), show))

        disp = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        fs_btn = self._big_button('fullscreen', self.tr('全屏', 'Full screen'),
                                  self.tr('全屏查看图片。 (F11)', 'View full screen (F11)'),
                                  self._toggle_fullscreen)
        self._attach_qat(fs_btn, 'fullscreen')
        disp.append(fs_btn)
        self.thumb_btn = self._big_button('thumbnail', self.tr('缩略图', 'Thumbnail'),
                                          self.tr('显示或隐藏缩略图。', 'Show or hide the thumbnail'),
                                          self._toggle_thumbnail)
        self._attach_qat(self.thumb_btn, 'thumbnail')
        disp.append(self.thumb_btn)
        ribbon.append(self._ribbon_group(self.tr('显示', 'Display'), disp))

        # Application theme: system / light / dark.  This is paim-specific and
        # persists independently of the desktop's GTK theme.
        theme_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        theme_menu = Gtk.MenuButton()
        self.theme_menu = theme_menu
        theme_menu.add_css_class('flat')
        theme_inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        self.theme_mode_label = Gtk.Label()
        self.theme_mode_label.add_css_class('ribbon-small-label')
        theme_inner.append(self.theme_mode_label)
        theme_inner.append(PaintIcon('dropdown', 12))
        theme_menu.set_child(theme_inner)
        theme_menu.set_tooltip_text(self.tr('应用主题', 'Application theme'))
        theme_pop = Gtk.Popover()
        theme_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.theme_mode_buttons = {}
        first_btn = None
        for mode, text in (
                ('auto', self.tr('跟随系统', 'Follow system')),
                ('light', self.tr('浅色', 'Light')),
                ('dark', self.tr('深色', 'Dark'))):
            cb = Gtk.CheckButton(label=text)
            if first_btn is not None:
                cb.set_group(first_btn)
            else:
                first_btn = cb
            cb.set_active(mode == self.theme_mode)
            cb.connect('toggled', self._on_theme_mode_toggled, mode)
            self.theme_mode_buttons[mode] = cb
            theme_list.append(cb)
        theme_pop.set_child(theme_list)
        self.theme_popover = theme_pop
        theme_menu.set_popover(theme_pop)
        self._attach_qat(theme_menu, 'theme')
        theme_box.append(theme_menu)
        ribbon.append(self._ribbon_group(self.tr('主题', 'Theme'), theme_box))
        self._update_theme_menu()
        return ribbon

    def _build_text_bar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.add_css_class('textbar')
        lab = Gtk.Label(label=self.tr('文本工具', 'Text tools'))
        lab.add_css_class('group-title')
        bar.append(lab)
        bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        bar.append(Gtk.Label(label=self.tr('字体:', 'Font:')))
        self.font_dropdown = Gtk.DropDown()
        families = [f.get_name() for f in PangoCairo.FontMap.get_default().list_families()]
        # Common first choices; keep the popup usable.
        common = ['Sans', 'Serif', 'Monospace', 'Arial', 'Times New Roman', 'Courier New',
                  'Microsoft YaHei', 'Noto Sans CJK SC']
        vals = []
        for f in common:
            if f not in vals:
                vals.append(f)
        for f in sorted(families):
            if f not in vals:
                vals.append(f)
        self.font_families = vals
        self.font_dropdown.set_model(Gtk.StringList.new(vals))
        self.font_dropdown.set_selected(0)
        self.font_dropdown.connect('notify::selected', self._font_changed)
        bar.append(self.font_dropdown)
        bar.append(Gtk.Label(label=self.tr('大小:', 'Size:')))
        self.font_size = Gtk.SpinButton.new_with_range(4, 200, 1)
        self.font_size.set_value(12)
        self.font_size.set_size_request(70, -1)
        self.font_size.connect('value-changed', self._font_size_changed)
        bar.append(self.font_size)
        self.btn_bold = Gtk.ToggleButton(label='B')
        self.btn_bold.set_tooltip_text(self.tr('加粗', 'Bold'))
        self.btn_bold.connect('toggled', lambda b: self._set_text_style('bold', b.get_active()))
        self.btn_italic = Gtk.ToggleButton(label='I')
        self.btn_italic.set_tooltip_text(self.tr('斜体', 'Italic'))
        self.btn_italic.connect('toggled', lambda b: self._set_text_style('italic', b.get_active()))
        self.btn_under = Gtk.ToggleButton(label='U')
        self.btn_under.set_tooltip_text(self.tr('下划线', 'Underline'))
        self.btn_under.connect('toggled', lambda b: self._set_text_style('underline', b.get_active()))
        bar.append(self.btn_bold); bar.append(self.btn_italic); bar.append(self.btn_under)
        bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        bar.append(Gtk.Label(label=self.tr('背景:', 'Background:')))
        self.btn_opaque = Gtk.ToggleButton(label=self.tr('不透明', 'Opaque'))
        self.btn_transparent = Gtk.ToggleButton(label=self.tr('透明', 'Transparent'))
        self.btn_transparent.set_group(self.btn_opaque)
        self.btn_opaque.set_active(False)
        self.btn_transparent.set_active(True)
        self.btn_opaque.connect('toggled', lambda b: self._set_text_opaque(b.get_active()))
        bar.append(self.btn_opaque); bar.append(self.btn_transparent)
        return bar

    # ------------------------------------------------------------------
    # Palette / color UI
    def _build_palette(self):
        while self.palette_grid.get_first_child():
            self.palette_grid.remove(self.palette_grid.get_first_child())
        for i, color in enumerate(DEFAULT_PALETTE[:40]):
            b = Gtk.Button()
            b.add_css_class('palette-swatch')
            b.set_size_request(18, 18)
            b.set_tooltip_text(color)
            p = Gtk.CssProvider()
            p.load_from_data(f'button.palette-swatch {{ background: {color}; }}'.encode())
            b.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            b.connect('clicked', lambda btn, c=color: self._palette_left(c))
            gc = Gtk.GestureClick()
            gc.set_button(3)
            gc.connect('pressed', lambda g, n, x, y, c=color: self._palette_right(c))
            b.add_controller(gc)
            self.palette_grid.attach(b, i % 10, i // 10, 1, 1)
        self._sync_palette()

    def _sync_palette(self):
        if not hasattr(self, 'color1_btn') or not hasattr(self, 'canvas'):
            return
        c1 = '#%02x%02x%02x' % self.canvas.color1
        c2 = '#%02x%02x%02x' % self.canvas.color2
        for btn, color in ((self.color1_btn, c1), (self.color2_btn, c2)):
            p = Gtk.CssProvider()
            p.load_from_data(f'button {{ background: {color}; }}'.encode())
            btn.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _palette_left(self, color):
        self.canvas.set_colors(color1=hex_to_rgb(color))
        self._sync_palette()

    def _palette_right(self, color):
        self.canvas.set_colors(color2=hex_to_rgb(color))
        self._sync_palette()

    def _on_colors_changed(self, c1, c2):
        self._sync_palette()

    def _edit_color(self, which):
        initial = self.canvas.color1 if which == 1 else self.canvas.color2
        def apply(rgb):
            if which == 1:
                self.canvas.set_colors(color1=rgb)
            else:
                self.canvas.set_colors(color2=rgb)
            self._sync_palette()
        ColorDialog(self, initial, apply).present()

    # ------------------------------------------------------------------
    # Shapes / tool state
    def _fill_shape_gallery(self):
        while self.shapes_grid.get_first_child():
            self.shapes_grid.remove(self.shapes_grid.get_first_child())
        page_size = 15
        items = SHAPE_ORDER[:page_size] if self.shape_page == 0 else SHAPE_ORDER[page_size:]
        for i, shape in enumerate(items):
            b = Gtk.Button()
            b.add_css_class('shape-button')
            b.set_tooltip_text(SHAPE_LABELS_ZH.get(shape, shape) if self.lang_zh else SHAPE_LABELS_EN.get(shape, shape))
            b.set_child(ShapeIcon(shape, 24))
            b.connect('clicked', lambda x, s=shape: self._choose_shape(s))
            self._attach_qat(b, 'shapes')
            self.shapes_grid.attach(b, i % 5, i // 5, 1, 1)
            self.shape_buttons[shape] = b
        self._update_shape_active()

    def _shape_page(self, delta):
        self.shape_page = (self.shape_page + delta) % 2
        self._fill_shape_gallery()

    def _choose_shape(self, shape):
        self.canvas.set_tool(shape)
        self._update_shape_active()
        self._set_tool_button_state(shape)

    def _update_shape_active(self):
        if not hasattr(self, 'canvas'):
            return
        for shape, b in getattr(self, 'shape_buttons', {}).items():
            if shape == self.canvas.tool:
                b.add_css_class('active-shape')
            else:
                b.remove_css_class('active-shape')

    def _set_opaque_selection(self, opaque):
        self.canvas.opaque_selection = bool(opaque)
        self.canvas.drawing.queue_draw()

    def _set_brush(self, brush):
        self.canvas.set_brush(brush)
        self._set_tool_button_state('brush')

    def _set_line_width(self, width):
        self.canvas.line_width = width
        self.size_menu.set_tooltip_text(f'{self.tr("粗细", "Size")}: {width}px')
        self.canvas.drawing.queue_draw()
        self._update_status_labels()

    def _set_style(self, kind, key):
        if kind == 'outline':
            self.canvas.outline_style = key
        else:
            self.canvas.fill_style = key
        self.canvas.drawing.queue_draw()

    def _on_tool_toggled(self, btn, tool):
        if btn.get_active():
            self._commit_current_text()
            self.canvas.set_tool(tool)
            self._set_tool_button_state(tool)
            self.textbar_revealer.set_reveal_child(tool == 'text')

    def _set_tool_button_state(self, tool):
        for t, b in getattr(self, 'tool_buttons', {}).items():
            b.handler_block_by_func(self._on_tool_toggled) if False else None
            if t == tool:
                if not b.get_active():
                    b.set_active(True)
            else:
                if b.get_active():
                    b.set_active(False)
        if hasattr(self, 'brush_btn'):
            self.brush_btn.set_active(tool == 'brush')
        self._update_shape_active()
        self._update_quick_access()

    def _update_quick_access(self):
        if not hasattr(self, 'qat_buttons'):
            return
        for key, btn in self.qat_buttons.items():
            if key == 'undo':
                btn.set_sensitive(self.doc.can_undo())
            elif key == 'redo':
                btn.set_sensitive(self.doc.can_redo())
            elif key in ('cut', 'copy', 'crop'):
                btn.set_sensitive(self.doc.selection is not None)
            else:
                btn.set_sensitive(True)
        if hasattr(self, 'tool_buttons'):
            self._update_shape_active()

    # ------------------------------------------------------------------
    # Status / title
    def _on_canvas_status(self, pos, sel, width, height, zoom):
        self._update_status_labels(pos, sel, width, height, zoom)

    def _update_status_labels(self, pos=None, sel=None, width=None, height=None, zoom=None):
        if width is None:
            width, height = self.doc.width, self.doc.height
        if zoom is None:
            zoom = self.canvas.zoom
        if pos:
            self.pos_label.set_text(f'{pos[0]}, {pos[1]} px')
        else:
            self.pos_label.set_text('')
        if sel:
            x, y, w, h = sel
            self.sel_label.set_text(f'{w} × {h}')
        else:
            self.sel_label.set_text('')
        self.size_label.set_text(f'{width} × {height} px')
        self.zoom_label.set_text(f'{int(round(zoom * 100))}%')
        self._sync_zoom_controls(zoom)
        if hasattr(self, 'thumb_area'):
            self.thumb_area.queue_draw()

    def _sync_zoom_controls(self, zoom=None):
        if not hasattr(self, 'zoom_scale'):
            return
        if zoom is None:
            zoom = self.canvas.zoom
        if abs(self.zoom_scale.get_value() - zoom) > 1e-6:
            self.zoom_scale.handler_block_by_func(self._on_zoom_scale) if False else None
            self.zoom_scale.set_value(zoom)
        self.zoom_label.set_text(f'{int(round(zoom * 100))}%')

    def _on_canvas_zoom(self, zoom):
        self.zoom = zoom
        self._sync_zoom_controls(zoom)
        self._update_status_labels()
        self._update_title()

    def _on_zoom_scale(self, scale):
        z = scale.get_value()
        if abs(z - self.canvas.zoom) > 1e-4:
            self.canvas.set_zoom(z)
        self.zoom_label.set_text(f'{int(round(z * 100))}%')

    def _on_canvas_pointer(self, point):
        # updated through status callback, so nothing else required
        pass

    def _on_canvas_modified(self):
        self._update_title()
        self._update_action_sensitivity()
        self._update_quick_access()

    def _update_title(self):
        if not hasattr(self, 'title_label'):
            return
        name = os.path.basename(self.doc.filename) if self.doc.filename else self.tr('无标题', 'Untitled')
        mark = ' *' if self.doc.dirty else ''
        self.title_label.set_text(f'{name}{mark} - paim')
        self.set_title(self.title_label.get_text())

    # ------------------------------------------------------------------
    # Actions and shortcuts
    def _build_actions(self):
        actions = {
            'new': self._new_clicked, 'open': self._open_clicked, 'save': self._save_clicked,
            'save-as': self._save_as_clicked, 'print': self._print, 'print-preview': self._print_preview,
            'page-setup': self._page_setup, 'properties': self._properties,
            'exit': self.close, 'undo': self._undo, 'redo': self._redo,
            'cut': self._cut_clicked, 'copy': self._copy_clicked, 'paste': self._paste_clicked,
            'delete': self._delete, 'select-all': self._select_all, 'invert-selection': self._invert_selection,
            'crop': self._crop, 'resize': self._resize_dialog, 'rotate-right': lambda: self._rotate('right'),
            'rotate-left': lambda: self._rotate('left'), 'invert-colors': self._invert_colors,
            'clear-image': self._clear_image, 'help': self._help, 'about': self._about,
            'zoom-in': self.canvas.zoom_in, 'zoom-out': self.canvas.zoom_out,
            'zoom-100': lambda: self.canvas.set_zoom(1.0), 'fullscreen': self._toggle_fullscreen,
            'grid': lambda: self.cb_grid.set_active(not self.cb_grid.get_active()),
            'ruler': lambda: self.cb_ruler.set_active(not self.cb_ruler.get_active()),
            'statusbar': lambda: self.cb_status.set_active(not self.cb_status.get_active()),
            'thumbnail': self._toggle_thumbnail, 'font-underline': lambda: self.btn_under.set_active(not self.btn_under.get_active()),
            'bold': lambda: self.btn_bold.set_active(not self.btn_bold.get_active()),
            'italic': lambda: self.btn_italic.set_active(not self.btn_italic.get_active()),
        }
        for name, cb in actions.items():
            act = Gio.SimpleAction.new(name, None)
            act.connect('activate', lambda a, p, c=cb: c())
            self.add_action(act)
        app = self.get_application()
        accels = {
            'app.new': ['<Control>n'], 'app.open': ['<Control>o'], 'app.save': ['<Control>s'],
            'app.save-as': ['F12'], 'app.print': ['<Control>p'], 'app.undo': ['<Control>z'],
            'app.redo': ['<Control>y'], 'app.cut': ['<Control>x'], 'app.copy': ['<Control>c'],
            'app.paste': ['<Control>v'], 'app.select-all': ['<Control>a'],
            'app.crop': ['<Control><Shift>x'], 'app.resize': ['<Control>w'],
            'app.properties': ['<Control>e'], 'app.invert-colors': ['<Control><Shift>i'],
            'app.zoom-in': ['<Control>Page_Up'], 'app.zoom-out': ['<Control>Page_Down'],
            'app.fullscreen': ['F11'], 'app.help': ['F1'], 'app.grid': ['<Control>g'],
            'app.ruler': ['<Control>r'], 'app.clear-image': ['<Control><Shift>n'],
            'app.bold': ['<Control>b'], 'app.italic': ['<Control>i'],
            'app.font-underline': ['<Control>u'],
        }
        # Window actions are registered as win.<name>; accelerators target them.
        for name, bindings in accels.items():
            win_name = 'win.' + name.removeprefix('app.')
            app.set_accels_for_action(win_name, bindings)

    # ------------------------------------------------------------------
    # Backstage file menu
    def _build_backstage(self):
        self.backstage = Gtk.Popover()
        self.backstage.set_has_arrow(False)
        self.backstage.set_position(Gtk.PositionType.BOTTOM)
        self.backstage.add_css_class('backstage')
        self.file_tab.set_popover(self.backstage)
        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer.set_size_request(760, 540)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left.set_size_request(210, -1)
        left.add_css_class('backstage-left')
        items = [
            ('new', self.tr('新建', 'New'), 'Ctrl+N'),
            ('open', self.tr('打开', 'Open'), 'Ctrl+O'),
            ('save', self.tr('保存', 'Save'), 'Ctrl+S'),
            ('save-as', self.tr('另存为', 'Save as'), 'F12'),
            ('print', self.tr('打印', 'Print'), 'Ctrl+P'),
            ('print-preview', self.tr('打印预览', 'Print preview'), ''),
            ('page-setup', self.tr('页面设置', 'Page setup'), ''),
            ('properties', self.tr('属性', 'Properties'), 'Ctrl+E'),
            ('about', self.tr('关于 paim', 'About paim'), ''),
            ('exit', self.tr('退出', 'Exit'), ''),
        ]
        for action, text, accel in items:
            b = Gtk.Button()
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.append(paint_image(action if action in ('new','open','save','print') else 'app', 18))
            lab = Gtk.Label(label=text)
            lab.set_xalign(0); lab.set_hexpand(True)
            row.append(lab)
            if accel:
                al = Gtk.Label(label=accel); al.add_css_class('hint'); row.append(al)
            b.set_child(row)
            b.add_css_class('backstage-item')
            b.connect('clicked', lambda x, a=action: self._backstage_action(a))
            left.append(b)
        left.append(Gtk.Separator())
        scan = Gtk.Button(label=self.tr('从扫描仪或照相机...', 'From scanner or camera...'))
        scan.add_css_class('backstage-item')
        scan.connect('clicked', lambda *a: self._scanner_unavailable())
        left.append(scan)
        email = Gtk.Button(label=self.tr('在电子邮件中发送', 'Send in e-mail'))
        email.add_css_class('backstage-item')
        email.connect('clicked', lambda *a: self._send_email())
        left.append(email)
        desktop = Gtk.Button(label=self.tr('设置为桌面背景', 'Set as desktop background'))
        desktop.add_css_class('backstage-item')
        desktop.connect('clicked', lambda *a: self._set_wallpaper())
        left.append(desktop)
        outer.append(left)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right.set_hexpand(True)
        right.set_margin_top(18); right.set_margin_bottom(18)
        right.set_margin_start(18); right.set_margin_end(18)
        title = Gtk.Label(label=self.tr('最近查看的图片', 'Recently viewed pictures'))
        title.set_xalign(0); title.add_css_class('group-title')
        right.append(title)
        self.recent_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        right.append(self.recent_box)
        self.recent_empty = Gtk.Label(label=self.tr('（没有最近使用的文件）', '(No recent files)'))
        self.recent_empty.set_xalign(0); self.recent_empty.add_css_class('hint')
        right.append(self.recent_empty)
        outer.append(right)
        self.backstage.set_child(outer)
        self._refresh_recent()

    def _open_backstage(self):
        if self.backstage.get_visible():
            self.backstage.popdown()
        else:
            self._refresh_recent()
            rect = Gdk.Rectangle()
            rect.x = 0
            self.backstage.set_pointing_to(rect)
            self.backstage.popup()

    def _backstage_action(self, action):
        self.backstage.popdown()
        {
            'new': self._new_clicked, 'open': self._open_clicked, 'save': self._save_clicked,
            'save-as': self._save_as_clicked, 'print': self._print,
            'print-preview': self._print_preview, 'page-setup': self._page_setup, 'properties': self._properties,
            'about': self._about, 'exit': self.close,
        }.get(action, lambda: None)()

    # ------------------------------------------------------------------
    # Document lifecycle and file dialogs
    def _confirm_save(self, callback):
        if not self.doc.dirty:
            callback()
            return
        dlg = Gtk.MessageDialog(transient_for=self, modal=True,
                                message_type=Gtk.MessageType.WARNING,
                                text=self.tr('你想将更改保存到 %s 吗?' % (os.path.basename(self.doc.filename) if self.doc.filename else self.tr('无标题', 'Untitled')),
                                             'Do you want to save changes?'),
                                buttons=Gtk.ButtonsType.NONE)
        dlg.add_button(self.tr('保存', 'Save'), Gtk.ResponseType.YES)
        dlg.add_button(self.tr('不保存', "Don't save"), Gtk.ResponseType.NO)
        dlg.add_button(self.tr('取消', 'Cancel'), Gtk.ResponseType.CANCEL)
        def resp(d, r):
            d.destroy()
            if r == Gtk.ResponseType.YES:
                self._save(on_done=callback)
            elif r == Gtk.ResponseType.NO:
                callback()
        dlg.connect('response', resp)
        dlg.present()

    def _new_clicked(self):
        def go():
            w, h = self.doc.width, self.doc.height
            self.doc = Document(w, h)
            self._bind_document()
        self._confirm_save(go)

    def _bind_document(self):
        self.canvas.reset_document(self.doc)
        self.canvas.doc = self.doc
        self.file_tab.set_sensitive(True)
        self._update_title()
        self._update_status_labels()
        self._update_action_sensitivity()
        self._update_quick_access()

    def _open_clicked(self):
        def choose():
            dlg = Gtk.FileDialog()
            dlg.set_title(self.tr('打开', 'Open'))
            filters = Gtk.ListStore()  # not used
            f = Gtk.FileFilter()
            f.set_name(self.tr('所有图片文件', 'All picture files'))
            f.add_pattern('*.png'); f.add_pattern('*.jpg'); f.add_pattern('*.jpeg')
            f.add_pattern('*.bmp'); f.add_pattern('*.dib'); f.add_pattern('*.gif')
            f.add_pattern('*.tif'); f.add_pattern('*.tiff'); f.add_pattern('*.webp')
            filters2 = Gio.ListStore.new(Gtk.FileFilter)
            filters2.append(f)
            dlg.set_filters(filters2)
            dlg.set_default_filter(f)
            dlg.open(self, None, self._on_open_selected)
        self._confirm_save(choose)

    def _on_open_selected(self, dlg, result):
        try:
            f = dlg.open_finish(result)
        except GLib.Error:
            return
        if f:
            self.load_path(f.get_path())

    def load_path(self, path):
        try:
            doc = Document.open(path)
        except Exception as exc:
            MessageDialog(self, self.tr('paim 无法打开该文件。', 'paim cannot open this file.'),
                          str(exc), Gtk.MessageType.ERROR).present()
            return
        self.doc = doc
        self._bind_document()
        self._add_recent(path)

    def _save_clicked(self):
        self._save()

    def _save(self, on_done=None):
        self._commit_current_text()
        self.canvas.commit_floating()
        if self.doc.filename:
            self._save_to_path(self.doc.filename, on_done=on_done)
        else:
            self._save_as_clicked(on_done=on_done)

    def _save_as_clicked(self, on_done=None):
        self._commit_current_text()
        self.canvas.commit_floating()
        self._save_after = on_done
        dlg = Gtk.FileDialog()
        dlg.set_title(self.tr('另存为', 'Save As'))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        for name, patterns in [
            (self.tr('PNG 图片', 'PNG picture'), ['*.png']),
            (self.tr('JPEG 图片', 'JPEG picture'), ['*.jpg', '*.jpeg']),
            (self.tr('BMP 图片', 'BMP picture'), ['*.bmp', '*.dib']),
            (self.tr('GIF 图片', 'GIF picture'), ['*.gif']),
            (self.tr('所有图片文件', 'All picture files'), ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.gif']),
        ]:
            f = Gtk.FileFilter(); f.set_name(name)
            for pat in patterns:
                f.add_pattern(pat)
            filters.append(f)
            if name.startswith(self.tr('PNG', 'PNG')):
                dlg.set_default_filter(f)
        dlg.set_filters(filters)
        base = os.path.basename(self.doc.filename) if self.doc.filename else (self.tr('无标题', 'Untitled') + '.png')
        dlg.set_initial_name(base)
        dlg.save(self, None, self._on_save_selected)

    def _on_save_selected(self, dlg, result):
        try:
            f = dlg.save_finish(result)
        except GLib.Error:
            return
        if not f:
            return
        path = f.get_path()
        root, ext = os.path.splitext(path)
        if not ext:
            ext = '.png'
            path += ext
        ext = ext.lower().lstrip('.')
        if ext in ('bmp', 'dib'):
            def done(fmt, bits):
                self._save_to_path(path, fmt=fmt, bits=bits)
            SaveOptionsDialog(self, ext, done).present()
        else:
            self._save_to_path(path, fmt=ext)

    def _save_to_path(self, path, fmt=None, bits=24, on_done=None):
        try:
            self.doc.save(path, fmt=fmt, bits=bits)
            self.doc.dirty = False
        except Exception as exc:
            MessageDialog(self, self.tr('paim 不能存储该文件。', 'paim cannot save this file.'),
                          str(exc), Gtk.MessageType.ERROR).present()
            return
        try:
            self._add_recent(path)
        except Exception:
            pass
        self._update_title()
        self._update_action_sensitivity()
        self._update_quick_access()
        cb = on_done if on_done is not None else self._save_after
        self._save_after = None
        if cb:
            cb()

    def _add_recent(self, path):
        path = os.path.abspath(path)
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]
        self._save_recent()
        self._refresh_recent()

    def _load_recent(self):
        try:
            path = Path(GLib.get_user_data_dir()) / 'mspaint-linux' / 'recent.json'
            if path.exists():
                self.recent_files = json.loads(path.read_text()) or []
        except Exception:
            self.recent_files = []

    def _save_recent(self):
        try:
            d = Path(GLib.get_user_data_dir()) / 'mspaint-linux'
            d.mkdir(parents=True, exist_ok=True)
            (d / 'recent.json').write_text(json.dumps(self.recent_files))
        except Exception:
            pass

    def _refresh_recent(self):
        if not hasattr(self, 'recent_box'):
            return
        while self.recent_box.get_first_child():
            self.recent_box.remove(self.recent_box.get_first_child())
        valid = [p for p in self.recent_files if os.path.exists(p)]
        self.recent_files = valid
        self.recent_empty.set_visible(not valid)
        for p in valid[:8]:
            b = Gtk.Button(label=os.path.basename(p))
            b.set_tooltip_text(p)
            b.set_halign(Gtk.Align.START)
            b.add_css_class('recent-item')
            b.connect('clicked', lambda x, pp=p: self._load_recent_file(pp))
            self.recent_box.append(b)

    def _load_recent_file(self, path):
        self.backstage.popdown()
        def go():
            self.load_path(path)
        self._confirm_save(go)

    # ------------------------------------------------------------------
    # Clipboard
    def _copy_to_clipboard(self, surface):
        if surface is None:
            return False
        self._quick_clipboard = surface
        png = surface_to_png_bytes(surface, with_alpha=True)
        cb = self.get_clipboard()
        png_provider = Gdk.ContentProvider.new_for_bytes('image/png', GLib.Bytes.new(png))
        try:
            texture_provider = Gdk.ContentProvider.new_for_value(Gdk.Texture.new_from_bytes(GLib.Bytes.new(png)))
            provider = Gdk.ContentProvider.new_union([texture_provider, png_provider])
        except Exception:
            provider = png_provider
        cb.set_content(provider)
        return True

    def _copy_clicked(self):
        s = self.canvas.copy_selection()
        if s is None:
            MessageDialog(self, self.tr('没有要复制的内容。', 'Nothing is selected.')).present()
            return
        self._copy_to_clipboard(s)
        self._update_action_sensitivity()

    def _cut_clicked(self):
        s = self.canvas.copy_selection()
        if s is None:
            return
        self._copy_to_clipboard(s)
        self.canvas.delete_selection()
        self._update_action_sensitivity()

    def _paste_clicked(self):
        cb = self.get_clipboard()
        def got(provider, result):
            try:
                texture = cb.read_texture_finish(result)
            except GLib.Error:
                texture = None
            if texture is not None:
                try:
                    data = texture.save_to_png_bytes()
                    self.canvas.paste_png_bytes(bytes(data.get_data()))
                    return
                except Exception:
                    pass
            # Some clipboard providers (notably several X11 applications)
            # expose image/png but no texture value.  Read the stream instead.
            try:
                cb.read_async(['image/png', 'image/jpeg', 'image/bmp'],
                              GLib.PRIORITY_DEFAULT, None, got_stream)
            except Exception:
                self._paste_fallback()
        def got_stream(source, result):
            try:
                stream, mime = cb.read_finish(result)
            except GLib.Error:
                stream = None
            if stream is not None:
                try:
                    data = stream.read_bytes(64 * 1024 * 1024, None)
                    self.canvas.paste_png_bytes(bytes(data.get_data()))
                    return
                except Exception:
                    pass
            self._paste_fallback()
        cb.read_texture_async(None, got)

    def _paste_fallback(self):
        if self._quick_clipboard is not None:
            # Clone before pasting to avoid sharing a mutable surface.
            self.canvas.paste_surface(_copy_surface_ref(self._quick_clipboard))

    def _paste_from_file(self):
        dlg = Gtk.FileDialog()
        dlg.set_title(self.tr('粘贴来源', 'Paste from'))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter(); f.set_name(self.tr('所有图片文件', 'All picture files'))
        for pat in ('*.png', '*.jpg', '*.jpeg', '*.bmp', '*.gif', '*.tif', '*.tiff', '*.webp'):
            f.add_pattern(pat)
        filters.append(f)
        dlg.set_filters(filters)
        dlg.open(self, None, self._on_paste_file)

    def _on_paste_file(self, dlg, result):
        try:
            f = dlg.open_finish(result)
        except GLib.Error:
            return
        if f:
            try:
                doc = Document.open(f.get_path())
            except Exception as exc:
                MessageDialog(self, self.tr('无法打开该文件。', 'Cannot open file.'), str(exc), Gtk.MessageType.ERROR).present()
                return
            self.canvas.paste_surface(doc.surface)

    # ------------------------------------------------------------------
    # Commands
    def _undo(self):
        self._commit_current_text()
        self.canvas.commit_floating()
        if self.doc.undo():
            self.canvas.update_after_image_change()
            self._update_title()
            self._update_action_sensitivity()
            self._update_quick_access()

    def _redo(self):
        self._commit_current_text()
        self.canvas.commit_floating()
        if self.doc.redo():
            self.canvas.update_after_image_change()
            self._update_title()
            self._update_action_sensitivity()
            self._update_quick_access()

    def _delete(self):
        self.canvas.delete_selection()
        self._update_action_sensitivity()

    def _select_all(self):
        self.canvas.select_all()
        self._update_action_sensitivity()

    def _invert_selection(self):
        if self.doc.selection is None:
            self.canvas.select_all()
        else:
            self.canvas.commit_floating()
            self.doc.invert_selection()
        self.canvas.drawing.queue_draw()
        self._update_action_sensitivity()

    def _crop(self):
        if self.canvas.crop():
            self._update_status_labels(); self._update_action_sensitivity(); self._update_title()

    def _resize_dialog(self):
        self._commit_current_text()
        def apply(w, h, skew_h, skew_v):
            if self.doc.selection:
                # Paint applies resize to the selection.  The document-level
                # helper currently resizes the whole image; resizing the
                # selection is handled by cropping its bounds and re-pasting.
                s = self.canvas.get_clipboard_surface()
                if s is None:
                    return
                self.canvas.commit_floating()
                self.doc.push_undo('调整大小')
                # scale selection floating in place using cairo
                sel = self.doc.selection
                if sel:
                    x, y, sw, sh = sel.rect
                    scaled = scale_surface(s, w, h)
                    ctx = cairo.Context(self.doc.surface)
                    ctx.set_operator(cairo.OPERATOR_SOURCE)
                    ctx.set_source_rgba(*self.doc.background)
                    ctx.rectangle(x, y, sw, sh); ctx.fill()
                    self.doc.selection = Selection(x, y, scaled.get_width(), scaled.get_height(),
                                                   floating=scaled, floating_origin=(x, y))
                    self.doc.dirty = True
                    self.canvas.update_after_image_change()
            else:
                if self.doc.resize(w, h):
                    self.canvas.update_after_image_change()
                if (skew_h or skew_v) and self.doc.skew(skew_h, skew_v):
                    self.canvas.update_after_image_change()
            self._update_title()
            self._update_action_sensitivity()
        ResizeDialog(self, self.doc.width, self.doc.height, apply).present()

    def _rotate(self, mode):
        self._commit_current_text()
        self.canvas.commit_floating()
        self.doc.rotate(mode)
        self.canvas.update_after_image_change()
        self._update_title()

    def _invert_colors(self):
        self._commit_current_text()
        self.canvas.commit_floating()
        self.doc.invert_colors()
        self.canvas.update_after_image_change()
        self._update_title()

    def _clear_image(self):
        self._commit_current_text()
        self.canvas.commit_floating()
        self.doc.clear_image()
        self.canvas.update_after_image_change()
        self._update_title()

    def _properties(self):
        def apply(w, h, color, transparent):
            if w != self.doc.width or h != self.doc.height:
                self.doc.resize_canvas(w, h)
            if not color:
                self._to_black_white()
            self.canvas.update_after_image_change()
            self._update_title()
        AttributesDialog(self, self.doc, apply).present()

    def _to_black_white(self):
        from PIL import Image
        img = self.doc.to_pil(with_alpha=False).convert('1').convert('RGB')
        from .document import pil_to_surface
        self.doc.push_undo('转换为黑白')
        self.doc.surface = pil_to_surface(img)
        self.doc.dirty = True

    # ------------------------------------------------------------------
    # Text
    def _commit_current_text(self):
        self.canvas._commit_text()

    def _font_changed(self, dropdown, pspec=None):
        i = dropdown.get_selected()
        if 0 <= i < len(self.font_families):
            self.canvas.text_family = self.font_families[i]
            self.canvas.update_text_style()

    def _font_size_changed(self, spin):
        self.canvas.text_size = spin.get_value()
        self.canvas.update_text_style()

    def _set_text_style(self, attr, value):
        setattr(self.canvas, 'text_' + attr, value)
        self.canvas.update_text_style()

    def _set_text_opaque(self, value):
        self.canvas.text_opaque = value
        self.canvas.update_text_style()

    # ------------------------------------------------------------------
    # View
    def _switch_ribbon(self, btn, name):
        if not btn.get_active():
            return
        self.home_tab.remove_css_class('active-tab')
        self.view_tab.remove_css_class('active-tab')
        if name == 'home':
            self.ribbon_stack.set_visible_child_name('home')
            self.home_tab.add_css_class('active-tab')
        else:
            self.ribbon_stack.set_visible_child_name('view')
            self.view_tab.add_css_class('active-tab')

    def _set_rulers_visible(self, visible):
        self.ruler_corner.set_visible(visible)
        self.hruler.set_visible(visible)
        self.vruler.set_visible(visible)
        self.canvas.rulers = visible

    def _toggle_rulers(self, active):
        self._set_rulers_visible(active)
        self.cb_ruler.set_active(active)

    def _toggle_grid(self, active):
        self.canvas.grid = active
        if self.cb_grid.get_active() != active:
            self.cb_grid.set_active(active)
        self.canvas.drawing.queue_draw()

    def _toggle_status(self, active):
        self.statusbar.set_visible(active)
        self.status_visible = active

    def _toggle_thumbnail(self):
        self.thumbnail_visible = not self.thumbnail_visible
        self.thumb_revealer.set_reveal_child(self.thumbnail_visible)
        self.thumb_btn.set_active(self.thumbnail_visible)
        self.thumb_area.queue_draw()

    def _toggle_fullscreen(self):
        if self.is_fullscreen():
            Gtk.Window.unfullscreen(self)
        else:
            Gtk.Window.fullscreen(self)

    def _on_fullscreen_changed(self, *args):
        self._is_fullscreen = self.is_fullscreen()

    def _draw_thumbnail(self, area, ctx, width, height):
        w, h = self.doc.width, self.doc.height
        if w <= 0 or h <= 0:
            return
        ctx.set_source_rgb(1, 1, 1); ctx.paint()
        scale = min((width - 4) / w, (height - 4) / h)
        x = (width - w * scale) / 2
        y = (height - h * scale) / 2
        ctx.save()
        ctx.translate(x, y); ctx.scale(scale, scale)
        ctx.set_source_surface(self.doc.surface, 0, 0)
        ctx.paint()
        ctx.restore()
        ctx.set_source_rgba(0.2, 0.2, 0.2, 0.6); ctx.rectangle(x, y, w * scale, h * scale); ctx.stroke()

    # ------------------------------------------------------------------
    # Printing / page setup
    def _print(self, preview=False):
        self._commit_current_text()
        self.canvas.commit_floating()
        op = Gtk.PrintOperation()
        op.set_use_full_page(False)
        op.set_unit(Gtk.Unit.INCH)
        op.set_show_progress(True)
        op.set_allow_async(True)
        page = Gtk.PageSetup()
        page.set_orientation(Gtk.PageOrientation.LANDSCAPE if self.page_settings['landscape'] else Gtk.PageOrientation.PORTRAIT)
        op.set_default_page_setup(page)
        op.connect('draw-page', self._draw_print_page)
        op.connect('begin-print', self._begin_print)
        try:
            if preview:
                res = op.run(Gtk.PrintOperationAction.PREVIEW, self)
            else:
                res = op.run(Gtk.PrintOperationAction.PRINT_DIALOG, self)
        except Exception as exc:
            MessageDialog(self, self.tr('paim 无法打印你的文档。', 'paim could not print the document.'),
                          str(exc), Gtk.MessageType.ERROR).present()

    def _begin_print(self, op, context):
        op.set_n_pages(1)

    def _draw_print_page(self, op, context, page_nr):
        ctx = context.get_cairo_context()
        page_w = context.get_width()
        page_h = context.get_height()
        scale = min(page_w / self.doc.width, page_h / self.doc.height) * self.page_settings['scale'] / 100.0
        w = self.doc.width * scale
        h = self.doc.height * scale
        x = (page_w - w) / 2 if self.page_settings['center'] else 0
        y = (page_h - h) / 2 if self.page_settings['center'] else 0
        ctx.save()
        ctx.rectangle(0, 0, page_w, page_h)
        ctx.clip()
        ctx.translate(x, y)
        ctx.scale(scale, scale)
        ctx.set_source_surface(self.doc.surface, 0, 0)
        ctx.paint()
        ctx.restore()

    def _print_preview(self):
        self._print(preview=True)

    def _page_setup(self):
        def apply(settings):
            self.page_settings.update(settings)
            MessageDialog(self, self.tr('页面设置已更新。', 'Page setup updated.')).present()
        PageSetupDialog(self, self.page_settings, apply).present()

    # ------------------------------------------------------------------
    # Misc commands
    def _set_wallpaper(self):
        if not self.doc.filename:
            MessageDialog(self, self.tr('在将它选为桌面背景前必须保存该文件。',
                                        'The file must be saved before setting it as the desktop background.')).present()
            return
        try:
            path = Path(GLib.get_user_data_dir()) / 'mspaint-linux' / 'wallpaper.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            self.doc.save(str(path), fmt='png')
            uri = path.as_uri()
            for key in ('picture-uri', 'picture-uri-dark'):
                subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', key, uri],
                               check=False, timeout=5)
            MessageDialog(self, self.tr('已将图片设置为桌面背景。', 'The picture was set as the desktop background.')).present()
        except Exception as exc:
            MessageDialog(self, self.tr('无法设置桌面背景。', 'Could not set the desktop background.'),
                          str(exc), Gtk.MessageType.ERROR).present()

    def _send_email(self):
        if not self.doc.filename:
            MessageDialog(self, self.tr('请先保存文件。', 'Please save the file first.')).present()
            return
        try:
            subprocess.Popen(['xdg-email', '--attach', self.doc.filename])
        except Exception as exc:
            MessageDialog(self, str(exc), Gtk.MessageType.ERROR).present()

    def _scanner_unavailable(self):
        MessageDialog(self, self.tr('未找到扫描仪或照相机，或该设备不受支持。',
                                    'No scanner or camera was found, or the device is not supported.'),
                      self.tr('paim 通过文件打开或粘贴来导入图像。',
                              'paim imports pictures from files or the clipboard.')).present()

    def _paint3d_unavailable(self):
        MessageDialog(self, self.tr('此功能已从 paim 中移除。', 'This feature is not part of paim.')).present()

    def _help(self):
        dlg = Gtk.Window(transient_for=self, modal=True, title=self.tr('paim 帮助', 'paim help'))
        dlg.set_default_size(560, 480)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(18); box.set_margin_end(18)
        title = Gtk.Label(label='paim')
        title.add_css_class('title-1'); title.set_xalign(0)
        box.append(title)
        text = self.tr(
            'paim 是一款在 Linux 上使用 GTK4 构建的轻量绘图应用。\n\n'
            '键盘快捷键:\n'
            '  Ctrl+N  新建\n  Ctrl+O  打开\n  Ctrl+S  保存\n  F12  另存为\n'
            '  Ctrl+Z  撤消\n  Ctrl+Y  重做\n  Ctrl+X/C/V  剪切/复制/粘贴\n'
            '  Ctrl+A  全选\n  Ctrl+W  调整大小和扭曲\n  Ctrl+E  属性\n'
            '  Ctrl+Shift+X  裁剪\n  Ctrl+Shift+I  反色\n  Ctrl+Shift+N  清除图像\n'
            '  Ctrl+PgUp/Ctrl+PgDn  放大/缩小\n  F11  全屏\n  F1  帮助\n'
            '  Delete  删除选定内容\n  Esc  取消选择或文本编辑\n\n'
            '主题：查看 → 主题，可跟随系统或手动选浅色/深色。\n'
            '快速访问：右键功能区命令即可添加到标题栏。',
            'paim is a lightweight drawing app for Linux built with GTK4.\n\n'
            'Keyboard shortcuts:\n'
            '  Ctrl+N  New\n  Ctrl+O  Open\n  Ctrl+S  Save\n  F12  Save as\n'
            '  Ctrl+Z  Undo\n  Ctrl+Y  Redo\n  Ctrl+X/C/V  Cut/Copy/Paste\n'
            '  Ctrl+A  Select all\n  Ctrl+W  Resize and skew\n  Ctrl+E  Properties\n'
            '  Ctrl+Shift+X  Crop\n  Ctrl+Shift+I  Invert colours\n  Ctrl+Shift+N  Clear image\n'
            '  Ctrl+PgUp/Ctrl+PgDn  Zoom in/out\n  F11  Full screen\n  F1  Help\n'
            '  Delete  Delete selection\n  Esc  Cancel selection or text editing\n\n'
            'Theme: View → Theme, follow the system or choose Light/Dark.\n'
            'Quick Access: right-click a ribbon command to pin it to the title bar.')
        lab = Gtk.Label(label=text)
        lab.set_wrap(True); lab.set_xalign(0); lab.set_selectable(True)
        box.append(lab)
        btn = Gtk.Button(label=self.tr('关闭', 'Close'))
        btn.connect('clicked', lambda *a: dlg.destroy())
        box.append(btn)
        dlg.set_child(box)
        dlg.present()

    def _about(self):
        AboutDialog(self).present()

    def _update_action_sensitivity(self):
        sel = self.doc.selection is not None
        for a in ('cut', 'copy', 'delete', 'invert-selection', 'crop'):
            act = self.lookup_action(a)
            if act:
                act.set_enabled(sel)
        self._update_quick_access()

    def _build_drop_hint(self):
        self.drop_hint = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.drop_hint.add_css_class('drop-hint')
        self.drop_hint.set_halign(Gtk.Align.FILL)
        self.drop_hint.set_valign(Gtk.Align.FILL)
        self.drop_hint.set_hexpand(True)
        self.drop_hint.set_vexpand(True)
        self.drop_hint.set_can_target(False)
        icon = Gtk.Image.new_from_icon_name('document-open-symbolic')
        icon.set_pixel_size(56)
        icon.set_halign(Gtk.Align.CENTER)
        self.drop_hint.append(icon)
        label = Gtk.Label(label=self.tr('松开以打开图片', 'Drop to open the image'))
        label.set_halign(Gtk.Align.CENTER)
        self.drop_hint.append(label)
        self.overlay.add_overlay(self.drop_hint)
        self.drop_hint.set_visible(False)

    def _setup_file_drop(self):
        target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        target.connect('enter', self._on_drop_enter)
        target.connect('motion', self._on_drop_motion)
        target.connect('leave', self._on_drop_leave)
        target.connect('drop', self._on_drop)
        self.add_controller(target)
        self._file_drop_target = target
        # Also attach to the content overlay so drops over the canvas and
        # any child widget are reliably captured on all compositors.
        target2 = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        target2.connect('enter', self._on_drop_enter)
        target2.connect('motion', self._on_drop_motion)
        target2.connect('leave', self._on_drop_leave)
        target2.connect('drop', self._on_drop)
        self.overlay.add_controller(target2)
        self._file_drop_target_overlay = target2

    def _show_drop_hint(self, visible):
        if hasattr(self, 'drop_hint'):
            self.drop_hint.set_visible(visible)

    def _on_drop_enter(self, target, x, y):
        self._show_drop_hint(True)
        return Gdk.DragAction.COPY

    def _on_drop_motion(self, target, x, y):
        self._show_drop_hint(True)
        return Gdk.DragAction.COPY

    def _on_drop_leave(self, target):
        self._show_drop_hint(False)

    def _on_drop(self, target, value, x, y):
        self._show_drop_hint(False)
        try:
            files = value.get_files()
        except Exception:
            files = []
        return self._open_dropped_files(files)

    def _open_dropped_files(self, files):
        candidates = []
        for f in files or []:
            path = f.get_path() if f else None
            if path and os.path.isfile(path):
                candidates.append(path)
        if not candidates:
            MessageDialog(self, self.tr('没有可打开的文件。', 'No file to open.')).present()
            return False
        # Prefer known image extensions, but let Pillow decide for anything
        # that looks like an image.
        exts = ('.png', '.jpg', '.jpeg', '.bmp', '.dib', '.gif', '.tif',
                '.tiff', '.webp', '.ico', '.ppm', '.pgm', '.tga')
        candidates.sort(key=lambda p: 0 if p.lower().endswith(exts) else 1)
        path = None
        last_error = None
        from PIL import Image
        for candidate in candidates:
            try:
                with Image.open(candidate) as im:
                    im.verify()
                path = candidate
                break
            except Exception as exc:
                last_error = exc
        if path is None:
            MessageDialog(self, self.tr('paim 无法打开该文件。', 'paim cannot open this file.'),
                          str(last_error or ''), Gtk.MessageType.ERROR).present()
            return False
        def go():
            self.load_path(path)
        self._confirm_save(go)
        return True

    def _apply_runtime_theme(self, dark, *, force=False):
        if self._applying_theme:
            return
        if not force and dark == self.dark_mode:
            return
        self._applying_theme = True
        try:
            apply_native_theme(dark)
            self.dark_mode = dark
            icon_module.set_dark_theme(dark)
            install_css(dark)
            self.remove_css_class('paint-light')
            self.remove_css_class('paint-dark')
            self.add_css_class('paint-dark' if dark else 'paint-light')
            self.canvas.dark = dark
            self.canvas.drawing.queue_draw()
            self.queue_draw()
            if hasattr(self, 'hruler'):
                self.hruler.queue_draw()
                self.vruler.queue_draw()
            if hasattr(self, 'thumb_area'):
                self.thumb_area.queue_draw()
            if hasattr(self, 'theme_mode_label'):
                self._update_theme_menu()
        finally:
            self._applying_theme = False

    def _on_system_theme_changed(self, *args):
        if self._applying_theme or self.theme_mode != 'auto':
            return
        dark = detect_dark_theme()
        self._apply_runtime_theme(dark)

    def _set_theme_mode(self, mode):
        if mode not in ('auto', 'light', 'dark'):
            return
        self.theme_mode = mode
        self._save_preferences()
        self._apply_runtime_theme(self._resolve_dark(), force=True)
        self._update_theme_menu()

    def _update_theme_menu(self):
        if not hasattr(self, 'theme_mode_label'):
            return
        labels = {
            'auto': self.tr('主题：跟随系统', 'Theme: System'),
            'light': self.tr('主题：浅色', 'Theme: Light'),
            'dark': self.tr('主题：深色', 'Theme: Dark'),
        }
        self.theme_mode_label.set_text(labels.get(self.theme_mode, labels['auto']))
        self._updating_theme_menu = True
        try:
            for mode, btn in getattr(self, 'theme_mode_buttons', {}).items():
                btn.set_active(mode == self.theme_mode)
        finally:
            self._updating_theme_menu = False

    def _on_theme_mode_toggled(self, btn, mode):
        if self._updating_theme_menu:
            return
        if btn.get_active():
            self._set_theme_mode(mode)

    def _on_window_key(self, controller, keyval, keycode, state):
        if self.canvas._text_editor is not None:
            return False
        focus = self.get_focus()
        if isinstance(focus, (Gtk.TextView, Gtk.Entry, Gtk.SpinButton)):
            return False
        return bool(self.canvas._on_key(controller, keyval, keycode, state))

    def _on_close_request(self, *args):
        if self._force_close or not self.doc.dirty:
            return False
        def go():
            self._force_close = True
            self.close()
        self._confirm_save(go)
        return True

    def _on_canvas_pointer(self, point):
        pass


# ----------------------------------------------------------------------
# Widgets used by the ribbon
class ShapeIcon(Gtk.DrawingArea):
    def __init__(self, shape, size=24):
        super().__init__()
        self.shape_name = shape
        self.set_content_width(size); self.set_content_height(size)
        self.set_draw_func(self._draw)

    def _draw(self, area, ctx, width, height):
        margin = 2.5
        w = width - 2 * margin; h = height - 2 * margin
        ctx.set_source_rgb(*icon_module.BLUE)
        ctx.set_line_width(1.3)
        if self.shape_name == 'line':
            ctx.move_to(margin, margin + h)
            ctx.line_to(margin + w, margin)
        elif self.shape_name == 'curve':
            ctx.move_to(margin, margin + h)
            ctx.curve_to(margin + w * 0.25, margin - h * 0.25,
                         margin + w * 0.75, margin + h * 1.25,
                         margin + w, margin)
        else:
            build_shape_path(ctx, self.shape_name, margin, margin, w, h)
        ctx.stroke()


class BrushIcon(Gtk.DrawingArea):
    def __init__(self, brush, size=36):
        super().__init__()
        self.brush_name = brush
        self.set_content_width(size); self.set_content_height(size)
        self.set_draw_func(self._draw)

    def _draw(self, area, ctx, width, height):
        ctx.save()
        # draw strokes in a warm orange, similar to the icon set
        ctx.set_line_width(4.5)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(0.86, 0.47, 0.16)
        if self.brush_name == 'calligraphy1':
            ctx.move_to(6, 26); ctx.line_to(29, 9)
        elif self.brush_name == 'calligraphy2':
            ctx.move_to(6, 8); ctx.line_to(29, 26)
        elif self.brush_name == 'airbrush':
            for i in range(30):
                import random
                r = random.Random(i)
                ctx.arc(9 + r.random() * 21, 9 + r.random() * 19, 0.8, 0, 2 * 3.14159)
                ctx.fill()
        elif self.brush_name == 'crayon':
            for i in range(5):
                ctx.set_line_width(1.3)
                ctx.move_to(7 + i, 26 - i); ctx.line_to(17 + i, 17 - i); ctx.stroke()
        elif self.brush_name == 'marker':
            ctx.set_line_width(8); ctx.set_source_rgba(0.8, 0.4, 0.12, 0.6)
            ctx.move_to(8, 24); ctx.line_to(28, 12); ctx.stroke()
        elif self.brush_name == 'watercolor':
            ctx.set_source_rgba(0.8, 0.4, 0.12, 0.28)
            for i in range(5):
                ctx.arc(12 + i * 3, 20 - i * 2, 6, 0, 2 * 3.14159); ctx.fill()
        else:
            ctx.move_to(8, 26); ctx.line_to(28, 10)
        if self.brush_name not in ('airbrush', 'watercolor', 'marker'):
            ctx.stroke()
        # brush handle
        ctx.set_source_rgb(*(0.76, 0.70, 0.62) if self.get_style_context().get_color().red > 0.5 else (0.28, 0.18, 0.1))
        ctx.set_line_width(3.5)
        ctx.move_to(25, 8); ctx.line_to(30, 13); ctx.stroke()
        ctx.restore()


class RulerWidget(Gtk.DrawingArea):
    def __init__(self, canvas, orientation):
        super().__init__()
        self.canvas = canvas
        self.orientation = orientation
        self.add_css_class('ruler')
        self.set_draw_func(self._draw)

    def _draw(self, area, ctx, width, height):
        horizontal = self.orientation == Gtk.Orientation.HORIZONTAL
        dark = getattr(self.canvas, 'dark', False)
        if dark:
            ctx.set_source_rgb(0.16, 0.17, 0.20); ctx.paint()
            ctx.set_source_rgb(0.62, 0.64, 0.68)
        else:
            ctx.set_source_rgb(0.94, 0.94, 0.94); ctx.paint()
            ctx.set_source_rgb(0.55, 0.55, 0.55)
        ctx.set_line_width(1)
        # The canvas is inside a scrolled window.  Query its adjustments.
        parent = self.canvas.get_parent()
        scrolled = parent.get_parent() if parent else None
        adj = None
        if isinstance(parent, Gtk.Viewport):
            adj = parent.get_hadjustment() if horizontal else parent.get_vadjustment()
        if adj is None:
            while scrolled is not None and not isinstance(scrolled, Gtk.ScrolledWindow):
                scrolled = scrolled.get_parent()
            if isinstance(scrolled, Gtk.ScrolledWindow):
                adj = scrolled.get_hadjustment() if horizontal else scrolled.get_vadjustment()
        offset = adj.get_value() if adj else 0
        z = self.canvas.zoom
        pad = 12
        # major ticks every 50 image pixels, minor every 10
        start_img = max(0, int((offset - (pad if horizontal else pad)) / z) - 50)
        end_img = start_img + int((width if horizontal else height) / z) + 100
        step = 10
        if z < 0.5:
            step = 50
        elif z < 1:
            step = 20
        for val in range(max(0, (start_img // step) * step), end_img + step, step):
            pos = pad + val * z - offset
            if pos < -20 or pos > (width if horizontal else height) + 20:
                continue
            major = val % (step * 5) == 0
            tick = 5 if major else 2
            if horizontal:
                ctx.move_to(pos + 0.5, height); ctx.line_to(pos + 0.5, height - tick)
            else:
                ctx.move_to(width, pos + 0.5); ctx.line_to(width - tick, pos + 0.5)
            ctx.stroke()
            if major:
                ctx.save()
                ctx.set_font_size(8)
                ctx.set_source_rgb(*(0.72, 0.74, 0.78) if dark else (0.35, 0.35, 0.35))
                if horizontal:
                    ctx.move_to(pos + 2, 9); ctx.show_text(str(val))
                else:
                    ctx.translate(8, pos + 2); ctx.rotate(-math.pi / 2)
                    ctx.show_text(str(val))
                ctx.restore()
        if horizontal:
            ctx.move_to(0, height - 0.5); ctx.line_to(width, height - 0.5); ctx.stroke()
        else:
            ctx.move_to(width - 0.5, 0); ctx.line_to(width - 0.5, height); ctx.stroke()


def _copy_surface_ref(surface):
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, surface.get_width(), surface.get_height())
    ctx = cairo.Context(out)
    ctx.set_source_surface(surface, 0, 0)
    ctx.paint()
    return out


def scale_surface(surface, w, h):
    w = max(1, int(round(w))); h = max(1, int(round(h)))
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(out)
    ctx.scale(w / surface.get_width(), h / surface.get_height())
    pat = cairo.SurfacePattern(surface)
    pat.set_filter(cairo.FILTER_GOOD)
    ctx.set_source(pat)
    ctx.paint()
    return out


def main(argv=None):
    app = PaintApplication()
    return app.run(argv)
