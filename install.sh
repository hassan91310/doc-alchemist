#!/usr/bin/env bash
# Doc Alchemist installer for Linux Mint / Ubuntu.
# - installs system deps (pandoc, GTK, LibreOffice Writer, venv support)
# - creates a local venv with markitdown (for PDF -> Markdown)
# - adds the app to your applications menu
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"

echo "==> Installing system packages (needs your sudo password)..."
sudo apt-get update -qq
sudo apt-get install -y pandoc python3-gi gir1.2-gtk-3.0 \
    libreoffice-writer python3-venv python3-pip poppler-utils

echo "==> Setting up Python environment for markitdown..."
if [ ! -x venv/bin/pip ]; then
    python3 -m venv --system-site-packages venv
fi
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet 'markitdown[pdf,docx]'

echo "==> Regenerating document themes..."
python3 make_themes.py

echo "==> Installing menu entry..."
mkdir -p ~/.local/share/applications
sed "s|__DIR__|$DIR|g" doc-alchemist.desktop \
    > ~/.local/share/applications/doc-alchemist.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true

echo
echo "Done! Find 'Doc Alchemist' in your menu (Office),"
echo "or run:  python3 $DIR/app.py"
