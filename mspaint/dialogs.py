# SPDX-License-Identifier: GPL-3.0-or-later
"""Dialogs used by paim."""
from __future__ import annotations

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gtk

from .i18n import tr


def label(text, xalign=0.0, css=None, wrap=False):
    w = Gtk.Label(label=text)
    w.set_xalign(xalign)
    if css:
        w.add_css_class(css)
    if wrap:
        w.set_wrap(True)
    return w


class BaseDialog(Gtk.Dialog):
    def __init__(self, parent, title, width=360):
        super().__init__(transient_for=parent, modal=True, use_header_bar=True)
        self.set_title(title)
        self.set_default_size(width, -1)
        self.set_resizable(False)
        self.add_button(tr('取消', 'Cancel'), Gtk.ResponseType.CANCEL)
        self.add_button(tr('确定', 'OK'), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.connect('response', self._on_response)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.content.set_margin_top(14)
        self.content.set_margin_bottom(14)
        self.content.set_margin_start(16)
        self.content.set_margin_end(16)
        self.get_content_area().append(self.content)

    def _on_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            self.apply()
        self.destroy()

    def apply(self):
        pass


class ResizeDialog(BaseDialog):
    def __init__(self, parent, width, height, callback):
        super().__init__(parent, tr('调整大小和扭曲', 'Resize and skew'), 400)
        self.src_w, self.src_h = width, height
        self.callback = callback
        self.mode = 'percent'
        self.keep_ratio = True

        group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        group.append(label(tr('调整大小', 'Resize'), css='section-title'))
        group.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        group.append(label(tr('倾斜', 'Skew'), css='section-title'))
        self.content.append(group)

        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        self.content.append(grid)
        self.unit_pct = Gtk.CheckButton(label=tr('百分比', 'Percentage'))
        self.unit_px = Gtk.CheckButton(label=tr('像素', 'Pixels'))
        self.unit_px.set_group(self.unit_pct)
        self.unit_pct.set_active(True)
        grid.attach(label(tr('单位:', 'Units:')), 0, 0, 2, 1)
        grid.attach(self.unit_pct, 0, 1, 1, 1)
        grid.attach(self.unit_px, 1, 1, 1, 1)
        grid.attach(label(tr('水平:', 'Horizontal:')), 0, 2, 1, 1)
        self.hspin = Gtk.SpinButton.new_with_range(1, 100000, 1)
        self.hspin.set_value(100)
        grid.attach(self.hspin, 1, 2, 1, 1)
        grid.attach(label(tr('垂直:', 'Vertical:')), 0, 3, 1, 1)
        self.vspin = Gtk.SpinButton.new_with_range(1, 100000, 1)
        self.vspin.set_value(100)
        grid.attach(self.vspin, 1, 3, 1, 1)
        self.ratio = Gtk.CheckButton(label=tr('保持纵横比', 'Maintain aspect ratio'))
        self.ratio.set_active(True)
        grid.attach(self.ratio, 0, 4, 2, 1)

        self.content.append(Gtk.Separator())
        skew = Gtk.Grid(column_spacing=10, row_spacing=8)
        self.content.append(skew)
        skew.attach(label(tr('水平:', 'Horizontal:')), 0, 0, 1, 1)
        self.skew_h = Gtk.SpinButton.new_with_range(-89, 89, 1)
        self.skew_h.set_value(0)
        skew.attach(self.skew_h, 1, 0, 1, 1)
        skew.attach(label(tr('度', 'degrees')), 2, 0, 1, 1)
        skew.attach(label(tr('垂直:', 'Vertical:')), 0, 1, 1, 1)
        self.skew_v = Gtk.SpinButton.new_with_range(-89, 89, 1)
        self.skew_v.set_value(0)
        skew.attach(self.skew_v, 1, 1, 1, 1)
        skew.attach(label(tr('度', 'degrees')), 2, 1, 1, 1)

        self.unit_pct.connect('toggled', self._mode_changed)
        self.unit_px.connect('toggled', self._mode_changed)
        self.hspin.connect('value-changed', self._h_changed)
        self.vspin.connect('value-changed', self._v_changed)
        self.ratio.connect('toggled', self._ratio_changed, None)
        self._updating = False

    def _mode_changed(self, btn):
        if self._updating:
            return
        self._updating = True
        if self.unit_px.get_active():
            self.mode = 'pixel'
            self.hspin.set_range(1, 100000)
            self.vspin.set_range(1, 100000)
            self.hspin.set_value(self.src_w)
            self.vspin.set_value(self.src_h)
        else:
            self.mode = 'percent'
            self.hspin.set_range(1, 10000)
            self.vspin.set_range(1, 10000)
            self.hspin.set_value(100)
            self.vspin.set_value(100)
        self._updating = False

    def _h_changed(self, spin):
        if self._updating or not self.ratio.get_active():
            return
        self._updating = True
        if self.mode == 'percent':
            self.vspin.set_value(spin.get_value())
        else:
            self.vspin.set_value(max(1, round(spin.get_value() * self.src_h / self.src_w)))
        self._updating = False

    def _v_changed(self, spin):
        if self._updating or not self.ratio.get_active():
            return
        self._updating = True
        if self.mode == 'percent':
            self.hspin.set_value(spin.get_value())
        else:
            self.hspin.set_value(max(1, round(spin.get_value() * self.src_w / self.src_h)))
        self._updating = False

    def _ratio_changed(self, *a):
        pass

    def apply(self):
        if self.mode == 'percent':
            w = self.src_w * self.hspin.get_value() / 100.0
            h = self.src_h * self.vspin.get_value() / 100.0
        else:
            w = self.hspin.get_value()
            h = self.vspin.get_value()
        self.callback(int(round(w)), int(round(h)), self.skew_h.get_value(),
                      self.skew_v.get_value())


class AttributesDialog(BaseDialog):
    def __init__(self, parent, doc, callback):
        super().__init__(parent, tr('映像属性', 'Image properties'), 360)
        self.doc = doc
        self.callback = callback
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        self.content.append(grid)
        grid.attach(label(tr('宽度:', 'Width:')), 0, 0, 1, 1)
        self.wspin = Gtk.SpinButton.new_with_range(1, 100000, 1)
        self.wspin.set_value(doc.width)
        grid.attach(self.wspin, 1, 0, 1, 1)
        grid.attach(label(tr('高度:', 'Height:')), 0, 1, 1, 1)
        self.hspin = Gtk.SpinButton.new_with_range(1, 100000, 1)
        self.hspin.set_value(doc.height)
        grid.attach(self.hspin, 1, 1, 1, 1)
        grid.attach(label(tr('单位:', 'Units:')), 0, 2, 1, 1)
        units = [tr('像素', 'Pixels'), tr('英寸', 'Inches'), tr('厘米', 'Centimeters')]
        self.units = Gtk.DropDown.new_from_strings(units)
        grid.attach(self.units, 1, 2, 1, 1)
        grid.attach(label(tr('颜色:', 'Colors:')), 0, 3, 1, 1)
        self.color = Gtk.CheckButton(label=tr('彩色', 'Color'))
        self.bw = Gtk.CheckButton(label=tr('黑白', 'Black and white'))
        self.bw.set_group(self.color)
        self.color.set_active(True)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.append(self.color); box.append(self.bw)
        grid.attach(box, 1, 3, 1, 1)
        self.transparent = Gtk.CheckButton(label=tr('透明', 'Transparent'))
        self.transparent.set_tooltip_text(tr('透明背景（保留 Alpha 通道）',
                                             'Transparent background (preserve the alpha channel)'))
        self.transparent.set_active(bool(getattr(doc, 'transparent', False)))
        grid.attach(self.transparent, 0, 4, 2, 1)
        self.content.append(label(tr('透明背景会保留 PNG、GIF 和 WebP 文件的透明通道。',
                                     'A transparent background is preserved in PNG, GIF and WebP files.'),
                                  css='hint', wrap=True))
        self.content.append(label(tr('注意：将图像转换为黑白后无法撤销。',
                                     'Note: converting the image to black and white cannot be undone.'),
                                  css='hint'))

    def apply(self):
        factor = 1.0
        if self.units.get_selected() == 1:
            factor = 96.0
        elif self.units.get_selected() == 2:
            factor = 96.0 / 2.54
        w = int(round(self.wspin.get_value() * factor))
        h = int(round(self.hspin.get_value() * factor))
        self.callback(w, h, not self.bw.get_active(), self.transparent.get_active())


class ColorDialog(BaseDialog):
    def __init__(self, parent, initial, callback, title=None):
        super().__init__(parent, title or tr('编辑颜色', 'Edit colors'), 440)
        self.callback = callback
        self.chooser = Gtk.ColorChooserWidget()
        self.chooser.set_use_alpha(False)
        self.chooser.set_rgba(Gdk.RGBA(initial[0] / 255, initial[1] / 255,
                                       initial[2] / 255, 1))
        self.content.append(self.chooser)
        grid = Gtk.Grid(column_spacing=3, row_spacing=3)
        from .raster import DEFAULT_PALETTE
        for i, color in enumerate(DEFAULT_PALETTE):
            b = Gtk.Button()
            b.set_size_request(20, 20)
            b.add_css_class('palette-swatch')
            p = Gtk.CssProvider()
            p.load_from_data(f'button {{ background: {color}; min-width: 18px; min-height: 18px; }}'.encode())
            b.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            b.connect('clicked', self._palette_click, color)
            grid.attach(b, i % 10, i // 10, 1, 1)
        self.content.append(grid)
        self.content.append(label(tr('在右侧颜色选择器中选择颜色，然后单击“确定”。',
                                     'Choose a color in the picker on the right, then click OK.'),
                                  css='hint', wrap=True))

    def _palette_click(self, btn, color):
        from .document import hex_to_rgb
        rgb = hex_to_rgb(color)
        self.chooser.set_rgba(Gdk.RGBA(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, 1))

    def apply(self):
        c = self.chooser.get_rgba()
        self.callback((int(round(c.red * 255)), int(round(c.green * 255)),
                       int(round(c.blue * 255))))


class SaveOptionsDialog(BaseDialog):
    def __init__(self, parent, fmt, callback):
        super().__init__(parent, tr('保存选项', 'Save options'), 340)
        self.fmt = fmt
        self.callback = callback
        self.content.append(label(tr('选择保存格式：', 'Choose a format:'), css='section-title'))
        formats = [tr('PNG 图片', 'PNG picture'), tr('JPEG 图片', 'JPEG picture'),
                   tr('BMP 图片', 'BMP picture'), tr('GIF 图片', 'GIF picture')]
        self.formats = Gtk.DropDown.new_from_strings(formats)
        mapping = {'png': 0, 'jpg': 1, 'jpeg': 1, 'bmp': 2, 'dib': 2, 'gif': 3}
        self.formats.set_selected(mapping.get(fmt, 0))
        self.content.append(self.formats)
        self.depth_label = label(tr('BMP 位深度：', 'BMP bit depth:'))
        depths = [tr('单色位图 (1 位)', 'Monochrome bitmap (1-bit)'),
                  tr('16 色位图 (4 位)', '16-color bitmap (4-bit)'),
                  tr('256 色位图 (8 位)', '256-color bitmap (8-bit)'),
                  tr('24 位位图', '24-bit bitmap')]
        self.depth = Gtk.DropDown.new_from_strings(depths)
        self.depth.set_selected(3)
        self.content.append(self.depth_label)
        self.content.append(self.depth)
        self.formats.connect('notify::selected', self._update_depth)
        self._update_depth()

    def _update_depth(self, *a):
        enabled = self.formats.get_selected() == 2
        self.depth_label.set_sensitive(enabled)
        self.depth.set_sensitive(enabled)

    def apply(self):
        fmt = ['png', 'jpg', 'bmp', 'gif'][self.formats.get_selected()]
        bits = [1, 4, 8, 24][self.depth.get_selected()]
        self.callback(fmt, bits)


class PageSetupDialog(BaseDialog):
    def __init__(self, parent, settings, callback):
        super().__init__(parent, tr('页面设置', 'Page setup'), 380)
        self.settings = settings
        self.callback = callback
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        self.content.append(grid)
        grid.attach(label(tr('方向:', 'Orientation:')), 0, 0, 1, 1)
        self.portrait = Gtk.CheckButton(label=tr('纵向', 'Portrait'))
        self.landscape = Gtk.CheckButton(label=tr('横向', 'Landscape'))
        self.landscape.set_group(self.portrait)
        self.portrait.set_active(not settings.get('landscape'))
        self.landscape.set_active(settings.get('landscape', False))
        box = Gtk.Box(spacing=10); box.append(self.portrait); box.append(self.landscape)
        grid.attach(box, 1, 0, 1, 1)
        grid.attach(label(tr('缩放:', 'Scale:')), 0, 1, 1, 1)
        self.scale = Gtk.SpinButton.new_with_range(10, 400, 1)
        self.scale.set_value(settings.get('scale', 100))
        grid.attach(self.scale, 1, 1, 1, 1)
        grid.attach(label('%'), 2, 1, 1, 1)
        grid.attach(label(tr('左边距:', 'Left margin:')), 0, 2, 1, 1)
        self.left = Gtk.SpinButton.new_with_range(0, 100, 0.1)
        self.left.set_value(settings.get('left', 0.5))
        grid.attach(self.left, 1, 2, 1, 1)
        grid.attach(label(tr('英寸', 'inches')), 2, 2, 1, 1)
        grid.attach(label(tr('上边距:', 'Top margin:')), 0, 3, 1, 1)
        self.top = Gtk.SpinButton.new_with_range(0, 100, 0.1)
        self.top.set_value(settings.get('top', 0.5))
        grid.attach(self.top, 1, 3, 1, 1)
        grid.attach(label(tr('英寸', 'inches')), 2, 3, 1, 1)
        self.center = Gtk.CheckButton(label=tr('居中', 'Center'))
        self.center.set_active(settings.get('center', True))
        self.content.append(self.center)

    def apply(self):
        self.callback({
            'landscape': self.landscape.get_active(),
            'scale': self.scale.get_value(),
            'left': self.left.get_value(),
            'top': self.top.get_value(),
            'center': self.center.get_active(),
        })


class AboutDialog(Gtk.AboutDialog):
    def __init__(self, parent):
        super().__init__(transient_for=parent, modal=True)
        self.set_program_name('paim')
        self.set_version('1.0.0')
        comments = tr(
            'paim (paintImproved)\n一款轻快的 Linux GTK4 绘图应用\n'
            '支持绘图工具、选区、文本、图像调整和多种文件格式。',
            'paim (paintImproved)\nA lightweight GTK4 drawing application for Linux.\n'
            'Tools, selections, text, image adjustments and many file formats.')
        self.set_comments(comments)
        self.set_website('https://github.com/myLiLingyun/paim')
        self.set_license_type(Gtk.License.GPL_3_0)
        self.set_copyright('Copyright (C) 2026 paim contributors')
        self.set_logo_icon_name('applications-graphics')


class MessageDialog(Gtk.MessageDialog):
    def __init__(self, parent, text, secondary=None, kind=Gtk.MessageType.INFO,
                 buttons=Gtk.ButtonsType.OK, callback=None):
        super().__init__(transient_for=parent, modal=True, message_type=kind,
                         buttons=buttons, text=text)
        if secondary:
            self.set_property('secondary-text', secondary)
        if callback:
            self.connect('response', lambda d, r: (callback(r), d.destroy()))
        else:
            self.connect('response', lambda d, r: d.destroy())
