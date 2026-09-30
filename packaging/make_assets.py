#!/usr/bin/env python3
"""Render the MSIX logo images in packaging/Assets/ from assets/icon.svg.

Needs: pip install cairosvg pillow
The PNGs are committed, so this only has to be re-run when the icon
changes.
"""
import io
from pathlib import Path

import cairosvg
from PIL import Image

HERE = Path(__file__).resolve().parent
SVG = (HERE.parent / "assets" / "icon.svg").read_bytes()
OUT = HERE / "Assets"


def icon(size):
    png = cairosvg.svg2png(bytestring=SVG, output_width=size,
                           output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def tile(w, h, icon_size):
    """Icon centered on a transparent w x h canvas."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ic = icon(icon_size)
    im.paste(ic, ((w - icon_size) // 2, (h - icon_size) // 2), ic)
    return im


def main():
    OUT.mkdir(exist_ok=True)
    for scale in (100, 200):
        f = scale / 100
        # tiles: icon at ~2/3 of the tile height, like the Windows defaults
        tile(int(150 * f), int(150 * f), int(100 * f)).save(
            OUT / f"Square150x150Logo.scale-{scale}.png")
        tile(int(310 * f), int(150 * f), int(100 * f)).save(
            OUT / f"Wide310x150Logo.scale-{scale}.png")
        tile(int(44 * f), int(44 * f), int(44 * f)).save(
            OUT / f"Square44x44Logo.scale-{scale}.png")
        tile(int(50 * f), int(50 * f), int(50 * f)).save(
            OUT / f"StoreLogo.scale-{scale}.png")
    # taskbar / start menu / file explorer sizes
    for size in (16, 24, 32, 48, 256):
        im = icon(size)
        im.save(OUT / f"Square44x44Logo.targetsize-{size}.png")
        im.save(OUT / f"Square44x44Logo.targetsize-{size}_altform-unplated.png")
    print(f"wrote {len(list(OUT.glob('*.png')))} images to {OUT}")


if __name__ == "__main__":
    main()
