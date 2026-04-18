#!/usr/bin/env bash
# Build a Linux AppImage from a PyInstaller one-folder bundle.
# Prerequisites: Python venv with pyinstaller, wxPython, Pillow, pyserial;
# appimagetool on PATH ( https://github.com/AppImage/AppImageKit/releases ).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f dist/niimbot-printer/niimbot-printer ]]; then
  echo "Run PyInstaller first:"
  echo "  pip install -e '.[dev]'"
  echo "  pyinstaller packaging/pyinstaller.spec"
  exit 1
fi

ARCH="$(uname -m)"
VERSION="${VERSION:-0.1.0}"
APPDIR="${ROOT}/build/AppDir"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" \
  "${APPDIR}/usr/share/icons/hicolor/256x256/apps" \
  "${APPDIR}/usr/share/icons/hicolor/128x128/apps" \
  "${APPDIR}/usr/share/icons/hicolor/48x48/apps" \
  "${APPDIR}/usr/share/icons/hicolor/32x32/apps"

cp -a "${ROOT}/dist/niimbot-printer/." "${APPDIR}/usr/bin/"

cp "${ROOT}/packaging/niimbot-printer.desktop" "${APPDIR}/usr/share/applications/"

ICON_SRC="${ROOT}/src/niimbot_printer/data/icon.png"
if [[ ! -f "${ICON_SRC}" ]]; then
  ICON_SRC="${ROOT}/icon.png"
fi
if [[ -f "${ICON_SRC}" ]]; then
  cp "${ICON_SRC}" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/niimbot-printer.png"
  cp "${ICON_SRC}" "${APPDIR}/usr/share/icons/hicolor/128x128/apps/niimbot-printer.png"
  cp "${ICON_SRC}" "${APPDIR}/usr/share/icons/hicolor/48x48/apps/niimbot-printer.png"
  cp "${ICON_SRC}" "${APPDIR}/usr/share/icons/hicolor/32x32/apps/niimbot-printer.png"
else
  echo "Warning: no icon.png; desktop integration may miss an icon"
  touch "${APPDIR}/usr/share/icons/hicolor/256x256/apps/niimbot-printer.png"
fi

ln -sf "usr/share/applications/niimbot-printer.desktop" "${APPDIR}/niimbot-printer.desktop"
ln -sf "usr/share/icons/hicolor/256x256/apps/niimbot-printer.png" "${APPDIR}/niimbot-printer.png"

cat > "${APPDIR}/AppRun" << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/niimbot-printer" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

if ! command -v appimagetool >/dev/null 2>&1; then
  echo "appimagetool not found; AppDir ready at ${APPDIR}"
  echo "Install from https://github.com/AppImage/AppImageKit/releases"
  exit 0
fi

export ARCH
appimagetool "${APPDIR}" "${ROOT}/dist/NIIMBOT-Printer-${VERSION}-${ARCH}.AppImage"
echo "Wrote dist/NIIMBOT-Printer-${VERSION}-${ARCH}.AppImage"
