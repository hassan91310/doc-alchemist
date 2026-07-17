#!/usr/bin/env python3
"""Generate themed pandoc reference .docx files in themes/.

Takes pandoc's default reference.docx and patches word/styles.xml
(fonts, colors, sizes) for each theme. Stdlib only.
"""
import re
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}

HERE = Path(__file__).resolve().parent
THEME_DIR = HERE / "themes"

# Per-theme style overrides.
#   font: (ascii/hAnsi font name)
#   color: RRGGBB   sz: half-points   b/i: bold/italic on-off
THEMES = {
    "elegant": {
        "_default": {"font": "Georgia", "sz": 22, "color": "333333"},
        "Title":      {"font": "Georgia", "sz": 56, "color": "1F3A5F"},
        "Subtitle":   {"font": "Georgia", "sz": 30, "color": "5A7184", "i": True},
        "Author":     {"font": "Georgia", "color": "5A7184"},
        "Date":       {"font": "Georgia", "color": "5A7184"},
        "Heading1":   {"font": "Georgia", "sz": 40, "color": "1F3A5F"},
        "Heading2":   {"font": "Georgia", "sz": 32, "color": "1F3A5F"},
        "Heading3":   {"font": "Georgia", "sz": 28, "color": "2E5077"},
        "Heading4":   {"font": "Georgia", "sz": 24, "color": "2E5077", "i": True},
        "Heading5":   {"font": "Georgia", "sz": 22, "color": "2E5077"},
        "Heading6":   {"font": "Georgia", "sz": 22, "color": "5A7184"},
        "Hyperlink":  {"color": "1F5C8B"},
        "BlockText":  {"color": "5A7184", "i": True},
        "SourceCode": {"font_code": "Consolas", "sz": 19},
        "VerbatimChar": {"font_code": "Consolas", "color": "9C3328"},
    },
    "modern": {
        "_default": {"font": "Calibri", "sz": 22, "color": "3B3B3B"},
        "Title":      {"font": "Calibri Light", "sz": 60, "color": "1A73E8"},
        "Subtitle":   {"font": "Calibri Light", "sz": 30, "color": "5F6368"},
        "Author":     {"font": "Calibri", "color": "5F6368"},
        "Date":       {"font": "Calibri", "color": "5F6368"},
        "Heading1":   {"font": "Calibri Light", "sz": 40, "color": "1A73E8"},
        "Heading2":   {"font": "Calibri Light", "sz": 32, "color": "1A73E8"},
        "Heading3":   {"font": "Calibri Light", "sz": 28, "color": "185ABC"},
        "Heading4":   {"font": "Calibri", "sz": 24, "color": "185ABC", "b": True},
        "Heading5":   {"font": "Calibri", "sz": 22, "color": "185ABC", "b": True},
        "Heading6":   {"font": "Calibri", "sz": 22, "color": "5F6368", "b": True},
        "Hyperlink":  {"color": "1A73E8"},
        "BlockText":  {"color": "5F6368", "i": True},
        "SourceCode": {"font_code": "Consolas", "sz": 19},
        "VerbatimChar": {"font_code": "Consolas", "color": "C5221F"},
    },
    "minimal": {
        "_default": {"font": "Arial", "sz": 21, "color": "111111"},
        "Title":      {"font": "Arial", "sz": 52, "color": "111111", "b": True},
        "Subtitle":   {"font": "Arial", "sz": 26, "color": "767676"},
        "Author":     {"font": "Arial", "color": "767676"},
        "Date":       {"font": "Arial", "color": "767676"},
        "Heading1":   {"font": "Arial", "sz": 36, "color": "111111", "b": True},
        "Heading2":   {"font": "Arial", "sz": 29, "color": "111111", "b": True},
        "Heading3":   {"font": "Arial", "sz": 25, "color": "111111", "b": True},
        "Heading4":   {"font": "Arial", "sz": 22, "color": "111111", "b": True},
        "Heading5":   {"font": "Arial", "sz": 21, "color": "444444", "b": True},
        "Heading6":   {"font": "Arial", "sz": 21, "color": "767676", "b": True},
        "Hyperlink":  {"color": "0B57D0"},
        "BlockText":  {"color": "555555", "i": True},
        "SourceCode": {"font_code": "Consolas", "sz": 19},
        "VerbatimChar": {"font_code": "Consolas", "color": "B3261E"},
    },
}

# Canonical child order inside w:rPr (subset we touch).
RPR_ORDER = ["rFonts", "b", "bCs", "i", "iCs", "color", "sz", "szCs"]


def w_tag(name):
    return f"{{{W}}}{name}"


def set_rpr_child(rpr, name, attrs):
    """Insert or update a w:rPr child, keeping schema order."""
    el = rpr.find(f"w:{name}", NS)
    if el is None:
        el = ET.Element(w_tag(name))
        my_rank = RPR_ORDER.index(name)
        pos = 0
        for i, child in enumerate(list(rpr)):
            local = child.tag.split("}")[-1]
            rank = RPR_ORDER.index(local) if local in RPR_ORDER else -1
            if rank != -1 and rank < my_rank:
                pos = i + 1
        rpr.insert(pos, el)
    for k, v in attrs.items():
        el.set(w_tag(k), v)
    return el


def get_or_make_rpr(style):
    rpr = style.find("w:rPr", NS)
    if rpr is None:
        rpr = ET.Element(w_tag("rPr"))
        style.append(rpr)  # rPr goes after pPr/metadata children
    return rpr


def _set_fonts(rpr, font):
    el = set_rpr_child(rpr, "rFonts", {"ascii": font, "hAnsi": font})
    # theme font attributes override explicit names — drop them
    for a in ("asciiTheme", "hAnsiTheme", "cstheme", "eastAsiaTheme"):
        el.attrib.pop(w_tag(a), None)


def apply_spec(rpr, spec):
    if "font" in spec:
        _set_fonts(rpr, spec["font"])
    if "font_code" in spec:
        _set_fonts(rpr, spec["font_code"])
    if "color" in spec:
        el = set_rpr_child(rpr, "color", {"val": spec["color"]})
        el.attrib.pop(w_tag("themeColor"), None)
        el.attrib.pop(w_tag("themeShade"), None)
        el.attrib.pop(w_tag("themeTint"), None)
    if "sz" in spec:
        set_rpr_child(rpr, "sz", {"val": str(spec["sz"])})
        set_rpr_child(rpr, "szCs", {"val": str(spec["sz"])})
    if spec.get("b"):
        set_rpr_child(rpr, "b", {})
        set_rpr_child(rpr, "bCs", {})
    if spec.get("i"):
        set_rpr_child(rpr, "i", {})
        set_rpr_child(rpr, "iCs", {})


def patch_styles_xml(xml_bytes, theme):
    # Register every namespace declared on the root so ET preserves prefixes.
    for prefix, uri in re.findall(rb'xmlns:(\w+)="([^"]+)"', xml_bytes[:4000]):
        ET.register_namespace(prefix.decode(), uri.decode())
    root = ET.fromstring(xml_bytes)

    default = theme.get("_default", {})
    rpr_default = root.find("w:docDefaults/w:rPrDefault/w:rPr", NS)
    if rpr_default is not None and default:
        apply_spec(rpr_default, default)

    for style in root.findall("w:style", NS):
        style_id = style.get(w_tag("styleId"))
        spec = theme.get(style_id)
        if spec:
            apply_spec(get_or_make_rpr(style), spec)

    return ET.tostring(root, xml_declaration=True, encoding="UTF-8")


def build_theme(base_docx, name, theme):
    out_path = THEME_DIR / f"{name}.docx"
    with zipfile.ZipFile(base_docx) as zin:
        items = [(i, zin.read(i.filename)) for i in zin.infolist()]
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, data in items:
            if info.filename == "word/styles.xml":
                data = patch_styles_xml(data, theme)
            zout.writestr(info.filename, data)
    print(f"wrote {out_path}")


def main():
    THEME_DIR.mkdir(exist_ok=True)
    base = THEME_DIR / "_base_reference.docx"
    with open(base, "wb") as f:
        subprocess.run(
            ["pandoc", "--print-default-data-file", "reference.docx"],
            stdout=f, check=True)
    for name, theme in THEMES.items():
        build_theme(base, name, theme)
    base.unlink()


if __name__ == "__main__":
    main()
