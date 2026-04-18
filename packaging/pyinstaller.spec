# -*- mode: python ; coding: utf-8 -*-
# Run from repo root: pyinstaller packaging/pyinstaller.spec

import os

block_cipher = None
spec_dir = os.path.dirname(os.path.abspath(SPEC))
root = os.path.dirname(spec_dir)
src = os.path.join(root, "src")
font_dir = os.path.join(root, "src", "niimbot_printer", "data", "fonts")
icon_pkg = os.path.join(root, "src", "niimbot_printer", "data", "icon.png")
icon_png = os.path.join(root, "icon.png")
icon_arg = icon_png if os.path.isfile(icon_png) else None

datas_list = [(font_dir, "niimbot_printer/data/fonts")]
if os.path.isfile(icon_pkg):
    datas_list.append((icon_pkg, "niimbot_printer/data"))
license_file = os.path.join(root, "LICENSE")
if os.path.isfile(license_file):
    datas_list.append((license_file, "niimbot_printer/data"))

a = Analysis(
    [os.path.join(spec_dir, "entry.py")],
    pathex=[src],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        "niimbot_printer.app",
        "niimbot_printer.gui",
        "niimbot_printer.printer",
        "niimbot_printer.renderer",
        "niimbot_printer.settings",
        "niimbot_printer.resources",
        "niimbot_printer.audit_log",
        "niimbot_printer.pretix",
        "niimbot_printer.pretix.client",
        "niimbot_printer.pretix.parse_secret",
        "niimbot_printer.pretix.badge_text",
        "serial.tools.list_ports",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="niimbot-printer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_arg,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="niimbot-printer",
)
