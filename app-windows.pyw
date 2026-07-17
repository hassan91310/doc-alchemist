#!/usr/bin/env python3
"""Doc Alchemist for Windows — Markdown <-> DOCX / PDF converter.

Tkinter UI sharing converter.py and themes/ with the Linux app.
Run install-windows.bat once, then double-click this file.
"""
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import converter

# optional drag & drop support (pip install tkinterdnd2)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TkRoot = TkinterDnD.Tk
    HAS_DND = True
except ImportError:
    TkRoot = tk.Tk
    HAS_DND = False

BG = "#fafafa"
ACCENT = "#1a73e8"
OK = "#2e7d32"
ERR = "#c62828"
MUTED = "#777777"

KIND_EMOJI = {"md": "📝", "docx": "📄", "pdf": "📕"}


class App(TkRoot):
    def __init__(self):
        super().__init__()
        self.title("Doc Alchemist")
        self.geometry("480x560")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.input_file = None
        self.output_file = None
        self.busy = False

        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure(".", background=BG, font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"))

        main = ttk.Frame(self, padding=20)
        main.pack(fill="both", expand=True)

        head = tk.Label(main, text="Doc Alchemist", bg=BG,
                        font=("Segoe UI", 16, "bold"))
        sub = tk.Label(main, text="Markdown ⇆ Word ⇆ PDF", bg=BG,
                       fg=MUTED, font=("Segoe UI", 10))
        head.pack()
        sub.pack(pady=(0, 12))

        # --- drop zone -----------------------------------------------------
        self.zone = tk.Canvas(main, height=170, bg="#f0f2f5",
                              highlightthickness=0, cursor="hand2")
        self.zone.pack(fill="x")
        self.zone.bind("<Button-1>", self.on_browse)
        self.zone.bind("<Configure>", lambda e: self._draw_zone())
        if HAS_DND:
            self.zone.drop_target_register(DND_FILES)
            self.zone.dnd_bind("<<Drop>>", self.on_drop)

        # --- options ---------------------------------------------------------
        opts = ttk.Frame(main)
        opts.pack(pady=16)
        ttk.Label(opts, text="Convert to").grid(row=0, column=0, sticky="e",
                                                padx=(0, 10), pady=4)
        self.fmt_var = tk.StringVar(value="docx")
        self.fmt_frame = ttk.Frame(opts)
        self.fmt_frame.grid(row=0, column=1, sticky="w", pady=4)
        self.fmt_buttons = []

        ttk.Label(opts, text="Theme").grid(row=1, column=0, sticky="e",
                                           padx=(0, 10), pady=4)
        self.theme_var = tk.StringVar()
        self.theme_combo = ttk.Combobox(
            opts, textvariable=self.theme_var, state="readonly", width=28,
            values=list(converter.THEMES.values()))
        self.theme_combo.current(0)
        self.theme_combo.grid(row=1, column=1, sticky="w", pady=4)

        # --- convert ---------------------------------------------------------
        self.convert_btn = ttk.Button(main, text="Convert",
                                      style="Accent.TButton",
                                      command=self.on_convert,
                                      state="disabled")
        self.convert_btn.pack(ipadx=18, ipady=2)
        self.progress = ttk.Progressbar(main, mode="indeterminate",
                                        length=200)

        # --- result ----------------------------------------------------------
        self.result_var = tk.StringVar()
        self.result_label = tk.Label(main, textvariable=self.result_var,
                                     bg=BG, wraplength=420, justify="center",
                                     font=("Segoe UI", 10, "bold"))
        self.result_label.pack(pady=(14, 2))
        self.note_var = tk.StringVar()
        tk.Label(main, textvariable=self.note_var, bg=BG, fg=MUTED,
                 wraplength=430, font=("Segoe UI", 8)).pack()
        self.action_frame = ttk.Frame(main)
        ttk.Button(self.action_frame, text="Open file",
                   command=self.on_open).pack(side="left", padx=4)
        ttk.Button(self.action_frame, text="Show in folder",
                   command=self.on_folder).pack(side="left", padx=4)

        # --- credits ---------------------------------------------------------
        tk.Label(self, text="Made with ❤ by Hassan Ali", bg=BG, fg="#999999",
                 font=("Segoe UI", 8)).pack(side="bottom", pady=6)

        self._set_formats(None)
        self._draw_zone()

    # --- drop zone -----------------------------------------------------------
    def _draw_zone(self):
        z = self.zone
        z.delete("all")
        w = z.winfo_width() or 440
        h = int(z["height"])
        z.create_rectangle(6, 6, w - 6, h - 6, dash=(6, 4), width=2,
                           outline="#9aa7b8")
        if self.input_file:
            kind = converter.input_kind(self.input_file)
            z.create_text(w / 2, h / 2 - 26, text=KIND_EMOJI.get(kind, "📄"),
                          font=("Segoe UI Emoji", 26))
            name = self.input_file.name
            if len(name) > 44:
                name = name[:24] + "…" + name[-16:]
            z.create_text(w / 2, h / 2 + 12, text=name,
                          font=("Segoe UI", 11, "bold"), fill="#222222")
            z.create_text(w / 2, h / 2 + 36,
                          text="Click to choose a different file",
                          font=("Segoe UI", 9), fill=MUTED)
        else:
            z.create_text(w / 2, h / 2 - 26, text="📂",
                          font=("Segoe UI Emoji", 26))
            hint = ("Drop a file here" if HAS_DND else "Click to choose a file")
            z.create_text(w / 2, h / 2 + 12, text=hint,
                          font=("Segoe UI", 12, "bold"), fill="#222222")
            z.create_text(w / 2, h / 2 + 36,
                          text="or click to browse — .md, .docx, .pdf",
                          font=("Segoe UI", 9), fill=MUTED)

    def on_browse(self, *_):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title="Choose a file",
            filetypes=[("Documents", "*.md *.markdown *.txt *.docx *.pdf"),
                       ("All files", "*.*")])
        if path:
            self.set_input(path)

    def on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        if paths:
            self.set_input(paths[0])

    def set_input(self, path):
        kind = converter.input_kind(path)
        if kind is None:
            self._show_error("That file type isn't supported. "
                             "Choose a .md, .docx or .pdf file.")
            return
        self.input_file = Path(path)
        self._clear_result()
        self._set_formats(kind)
        self.convert_btn.config(state="normal")
        self._draw_zone()

    # --- formats / theme -------------------------------------------------------
    def _set_formats(self, kind):
        for b in self.fmt_buttons:
            b.destroy()
        self.fmt_buttons = []
        options = converter.OUTPUTS_FOR.get(
            kind, [("docx", "Word (.docx)"), ("pdf", "PDF (.pdf)")])
        self.fmt_var.set(options[0][0])
        for fmt, label in options:
            b = ttk.Radiobutton(self.fmt_frame, text=label, value=fmt,
                                variable=self.fmt_var,
                                command=self._update_theme_state,
                                state="normal" if kind else "disabled")
            b.pack(side="left", padx=(0, 10))
            self.fmt_buttons.append(b)
        self._update_theme_state()

    def _update_theme_state(self):
        themed = self.fmt_var.get() in ("docx", "pdf")
        self.theme_combo.config(state="readonly" if themed else "disabled")

    def _theme_key(self):
        label = self.theme_var.get()
        for key, val in converter.THEMES.items():
            if val == label:
                return key
        return "elegant"

    # --- conversion --------------------------------------------------------------
    def on_convert(self):
        if not self.input_file or self.busy:
            return
        self.busy = True
        self.convert_btn.config(state="disabled")
        self._clear_result()
        self.progress.pack(pady=(10, 0))
        self.progress.start(12)
        fmt, theme = self.fmt_var.get(), self._theme_key()
        threading.Thread(target=self._work, args=(fmt, theme),
                         daemon=True).start()

    def _work(self, fmt, theme):
        try:
            out, note = converter.convert(self.input_file, fmt, theme)
            self.after(0, self._done, out, note)
        except converter.ConversionError as e:
            self.after(0, self._fail, str(e))
        except Exception as e:
            self.after(0, self._fail, f"Unexpected error: {e}")

    def _finish_busy(self):
        self.busy = False
        self.progress.stop()
        self.progress.pack_forget()
        self.convert_btn.config(state="normal")

    def _done(self, out, note):
        self._finish_busy()
        self.output_file = out
        self.result_label.config(fg=OK)
        self.result_var.set(f"✓  Saved as {out.name}")
        self.note_var.set(note)
        self.action_frame.pack(pady=6)

    def _fail(self, msg):
        self._finish_busy()
        self._show_error(msg)

    def _show_error(self, msg):
        self.result_label.config(fg=ERR)
        self.result_var.set(msg)
        self.note_var.set("")
        self.action_frame.pack_forget()

    def _clear_result(self):
        self.result_var.set("")
        self.note_var.set("")
        self.action_frame.pack_forget()

    # --- result actions -------------------------------------------------------------
    def on_open(self):
        if self.output_file:
            import os
            os.startfile(str(self.output_file))

    def on_folder(self):
        if self.output_file:
            subprocess.Popen(["explorer", "/select,", str(self.output_file)])


if __name__ == "__main__":
    App().mainloop()
