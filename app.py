#!/usr/bin/env python3
"""Doc Alchemist — Markdown <-> DOCX / PDF converter for Linux Mint."""
import subprocess
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

import converter
import updates

APP_ID = "com.hassan.docalchemist"
HERE = Path(__file__).resolve().parent

CSS = b"""
.drop-zone {
    border: 2px dashed alpha(@theme_fg_color, 0.35);
    border-radius: 14px;
    background: alpha(@theme_fg_color, 0.04);
    padding: 24px;
}
.drop-zone.active {
    border-color: @theme_selected_bg_color;
    background: alpha(@theme_selected_bg_color, 0.12);
}
.drop-title { font-size: 15px; font-weight: 600; }
.drop-hint  { opacity: 0.65; }
.file-name  { font-size: 14px; font-weight: 700; }
.result-ok  { color: #2e7d32; font-weight: 600; }
.result-err { color: #c62828; }
.result-warn { color: #e65100; font-weight: 600; }
.note       { opacity: 0.7; font-size: 11px; }
.big-btn    { padding: 8px 26px; font-size: 14px; }
.credit     { opacity: 0.55; font-size: 11px; }
"""

FORMAT_ICONS = {"md": "text-x-generic", "docx": "x-office-document",
                "pdf": "application-pdf"}


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Doc Alchemist")
        self.set_default_size(460, 520)
        self.set_resizable(False)
        self.input_file = None
        self.busy = False

        header = Gtk.HeaderBar(title="Doc Alchemist",
                               subtitle="Markdown ⇆ Word ⇆ PDF")
        header.set_show_close_button(True)
        upd_btn = Gtk.Button.new_from_icon_name(
            "software-update-available-symbolic", Gtk.IconSize.BUTTON)
        upd_btn.set_tooltip_text("Check for updates")
        upd_btn.connect("clicked", self.on_check_updates)
        header.pack_end(upd_btn)
        self.set_titlebar(header)

        style = Gtk.CssProvider()
        style.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), style,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                        margin=24)
        self.add(outer)

        # --- drop zone -----------------------------------------------------
        self.drop_zone = Gtk.EventBox()
        self.drop_zone.get_style_context().add_class("drop-zone")
        zone_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        zone_box.set_valign(Gtk.Align.CENTER)
        self.drop_icon = Gtk.Image.new_from_icon_name(
            "document-send-symbolic", Gtk.IconSize.DIALOG)
        self.drop_icon.set_pixel_size(56)
        self.drop_title = Gtk.Label(label="Drop a file here")
        self.drop_title.get_style_context().add_class("drop-title")
        self.drop_title.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.drop_title.set_max_width_chars(38)
        self.drop_hint = Gtk.Label(label="or click to browse — .md, .docx, .pdf")
        self.drop_hint.get_style_context().add_class("drop-hint")
        zone_box.pack_start(self.drop_icon, False, False, 0)
        zone_box.pack_start(self.drop_title, False, False, 0)
        zone_box.pack_start(self.drop_hint, False, False, 0)
        self.drop_zone.add(zone_box)
        self.drop_zone.set_size_request(-1, 180)
        self.drop_zone.connect("button-press-event", self.on_browse)
        outer.pack_start(self.drop_zone, False, False, 0)

        targets = [Gtk.TargetEntry.new("text/uri-list", 0, 0)]
        self.drop_zone.drag_dest_set(Gtk.DestDefaults.ALL, targets,
                                     Gdk.DragAction.COPY)
        self.drop_zone.connect("drag-data-received", self.on_drop)
        self.drop_zone.connect("drag-motion", self.on_drag_motion)
        self.drop_zone.connect("drag-leave", self.on_drag_leave)

        # --- options -------------------------------------------------------
        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_halign(Gtk.Align.CENTER)
        outer.pack_start(grid, False, False, 0)

        lbl_to = Gtk.Label(label="Convert to")
        lbl_to.set_xalign(1)
        self.format_box = Gtk.Box(spacing=6)
        self.format_buttons = []
        grid.attach(lbl_to, 0, 0, 1, 1)
        grid.attach(self.format_box, 1, 0, 1, 1)

        self.lbl_theme = Gtk.Label(label="Theme")
        self.lbl_theme.set_xalign(1)
        self.theme_combo = Gtk.ComboBoxText()
        for key, label in converter.THEMES.items():
            self.theme_combo.append(key, label)
        self.theme_combo.set_active(0)
        grid.attach(self.lbl_theme, 0, 1, 1, 1)
        grid.attach(self.theme_combo, 1, 1, 1, 1)

        # --- convert button ------------------------------------------------
        btn_row = Gtk.Box(spacing=10)
        btn_row.set_halign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.convert_btn = Gtk.Button(label="Convert")
        self.convert_btn.get_style_context().add_class("suggested-action")
        self.convert_btn.get_style_context().add_class("big-btn")
        self.convert_btn.set_sensitive(False)
        self.convert_btn.connect("clicked", self.on_convert)
        btn_row.pack_start(self.convert_btn, False, False, 0)
        btn_row.pack_start(self.spinner, False, False, 0)
        outer.pack_start(btn_row, False, False, 0)

        # --- result --------------------------------------------------------
        self.result_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                  spacing=8)
        self.result_label = Gtk.Label()
        self.result_label.set_line_wrap(True)
        self.result_label.set_max_width_chars(48)
        self.result_label.set_justify(Gtk.Justification.CENTER)
        self.note_label = Gtk.Label()
        self.note_label.get_style_context().add_class("note")
        self.note_label.set_line_wrap(True)
        self.note_label.set_max_width_chars(52)
        action_row = Gtk.Box(spacing=8)
        action_row.set_halign(Gtk.Align.CENTER)
        self.open_btn = Gtk.Button(label="Open file")
        self.open_btn.connect("clicked", self.on_open_file)
        self.folder_btn = Gtk.Button(label="Show in folder")
        self.folder_btn.connect("clicked", self.on_open_folder)
        action_row.pack_start(self.open_btn, False, False, 0)
        action_row.pack_start(self.folder_btn, False, False, 0)
        self.result_box.pack_start(self.result_label, False, False, 0)
        self.result_box.pack_start(self.note_label, False, False, 0)
        self.result_box.pack_start(action_row, False, False, 0)
        outer.pack_start(self.result_box, False, False, 0)

        # --- credits ---------------------------------------------------------
        credit = Gtk.Label(label="Made with ❤ by Hassan Ali")
        credit.get_style_context().add_class("credit")
        credit.set_valign(Gtk.Align.END)
        outer.pack_end(credit, True, False, 0)

        self.show_all()
        self.result_box.hide()
        self.spinner.hide()
        self._set_formats(None)

    # --- file selection ----------------------------------------------------
    def on_browse(self, *_):
        if self.busy:
            return
        dlg = Gtk.FileChooserDialog(title="Choose a file", parent=self,
                                    action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL,
                        "Open", Gtk.ResponseType.OK)
        flt = Gtk.FileFilter()
        flt.set_name("Documents (md, docx, pdf)")
        for pat in ("*.md", "*.markdown", "*.txt", "*.docx", "*.pdf"):
            flt.add_pattern(pat)
        dlg.add_filter(flt)
        if dlg.run() == Gtk.ResponseType.OK:
            self.set_input(dlg.get_filename())
        dlg.destroy()

    def on_drag_motion(self, widget, *_):
        widget.get_style_context().add_class("active")
        return True

    def on_drag_leave(self, widget, *_):
        widget.get_style_context().remove_class("active")

    def on_drop(self, widget, ctx, x, y, data, info, time):
        widget.get_style_context().remove_class("active")
        uris = data.get_uris()
        if uris:
            path = urllib.parse.unquote(
                urllib.parse.urlparse(uris[0]).path)
            self.set_input(path)
        ctx.finish(True, False, time)

    def set_input(self, path):
        kind = converter.input_kind(path)
        if kind is None:
            self._error("That file type isn't supported.\n"
                        "Choose a .md, .docx or .pdf file.")
            return
        self.input_file = Path(path)
        self.drop_icon.set_from_icon_name(
            FORMAT_ICONS.get(kind, "text-x-generic"), Gtk.IconSize.DIALOG)
        self.drop_icon.set_pixel_size(56)
        self.drop_title.set_label(self.input_file.name)
        self.drop_title.get_style_context().add_class("file-name")
        self.drop_hint.set_label("Click to choose a different file")
        self.result_box.hide()
        self._set_formats(kind)
        self.convert_btn.set_sensitive(True)

    # --- format / theme ----------------------------------------------------
    def _set_formats(self, kind):
        for b in self.format_buttons:
            b.destroy()
        self.format_buttons = []
        options = converter.OUTPUTS_FOR.get(kind, [("docx", "Word (.docx)"),
                                                   ("pdf", "PDF (.pdf)")])
        group = None
        for fmt, label in options:
            btn = Gtk.RadioButton.new_with_label_from_widget(group, label)
            group = group or btn
            btn.fmt = fmt
            btn.set_sensitive(kind is not None)
            btn.connect("toggled", self._update_theme_visibility)
            self.format_box.pack_start(btn, False, False, 0)
            self.format_buttons.append(btn)
        self.format_box.show_all()
        self._update_theme_visibility()

    def _selected_format(self):
        for b in self.format_buttons:
            if b.get_active():
                return b.fmt
        return None

    def _update_theme_visibility(self, *_):
        themed = self._selected_format() in ("docx", "pdf")
        self.theme_combo.set_sensitive(themed)
        self.lbl_theme.set_sensitive(themed)

    # --- conversion ---------------------------------------------------------
    def on_convert(self, *_):
        if not self.input_file or self.busy:
            return
        fmt = self._selected_format()
        theme = self.theme_combo.get_active_id() or "elegant"
        self.busy = True
        self.convert_btn.set_sensitive(False)
        self.result_box.hide()
        self.spinner.show()
        self.spinner.start()
        threading.Thread(target=self._work, args=(fmt, theme),
                         daemon=True).start()

    def _work(self, fmt, theme):
        try:
            out, note = converter.convert(self.input_file, fmt, theme)
            GLib.idle_add(self._done, out, note)
        except converter.ConversionError as e:
            GLib.idle_add(self._fail, str(e))
        except Exception as e:  # unexpected
            GLib.idle_add(self._fail, f"Unexpected error: {e}")

    def _finish_busy(self):
        self.busy = False
        self.spinner.stop()
        self.spinner.hide()
        self.convert_btn.set_sensitive(True)

    def _done(self, out, note):
        self._finish_busy()
        self.output_file = out
        self.result_label.set_markup(
            f'<span size="large">✓</span>  Saved as <b>{GLib.markup_escape_text(out.name)}</b>')
        self.result_label.get_style_context().add_class("result-ok")
        self.result_label.get_style_context().remove_class("result-err")
        if note:
            self.note_label.set_label(note)
            self.note_label.show()
        else:
            self.note_label.hide()
        self.result_box.show()
        self.result_label.show()
        self.open_btn.show()
        self.folder_btn.show()

    def _fail(self, msg):
        self._finish_busy()
        self._error(msg)

    def _error(self, msg):
        self.result_label.set_label(msg)
        self.result_label.get_style_context().add_class("result-err")
        self.result_label.get_style_context().remove_class("result-ok")
        self.note_label.hide()
        self.result_box.show()
        self.result_label.show()
        self.open_btn.hide()
        self.folder_btn.hide()

    # --- updates ------------------------------------------------------------
    def on_check_updates(self, *_):
        dlg = Gtk.Dialog(title="Updates & dependencies", transient_for=self,
                         modal=True)
        dlg.set_default_size(400, -1)
        dlg.set_resizable(False)
        dlg.add_button("Close", Gtk.ResponseType.CLOSE)
        area = dlg.get_content_area()
        area.set_spacing(12)
        area.set_property("margin", 16)
        status = Gtk.Label(label="Checking…")
        status.set_line_wrap(True)
        status.set_max_width_chars(44)
        status.set_justify(Gtk.Justification.CENTER)
        grid = Gtk.Grid(column_spacing=16, row_spacing=6)
        grid.set_halign(Gtk.Align.CENTER)
        area.pack_start(status, False, False, 0)
        area.pack_start(grid, False, False, 0)
        state = {"url": None}

        def on_response(d, resp):
            if resp == 1 and state["url"]:
                webbrowser.open(state["url"])
            else:
                d.destroy()
        dlg.connect("response", on_response)
        dlg.show_all()

        app_cls = {"ok": "result-ok", "update": "result-warn",
                   "dev": "note", "error": "result-err"}
        dep_cls = {"ok": "result-ok", "installed": "result-ok",
                   "outdated": "result-warn", "missing": "result-err"}

        def show(app, deps):
            if not dlg.get_visible():
                return
            status.set_label(app["message"])
            status.get_style_context().add_class(app_cls[app["status"]])
            if app["status"] == "update" and app.get("url"):
                state["url"] = app["url"]
                dlg.add_button("Download update", 1)
            for i, d in enumerate(deps):
                name = Gtk.Label(xalign=1, yalign=0)
                name.set_markup(f"<b>{GLib.markup_escape_text(d['name'])}</b>")
                val = Gtk.Label(label=updates.describe(d), xalign=0)
                val.set_line_wrap(True)
                val.set_max_width_chars(40)
                val.get_style_context().add_class(dep_cls[d["status"]])
                grid.attach(name, 0, i, 1, 1)
                grid.attach(val, 1, i, 1, 1)
            dlg.show_all()

        def work():
            app = updates.check_app_update()
            deps = updates.check_dependencies()
            GLib.idle_add(show, app, deps)

        threading.Thread(target=work, daemon=True).start()

    # --- result actions -----------------------------------------------------
    def on_open_file(self, *_):
        subprocess.Popen(["xdg-open", str(self.output_file)])

    def on_open_folder(self, *_):
        subprocess.Popen(["xdg-open", str(self.output_file.parent)])


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        win = self.get_active_window()
        if not win:
            win = Window(self)
        win.present()


if __name__ == "__main__":
    App().run()
