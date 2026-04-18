# niimbot-printer

![App icon](icon.png)

`favicon.png` is a 32×32 copy for static sites or browser tabs.

Desktop app to print **labels** on a **NIIMBOT B1** over USB serial, using the same packet protocol as [hairymnstr/niimctl](https://github.com/hairymnstr/niimctl). Optional logging records each successful print.

**Downloads:** GitHub **Releases** (after you push this repo) include Linux **AppImage** builds from CI when you tag a version (e.g. `v0.1.0`).

## Requirements

- Python 3.10+
- System packages often needed for wxPython wheels: GTK3, etc. (on Ubuntu: `python3-pip` and a desktop environment usually pull these in).
- USB serial access: user must be able to read/write the device (e.g. `dialout` group on GNU/Linux).

```bash
sudo usermod -aG dialout "$USER"
# then log out and back in
```

## Run from source

```bash
cd /path/to/niimbot-printer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m niimbot_printer
# or: niimbot-printer
```

Configuration is stored under XDG paths:

- `~/.config/niimbot-printer/config.json`
- `~/.local/share/niimbot-printer/state.json` (next sequence number)
- When logging is enabled, the audit file is always **`~/print.log`** (JSON Lines). The file is created automatically on first logged print.

If you used an older build, config may have lived under `~/.config/niimbot-welcome/`; copy or re-enter settings as needed.

### Bundled font

The default typeface is **Bitter** (Latin 600), bundled under `src/niimbot_printer/data/fonts/`.  
Copyright 2011 The Bitter Project Authors (https://github.com/solmatas/Bitter).  
Licensed under the **SIL Open Font License, Version 1.1** — see `src/niimbot_printer/data/fonts/OFL.txt`.

You can override it in **Settings** with any TTF/OTF path.

### Log format (JSONL)

Each line is one JSON object, for example:

```json
{"ts":"2026-04-18T14:30:00Z","name":"Ada Lovelace","seq":12,"source":"manual","pretix_event_slug":null,"pretix_order_code":null,"pretix_position_id":null}
```

The `name` field holds the printed text line. Logging is **on by default**; disable it in **File → Settings** if you do not want content written to disk.

## Packaging (PyInstaller + AppImage)

Build a windowed binary folder with PyInstaller:

```bash
pip install -e ".[dev]"
pyinstaller packaging/pyinstaller.spec
```

The runnable is `dist/niimbot-printer/niimbot-printer`. The spec bundles the `data/fonts` directory for the default Bitter font.

Wrap that folder as an AppImage (install `appimagetool` first):

```bash
chmod +x packaging/build-appimage.sh
./packaging/build-appimage.sh
```

This produces `dist/NIIMBOT-Printer-<version>-<arch>.AppImage` when `appimagetool` is available, or leaves a ready-to-use `build/AppDir` if it is not.

For widest Linux compatibility, build on the **oldest** distro you intend to support (glibc on the build machine sets the floor).

## Settings

- **Serial port** — e.g. `/dev/ttyACM0` (refresh lists USB serial devices when available).
- **Font file** — optional; empty uses bundled Bitter. Bold prefers a `*-Bold.ttf` next to the chosen file or common system bold fonts.
- **Label width / height** — default 384×240 pixels (width must be a multiple of 8).
- **Density / label type** — match niimctl defaults (3 and 1); adjust if your media requires it.
- **Logging** — toggle only; path is always `~/print.log` when enabled.

## License

This project is licensed under the GNU General Public License v3.0 or later.
