#!/usr/bin/env bash
# Build a GNU/Linux AppImage from a PyInstaller one-folder bundle.
# Prerequisites: Python venv with pyinstaller, wxPython, Pillow, pyserial;
# appimagetool on PATH ( https://github.com/AppImage/AppImageKit/releases ).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DIST_NAME="${DIST_NAME:-niimbot-printer}"
APPIMAGE_VARIANT="${APPIMAGE_VARIANT:-}"

if [[ ! -f "dist/${DIST_NAME}/niimbot-printer" ]]; then
  echo "Run PyInstaller first (executable must be at dist/${DIST_NAME}/niimbot-printer):"
  echo "  pip install -e '.[dev]'"
  echo "  pyinstaller packaging/pyinstaller.spec"
  echo "  # or: pyinstaller packaging/pyinstaller-minimal.spec && DIST_NAME=niimbot-printer-minimal $0"
  exit 1
fi

ARCH="$(uname -m)"
VERSION="${VERSION:-0.2.0}"
APPDIR="${ROOT}/build/AppDir"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" \
  "${APPDIR}/usr/share/icons/hicolor/256x256/apps" \
  "${APPDIR}/usr/share/icons/hicolor/128x128/apps" \
  "${APPDIR}/usr/share/icons/hicolor/48x48/apps" \
  "${APPDIR}/usr/share/icons/hicolor/32x32/apps"

cp -a "${ROOT}/dist/${DIST_NAME}/." "${APPDIR}/usr/bin/"

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
OUT_NAME="NIIMBOT-Printer-${VERSION}-${ARCH}"
if [[ -n "${APPIMAGE_VARIANT}" ]]; then
  OUT_NAME="${OUT_NAME}-${APPIMAGE_VARIANT}"
fi
appimagetool "${APPDIR}" "${ROOT}/dist/${OUT_NAME}.AppImage"
echo "Wrote dist/${OUT_NAME}.AppImage"
