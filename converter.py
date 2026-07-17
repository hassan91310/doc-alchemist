#!/usr/bin/env python3
"""Conversion engine: Markdown <-> DOCX / PDF.

Routes:
  md   -> docx : pandoc with a themed reference docx
  md   -> pdf  : pandoc -> themed docx -> LibreOffice PDF export
  docx -> md   : pandoc (extracts embedded images alongside)
  docx -> pdf  : LibreOffice PDF export
  pdf  -> md   : markitdown (falls back to pdftotext if missing)
  pdf  -> docx : pdf -> md -> themed docx
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if getattr(sys, "frozen", False):  # running from a PyInstaller bundle
    HERE = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    HERE = Path(__file__).resolve().parent
THEME_DIR = HERE / "themes"
IS_WINDOWS = sys.platform == "win32"
# don't flash console windows when running from the .pyw GUI on Windows
POPEN_FLAGS = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}

THEMES = {
    "elegant": "Elegant — serif, deep navy",
    "modern": "Modern — clean sans, blue",
    "minimal": "Minimal — black & white",
}

MD_EXTS = {".md", ".markdown", ".mdown", ".mkd", ".txt"}

# input kind -> offered output formats
OUTPUTS_FOR = {
    "md": [("docx", "Word (.docx)"), ("pdf", "PDF (.pdf)")],
    "docx": [("md", "Markdown (.md)"), ("pdf", "PDF (.pdf)")],
    "pdf": [("md", "Markdown (.md)"), ("docx", "Word (.docx)")],
}


class ConversionError(Exception):
    pass


class NoPdfEngineError(ConversionError):
    """No LibreOffice / MS Word available for high-quality PDF export."""


def input_kind(path):
    ext = Path(path).suffix.lower()
    if ext in MD_EXTS:
        return "md"
    if ext == ".docx":
        return "docx"
    if ext == ".pdf":
        return "pdf"
    return None


def unique_path(directory, stem, ext):
    p = Path(directory) / f"{stem}{ext}"
    n = 1
    while p.exists():
        p = Path(directory) / f"{stem}-{n}{ext}"
        n += 1
    return p


def _run(cmd, **kw):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=180, **POPEN_FLAGS, **kw)
    except FileNotFoundError:
        raise ConversionError(f"'{cmd[0]}' is not installed.")
    except subprocess.TimeoutExpired:
        raise ConversionError(f"'{cmd[0]}' timed out.")
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip().splitlines()
        tail = "\n".join(msg[-4:]) if msg else "unknown error"
        raise ConversionError(f"{Path(cmd[0]).name} failed:\n{tail}")
    return r


def _find_bin(name, extra_paths=()):
    found = shutil.which(name)
    if found:
        return found
    for p in extra_paths:
        p = Path(os.path.expandvars(str(p)))
        if p.exists():
            return str(p)
    return None


def _pandoc_bin():
    b = _find_bin("pandoc", [
        r"%LOCALAPPDATA%\Pandoc\pandoc.exe",
        r"%ProgramFiles%\Pandoc\pandoc.exe",
    ] if IS_WINDOWS else [])
    if not b:
        raise ConversionError(
            "pandoc is not installed.\n"
            + ("Run install-windows.bat or: winget install JohnMacFarlane.Pandoc"
               if IS_WINDOWS else "Run: sudo apt install pandoc"))
    return b


def _soffice_bin():
    return _find_bin("soffice", [
        r"%ProgramFiles%\LibreOffice\program\soffice.exe",
        r"%ProgramFiles(x86)%\LibreOffice\program\soffice.exe",
    ] if IS_WINDOWS else [])


def _markitdown_bin():
    sub = ("Scripts", "markitdown.exe") if IS_WINDOWS else ("bin", "markitdown")
    cand = HERE / "venv" / sub[0] / sub[1]
    if cand.exists():
        return str(cand)
    return shutil.which("markitdown")


def _md_to_docx(src, dest, theme):
    ref = THEME_DIR / f"{theme}.docx"
    _run([_pandoc_bin(), "-s", str(src), "-o", str(dest),
          f"--reference-doc={ref}", "--highlight-style=tango"],
         cwd=str(Path(src).parent))


def _docx_to_pdf(src, dest):
    soffice = _soffice_bin()
    if soffice:
        with tempfile.TemporaryDirectory(prefix="mdconv-") as tmp:
            profile = (Path(tmp) / "lo-profile").as_uri()
            _run([soffice, "--headless",
                  f"-env:UserInstallation={profile}",
                  "--convert-to", "pdf", "--outdir", tmp, str(src)])
            produced = Path(tmp) / (Path(src).stem + ".pdf")
            if not produced.exists():
                raise ConversionError("LibreOffice did not produce a PDF.")
            shutil.move(str(produced), str(dest))
        return
    if IS_WINDOWS:
        # fall back to Microsoft Word via docx2pdf
        try:
            from docx2pdf import convert as _word_convert
            _word_convert(str(src), str(dest))
            if Path(dest).exists():
                return
        except Exception:
            pass
        d2p = _find_bin("docx2pdf",
                        [HERE / "venv" / "Scripts" / "docx2pdf.exe"])
        if d2p:
            try:
                _run([d2p, str(src), str(dest)])
                if Path(dest).exists():
                    return
            except ConversionError:
                pass
    raise NoPdfEngineError("no LibreOffice or MS Word found")


def _venv_python():
    py = HERE / "venv" / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
    return py if py.exists() else None


def _simple_md_pdf(src_md, dest, theme):
    """Last-resort md -> pdf via the built-in pure-Python renderer."""
    try:
        import simple_pdf  # importable in the frozen exe / dev checkout
        simple_pdf.render(str(src_md), str(dest), theme)
        return
    except ImportError:
        pass
    py = _venv_python()
    script = HERE / "simple_pdf.py"
    if not script.exists():
        script = HERE / "simple_pdf.pyc"
    if py and script.exists():
        _run([str(py), str(script), str(src_md), str(dest), theme])
        return
    raise ConversionError(
        "No PDF engine found. Install LibreOffice"
        + (" or MS Word." if IS_WINDOWS else ":\nsudo apt install libreoffice-writer"))


SIMPLE_PDF_NOTE = ("LibreOffice/Word not found — used the built-in "
                   "simple PDF engine (basic styling).")


def _docx_to_md(src, dest):
    media_dir = f"{dest.stem}_media"
    _run([_pandoc_bin(), str(src), "-t", "gfm", "--wrap=none",
          f"--extract-media={media_dir}", "-o", str(dest.name)],
         cwd=str(dest.parent))
    # remove the media dir if the document had no images
    md = dest.parent / media_dir
    if md.exists() and not any(md.rglob("*.*")):
        shutil.rmtree(md, ignore_errors=True)


def _pdf_to_md(src, dest):
    """Returns a note string ('' if clean conversion)."""
    installer = "install-windows.bat" if IS_WINDOWS else "install.sh"
    if getattr(sys, "frozen", False):
        # markitdown is bundled as a library inside the frozen exe
        try:
            from markitdown import MarkItDown
            text = MarkItDown().convert(str(src)).text_content
            Path(dest).write_text(text, encoding="utf-8")
            return ""
        except ImportError:
            pass
    mid = _markitdown_bin()
    if mid:
        _run([mid, str(src), "-o", str(dest)])
        return ""
    if shutil.which("pdftotext"):
        _run(["pdftotext", "-layout", str(src), str(dest)])
        return (f"markitdown is not installed (run {installer}) — "
                "used basic text extraction instead.")
    # last resort: pdfminer (ships with markitdown's venv / frozen exe)
    extract = ("import sys; from pdfminer.high_level import extract_text; "
               "open(sys.argv[2], 'w', encoding='utf-8')"
               ".write(extract_text(sys.argv[1]) or '')")
    try:
        from pdfminer.high_level import extract_text
        Path(dest).write_text(extract_text(str(src)) or "", encoding="utf-8")
        return "used basic text extraction (pdfminer)."
    except ImportError:
        pass
    py = _venv_python()
    if py:
        _run([str(py), "-c", extract, str(src), str(dest)])
        return "used basic text extraction (pdfminer)."
    raise ConversionError(
        f"PDF reading needs markitdown. Run {installer} to set it up.")


def convert(src, out_format, theme="elegant"):
    """Convert src to out_format. Returns (output_path, note)."""
    src = Path(src).resolve()
    if not src.exists():
        raise ConversionError(f"File not found: {src}")
    kind = input_kind(src)
    if kind is None:
        raise ConversionError("Unsupported input type. "
                              "Use .md, .docx or .pdf files.")
    if not any(f == out_format for f, _ in OUTPUTS_FOR[kind]):
        raise ConversionError(f"Can't convert {kind} to {out_format}.")

    dest = unique_path(src.parent, src.stem, f".{out_format}")
    note = ""

    if kind == "md" and out_format == "docx":
        _md_to_docx(src, dest, theme)
    elif kind == "md" and out_format == "pdf":
        try:
            with tempfile.TemporaryDirectory(prefix="mdconv-") as tmp:
                tmp_docx = Path(tmp) / (src.stem + ".docx")
                _md_to_docx(src, tmp_docx, theme)
                _docx_to_pdf(tmp_docx, dest)
        except NoPdfEngineError:
            _simple_md_pdf(src, dest, theme)
            note = SIMPLE_PDF_NOTE
    elif kind == "docx" and out_format == "pdf":
        try:
            _docx_to_pdf(src, dest)
        except NoPdfEngineError:
            with tempfile.TemporaryDirectory(prefix="mdconv-") as tmp:
                tmp_md = Path(tmp) / (src.stem + ".md")
                _run([_pandoc_bin(), str(src), "-t", "gfm", "--wrap=none",
                      "-o", str(tmp_md)], cwd=tmp)
                _simple_md_pdf(tmp_md, dest, theme)
            note = SIMPLE_PDF_NOTE
    elif kind == "docx" and out_format == "md":
        _docx_to_md(src, dest)
    elif kind == "pdf" and out_format == "md":
        note = _pdf_to_md(src, dest)
    elif kind == "pdf" and out_format == "docx":
        with tempfile.TemporaryDirectory(prefix="mdconv-") as tmp:
            tmp_md = Path(tmp) / (src.stem + ".md")
            note = _pdf_to_md(src, tmp_md)
            _md_to_docx(tmp_md, dest, theme)

    if not dest.exists():
        raise ConversionError("Conversion produced no output file.")
    return dest, note


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("usage: converter.py <file> <docx|pdf|md> [theme]")
        sys.exit(1)
    out, note = convert(sys.argv[1], sys.argv[2],
                        sys.argv[3] if len(sys.argv) > 3 else "elegant")
    print(f"wrote {out}")
    if note:
        print(f"note: {note}")
