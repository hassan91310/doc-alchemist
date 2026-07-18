#!/usr/bin/env python3
"""Update & dependency checks for Doc Alchemist.

The packaged builds (Windows exe / Linux deb) ship an app_info.json
next to the app with the version and the GitHub repo that hosts
releases; it is written at build time by release.yml / build_deb.sh.
Running from a source checkout reports "dev" and skips the app check.

Only the standard library is used, so this works the same in the
frozen exe, the deb and a dev checkout.
"""
import json
import re
import subprocess
import sys
from urllib.request import Request, urlopen

import converter

TIMEOUT = 10
_HEADERS = {"User-Agent": "DocAlchemist-update-check"}


def _app_info():
    try:
        return json.loads((converter.HERE / "app_info.json")
                          .read_text(encoding="utf-8"))
    except Exception:
        return {}


_INFO = _app_info()
APP_VERSION = _INFO.get("version") or "dev"
RELEASE_REPO = _INFO.get("repo") or None


def _get_json(url):
    with urlopen(Request(url, headers=_HEADERS), timeout=TIMEOUT) as r:
        return json.load(r)


def _vtuple(v):
    return tuple(int(n) for n in re.findall(r"\d+", v or "")[:4]) or (0,)


def _newer(latest, current):
    return bool(latest and current) and _vtuple(latest) > _vtuple(current)


# --- app update ---------------------------------------------------------------

def check_app_update():
    """Returns {status: ok|update|dev|error, message, [latest, url]}."""
    if APP_VERSION == "dev":
        return {"status": "dev",
                "message": "Running from source — the update check "
                           "applies to installed builds only."}
    if not RELEASE_REPO:
        return {"status": "error",
                "message": "This build doesn't know its release page."}
    try:
        rel = _get_json(
            f"https://api.github.com/repos/{RELEASE_REPO}/releases/latest")
    except Exception:
        return {"status": "error",
                "message": "Couldn't reach GitHub to check for updates. "
                           "Are you online?"}
    latest = (rel.get("tag_name") or "").lstrip("v")
    if _newer(latest, APP_VERSION):
        return {"status": "update", "latest": latest,
                "url": rel.get("html_url"),
                "message": f"Version {latest} is available "
                           f"(you have {APP_VERSION})."}
    return {"status": "ok",
            "message": f"Doc Alchemist {APP_VERSION} is up to date."}


# --- dependencies -------------------------------------------------------------

def _cmd_version(cmd):
    """First x.y… number in a --version output, or None."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20,
                           **converter.POPEN_FLAGS)
        m = re.search(r"\d+\.\d+[\d.]*", (r.stdout or "") + (r.stderr or ""))
        return m.group(0) if m else None
    except Exception:
        return None


def _markitdown_version():
    try:
        from importlib.metadata import version
        return version("markitdown")
    except Exception:
        pass
    py = converter._venv_python()
    if py:
        try:
            r = subprocess.run(
                [str(py), "-c", "from importlib.metadata import version; "
                                "print(version('markitdown'))"],
                capture_output=True, text=True, timeout=20,
                **converter.POPEN_FLAGS)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return None


def _dep(name, found, installed, latest, note=""):
    if not found:
        status = "missing"
    elif _newer(latest, installed):
        status = "outdated"
    elif latest and installed:
        status = "ok"
    else:
        status = "installed"   # present, but no version info to compare
    return {"name": name, "installed": installed, "latest": latest,
            "status": status, "note": note}


def check_dependencies():
    """Returns a list of dep dicts (see _dep) for the external tools."""
    deps = []

    try:
        pandoc = converter._pandoc_bin()
    except converter.ConversionError:
        pandoc = None
    try:
        latest = _get_json("https://api.github.com/repos/jgm/pandoc/"
                           "releases/latest").get("tag_name", "").lstrip("v")
    except Exception:
        latest = None
    note = "" if pandoc else (
        "required — winget install JohnMacFarlane.Pandoc"
        if converter.IS_WINDOWS else "required — sudo apt install pandoc")
    deps.append(_dep("pandoc", bool(pandoc),
                     _cmd_version([pandoc, "--version"]) if pandoc else None,
                     latest, note))

    soffice = converter._soffice_bin()
    deps.append(_dep(
        "LibreOffice", bool(soffice),
        _cmd_version([soffice, "--version"]) if soffice else None, None,
        "" if soffice else "optional — used for high-quality PDF export"))

    mi_ver = _markitdown_version()
    mi_found = mi_ver is not None or converter._markitdown_bin() is not None
    try:
        latest = _get_json(
            "https://pypi.org/pypi/markitdown/json")["info"]["version"]
    except Exception:
        latest = None
    d = _dep("markitdown", mi_found, mi_ver, latest,
             "" if mi_found else "optional — used for PDF → Markdown")
    if d["status"] == "outdated":
        d["note"] = ("bundled — updated with new app releases"
                     if getattr(sys, "frozen", False)
                     else "update: venv pip install -U \"markitdown[pdf,docx]\"")
    deps.append(d)
    return deps


def describe(dep):
    """One-line human summary of a dep dict, note on a second line."""
    if dep["status"] == "missing":
        s = "not installed"
    elif dep["status"] == "outdated":
        s = f"{dep['installed']} — {dep['latest']} available"
    elif dep["status"] == "ok":
        s = f"{dep['installed']} — up to date"
    else:
        s = dep["installed"] or "installed"
    if dep["note"]:
        s += f"\n{dep['note']}"
    return s


if __name__ == "__main__":
    # legacy Windows consoles can't print unicode arrows/dashes
    sys.stdout.reconfigure(errors="replace")
    app = check_app_update()
    print(f"app: {app['message']}")
    for d in check_dependencies():
        print(f"{d['name']}: " + describe(d).replace("\n", " — "))
