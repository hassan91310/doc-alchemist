# Third-party software in Doc Alchemist

The Windows builds of Doc Alchemist include the following open-source
software. Full license texts for the bundled Python packages are in
`THIRD-PARTY-LICENSES.txt`, next to this file. Pandoc's license is in
the `pandoc` folder.

| Component | License | Source |
|-----------|---------|--------|
| pandoc (separate program in `pandoc\`) | GPL-2.0-or-later | https://github.com/jgm/pandoc |
| Python | PSF-2.0 | https://www.python.org |
| Tcl/Tk | Tcl/Tk license (BSD-style) | https://www.tcl.tk |
| markitdown | MIT | https://github.com/microsoft/markitdown |
| magika | Apache-2.0 | https://github.com/google/magika |
| pdfminer.six | MIT | https://github.com/pdfminer/pdfminer.six |
| fpdf2 | LGPL-3.0 | https://github.com/py-pdf/fpdf2 |
| Python-Markdown | BSD-3-Clause | https://github.com/Python-Markdown/markdown |
| tkinterdnd2 / tkdnd | MIT / BSD-style | https://github.com/Eliav2/tkinterdnd2 |
| pywin32 | PSF-2.0 | https://github.com/mhammond/pywin32 |
| uharfbuzz / HarfBuzz | Apache-2.0 / MIT | https://github.com/harfbuzz/uharfbuzz |

Pandoc is a separate program that Doc Alchemist runs. It is shipped
unmodified. Its source code is available at the link above; for the
exact version shipped, see `pandoc\pandoc.exe --version` and the
matching release tag.

Optional programs that Doc Alchemist uses if they're installed, but
does not ship: LibreOffice (MPL-2.0) and Microsoft Word.
