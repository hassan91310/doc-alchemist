#!/usr/bin/env bash
# Build the Doc Alchemist .deb installer (compiled bytecode only, no source).
# Usage: ./build_deb.sh [version]
set -e
cd "$(dirname "$0")"
VERSION="${1:-1.0.0}"
PYV="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PKG="doc-alchemist"
ROOT="build/${PKG}_${VERSION}_all"

rm -rf build
mkdir -p "$ROOT/opt/doc-alchemist/assets" \
         "$ROOT/usr/bin" \
         "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" \
         "$ROOT/DEBIAN"

# --- app payload: byte-compiled only -----------------------------------------
python3 -m compileall -b -q app.py converter.py
mv app.pyc converter.pyc "$ROOT/opt/doc-alchemist/"
cp -r themes "$ROOT/opt/doc-alchemist/themes"
rm -f "$ROOT/opt/doc-alchemist/themes/_base_reference.docx"
cp assets/icon.svg "$ROOT/opt/doc-alchemist/assets/"
cp assets/icon.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/doc-alchemist.svg"

# --- launcher ------------------------------------------------------------------
cat > "$ROOT/usr/bin/doc-alchemist" <<EOF
#!/bin/sh
exec /usr/bin/python${PYV} /opt/doc-alchemist/app.pyc "\$@"
EOF
chmod 755 "$ROOT/usr/bin/doc-alchemist"

# --- menu entry ------------------------------------------------------------------
cat > "$ROOT/usr/share/applications/doc-alchemist.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Doc Alchemist
Comment=Convert Markdown, Word and PDF documents with beautiful themes
Exec=doc-alchemist
Icon=doc-alchemist
Terminal=false
Categories=Office;Utility;
Keywords=markdown;docx;pdf;convert;pandoc;
StartupNotify=true
EOF

# --- package metadata ---------------------------------------------------------------
cat > "$ROOT/DEBIAN/control" <<EOF
Package: ${PKG}
Version: ${VERSION}
Section: office
Priority: optional
Architecture: all
Depends: python${PYV}, python${PYV}-venv, python3-gi, gir1.2-gtk-3.0, pandoc, libreoffice-writer, poppler-utils
Maintainer: Hassan Ali <hassan.butt1752000@gmail.com>
Description: Convert Markdown, Word and PDF documents with beautiful themes
 Doc Alchemist converts Markdown to styled Word/PDF documents and back,
 using pandoc, LibreOffice and markitdown. Includes three built-in
 document themes (Elegant, Modern, Minimal).
EOF

cat > "$ROOT/DEBIAN/postinst" <<EOF
#!/bin/sh
set -e
# markitdown lives in a private venv (best PDF -> Markdown quality)
if [ ! -x /opt/doc-alchemist/venv/bin/markitdown ]; then
    echo "Setting up markitdown (PDF support)..."
    python${PYV} -m venv /opt/doc-alchemist/venv 2>/dev/null && \
    /opt/doc-alchemist/venv/bin/pip install --quiet 'markitdown[pdf,docx]' || \
    echo "Warning: markitdown setup failed (no network?). PDF -> Markdown will use basic text extraction."
fi
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q /usr/share/icons/hicolor || true
exit 0
EOF
chmod 755 "$ROOT/DEBIAN/postinst"

cat > "$ROOT/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    rm -rf /opt/doc-alchemist/venv
    rmdir /opt/doc-alchemist 2>/dev/null || true
fi
exit 0
EOF
chmod 755 "$ROOT/DEBIAN/postrm"

dpkg-deb --build --root-owner-group "$ROOT" "build/${PKG}_${VERSION}_all.deb" >/dev/null
echo "built build/${PKG}_${VERSION}_all.deb"