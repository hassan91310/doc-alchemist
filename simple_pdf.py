#!/usr/bin/env python3
"""Built-in "simple" Markdown -> PDF renderer.

Fallback used when neither LibreOffice nor MS Word is available.
Pure Python (markdown + fpdf2), basic but readable styling that
approximates the document themes.

Usable as a module (render()) or a script:
    python simple_pdf.py input.md output.pdf [theme]
"""
import os
import re
import sys
from pathlib import Path

import markdown
from fpdf import FPDF

# theme -> (body_font, heading_font, heading_color, accent_color)
STYLES = {
    "elegant": ("times", "times", (31, 58, 95), (31, 92, 139)),
    "modern": ("helvetica", "helvetica", (26, 115, 232), (26, 115, 232)),
    "minimal": ("helvetica", "helvetica", (17, 17, 17), (11, 87, 208)),
}

# Unicode TrueType fonts, used when the system has them (the core PDF
# fonts above are latin-1 only). role -> candidate (dir, regular, bold,
# italic, bold-italic); the first set whose regular file exists wins.
WIN_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
DEJAVU = Path("/usr/share/fonts/truetype/dejavu")
_DEJAVU_SANS = (DEJAVU, "DejaVuSans.ttf", "DejaVuSans-Bold.ttf",
                "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf")
FONT_FILES = {
    "serif": [(WIN_FONTS, "georgia.ttf", "georgiab.ttf", "georgiai.ttf",
               "georgiaz.ttf"),
              (DEJAVU, "DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf",
               "DejaVuSerif-Italic.ttf", "DejaVuSerif-BoldItalic.ttf")],
    "sans": [(WIN_FONTS, "calibri.ttf", "calibrib.ttf", "calibrii.ttf",
              "calibriz.ttf"), _DEJAVU_SANS],
    "arial": [(WIN_FONTS, "arial.ttf", "arialbd.ttf", "ariali.ttf",
               "arialbi.ttf"), _DEJAVU_SANS],
    "mono": [(WIN_FONTS, "consola.ttf", "consolab.ttf", "consolai.ttf",
              "consolaz.ttf"),
             (DEJAVU, "DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf",
              "DejaVuSansMono-Oblique.ttf",
              "DejaVuSansMono-BoldOblique.ttf")],
}
# theme -> (body role, heading role), matching the docx themes
THEME_FONTS = {"elegant": ("serif", "serif"), "modern": ("sans", "sans"),
               "minimal": ("arial", "arial")}
# glyphs the theme fonts lack: Arabic/Urdu, Indic, CJK, Korean
FALLBACK_FILES = [
    WIN_FONTS / "segoeui.ttf", WIN_FONTS / "Nirmala.ttf",
    WIN_FONTS / "Nirmala.ttc", WIN_FONTS / "msyh.ttc",
    WIN_FONTS / "malgun.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
    Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
]

# core PDF fonts are latin-1 only; map common unicode punctuation
REPLACEMENTS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "•": "*",
    " ": " ", "→": "->", "⇆": "<->", "✅": "[ok]",
    "✓": "v", "✗": "x", "❤": "<3", "﻿": "",
}


def _latinize(text):
    for k, v in REPLACEMENTS.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def _add_family(pdf, role):
    """Register a TrueType family for role; returns its name or None."""
    for folder, *files in FONT_FILES[role]:
        paths = [folder / f for f in files]
        if not paths[0].exists():
            continue
        for style, path in zip(("", "B", "I", "BI"), paths):
            # a missing bold/italic file falls back to the regular face
            pdf.add_font(role, style, str(path if path.exists()
                                          else paths[0]))
        return role
    return None


def _setup_unicode_fonts(pdf, theme, text):
    """Returns (body, heading, mono) TrueType families, or None if the
    system lacks them (then the latin-1 core fonts are used)."""
    body_role, head_role = THEME_FONTS.get(theme, THEME_FONTS["elegant"])
    try:
        body = _add_family(pdf, body_role)
        head = _add_family(pdf, head_role) if head_role != body_role else body
        mono = _add_family(pdf, "mono") or body
    except Exception:
        return None
    if not body:
        return None
    # only load the (large) script fonts when the text needs them;
    # punctuation and symbols (U+2000-2BFF) are in the theme fonts
    if any(ord(c) > 0x2FF and not 0x2000 <= ord(c) < 0x2C00 for c in text):
        fallbacks = []
        for i, path in enumerate(p for p in FALLBACK_FILES if p.exists()):
            try:
                pdf.add_font(f"fallback{i}", "", str(path))
                fallbacks.append(f"fallback{i}")
            except Exception:
                pass
        if fallbacks:
            pdf.set_fallback_fonts(fallbacks, exact_match=False)
        try:  # joins Arabic/Urdu letters and lays out right-to-left
            pdf.set_text_shaping(True)
        except Exception:  # uharfbuzz not installed
            pass
    return body, head or body, mono


def _split_front_matter(md_text):
    """Return (meta dict, body) honoring a leading YAML block."""
    meta = {}
    if md_text.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", md_text, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip().lower()] = v.strip().strip("'\"")
            md_text = md_text[m.end():]
    return meta, md_text


class _Doc(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font(self.body_font, "", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 10, f"{self.page_no()}", align="C")


def render(src, dest, theme="elegant"):
    body_font, head_font, head_color, accent = STYLES.get(
        theme, STYLES["elegant"])
    mono_font = None

    meta, md_text = _split_front_matter(
        Path(src).read_text(encoding="utf-8", errors="replace"))
    html = markdown.markdown(
        md_text, extensions=["tables", "fenced_code", "sane_lists"])

    pdf = _Doc(format="A4")
    fonts = _setup_unicode_fonts(pdf, theme, md_text)
    if fonts:
        body_font, head_font, mono_font = fonts
        text = str
    else:
        text = _latinize
    html = text(html)
    pdf.body_font = body_font
    pdf.set_margins(22, 20, 22)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()

    # title block from front matter
    if meta.get("title"):
        pdf.set_font(head_font, "B", 26)
        pdf.set_text_color(*head_color)
        pdf.multi_cell(0, 12, text(meta["title"]), align="C",
                       new_x="LMARGIN", new_y="NEXT")
        if meta.get("subtitle"):
            pdf.set_font(head_font, "I", 14)
            pdf.set_text_color(110, 110, 110)
            pdf.multi_cell(0, 8, text(meta["subtitle"]), align="C",
                           new_x="LMARGIN", new_y="NEXT")
        line = " - ".join(filter(None, [meta.get("author"), meta.get("date")]))
        if line:
            pdf.set_font(body_font, "", 10)
            pdf.set_text_color(110, 110, 110)
            pdf.multi_cell(0, 6, text(line), align="C",
                           new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

    pdf.set_font(body_font, "", 11)
    pdf.set_text_color(30, 30, 30)

    hc = "#%02x%02x%02x" % head_color
    ac = "#%02x%02x%02x" % accent
    try:
        from fpdf.fonts import FontFace
    except ImportError:  # old fpdf2: no per-tag styling
        pdf.write_html(html)
    else:
        tag_styles = {
            f"h{i}": FontFace(family=head_font, color=hc,
                              size_pt=[0, 22, 17, 14, 12, 11, 11][i])
            for i in range(1, 7)
        }
        tag_styles["a"] = FontFace(color=ac)
        if mono_font:
            tag_styles["code"] = FontFace(family=mono_font)
            tag_styles["pre"] = FontFace(family=mono_font)
        pdf.write_html(html, tag_styles=tag_styles)

    pdf.output(str(dest))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: simple_pdf.py input.md output.pdf [theme]")
        sys.exit(1)
    render(sys.argv[1], sys.argv[2],
           sys.argv[3] if len(sys.argv) > 3 else "elegant")
    print(f"wrote {sys.argv[2]}")
