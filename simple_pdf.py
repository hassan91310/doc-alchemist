#!/usr/bin/env python3
"""Built-in "simple" Markdown -> PDF renderer.

Fallback used when neither LibreOffice nor MS Word is available.
Pure Python (markdown + fpdf2), basic but readable styling that
approximates the document themes.

Usable as a module (render()) or a script:
    python simple_pdf.py input.md output.pdf [theme]
"""
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

    meta, md_text = _split_front_matter(
        Path(src).read_text(encoding="utf-8", errors="replace"))
    html = markdown.markdown(
        md_text, extensions=["tables", "fenced_code", "sane_lists"])
    html = _latinize(html)

    pdf = _Doc(format="A4")
    pdf.body_font = body_font
    pdf.set_margins(22, 20, 22)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()

    # title block from front matter
    if meta.get("title"):
        pdf.set_font(head_font, "B", 26)
        pdf.set_text_color(*head_color)
        pdf.multi_cell(0, 12, _latinize(meta["title"]), align="C",
                       new_x="LMARGIN", new_y="NEXT")
        if meta.get("subtitle"):
            pdf.set_font(head_font, "I", 14)
            pdf.set_text_color(110, 110, 110)
            pdf.multi_cell(0, 8, _latinize(meta["subtitle"]), align="C",
                           new_x="LMARGIN", new_y="NEXT")
        line = " - ".join(filter(None, [meta.get("author"), meta.get("date")]))
        if line:
            pdf.set_font(body_font, "", 10)
            pdf.set_text_color(110, 110, 110)
            pdf.multi_cell(0, 6, _latinize(line), align="C",
                           new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

    pdf.set_font(body_font, "", 11)
    pdf.set_text_color(30, 30, 30)

    hc = "#%02x%02x%02x" % head_color
    ac = "#%02x%02x%02x" % accent
    try:  # newer fpdf2: per-tag styling
        from fpdf.fonts import FontFace
        tag_styles = {
            f"h{i}": FontFace(family=head_font, color=hc,
                              size_pt=[0, 22, 17, 14, 12, 11, 11][i])
            for i in range(1, 7)
        }
        tag_styles["a"] = FontFace(color=ac)
        pdf.write_html(html, tag_styles=tag_styles)
    except Exception:
        pdf.write_html(html)

    pdf.output(str(dest))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: simple_pdf.py input.md output.pdf [theme]")
        sys.exit(1)
    render(sys.argv[1], sys.argv[2],
           sys.argv[3] if len(sys.argv) > 3 else "elegant")
    print(f"wrote {sys.argv[2]}")
