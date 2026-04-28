<!-- markdownlint-disable MD033 MD041 -->
![App icon](icon.png)

# niimbot-printer

![GitHub Release](https://img.shields.io/github/v/release/ooguz/niimbot-printer) ![PyPI - Version](https://img.shields.io/pypi/v/niimbot-printer) [![Release AppImage](https://github.com/ooguz/niimbot-printer/actions/workflows/release-appimage.yml/badge.svg)](https://github.com/ooguz/niimbot-printer/actions/workflows/release-appimage.yml) <a href="https://www.buymeacoffee.com/ooguz" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 20px !important;width: 85px !important;" ></a>

Desktop app to print **labels** on a **NIIMBOT B1** over USB serial. Optional logging records each successful print.

The app can also integrate with [Pretix](https://pretix.eu) to check-in and print badges, see the section below.

**TLDR Downloads:** GitHub **Releases** include two GNU/Linux **AppImage** builds: `NIIMBOT-Printer-<version>-<arch>.AppImage` (standalone, no Pretix support) and `NIIMBOT-Printer-<version>-<arch>-pretix.AppImage` (with Pretix support).

## Screenshots

![Main window](assets/screenshot_main_screen.png)
![Settings](assets/screenshot_settings_screen.png)

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

The default typeface is **Bitter** (Latin Ext 600), bundled under `src/niimbot_printer/data/fonts/`.  
Copyright (c) 2011-2020, Sol Matas [www.solmatas.com](https://www.solmatas.com)
Licensed under the **SIL Open Font License, Version 1.1** — see `src/niimbot_printer/data/fonts/OFL.txt`.

You can override it in **Settings** with any TTF/OTF path.

### Log format (JSONL)

Each line is one JSON object, for example:

```json
{"ts":"2026-04-18T14:30:00Z","name":"Ada Lovelace","seq":12,"source":"manual","pretix_event_slug":null,"pretix_order_code":null,"pretix_position_id":null,"label_copies":2}
```

The `name` field holds the printed text line. Logging is **on by default**; disable it in **File → Settings** if you do not want content written to disk.

Successful **Pretix** prints set `source` to `"pretix"` and fill `pretix_event_slug`, `pretix_order_code`, and `pretix_position_id` when Pretix returns them.

## Pretix check-in (optional)

The app can call your [Pretix](https://pretix.eu) instance’s [check-in redeem API](https://docs.pretix.eu/en/latest/api/resources/checkin.html), check in a ticket from the scanned **secret**, then print a name badge. This is **off by default** and does not contact the network until you enable it in **Settings**.

1. In Pretix (organizer settings), create an **API token** with permission to manage check-ins for your events.
2. In **File → Settings**, under **Pretix (optional)**:
   - Enable **Pretix check-in and badge printing**.
   - **Pretix base URL** — HTTPS only, e.g. `https://kayit.oyd.org.tr` (no trailing slash). If Pretix lives under a subpath, include it (e.g. `https://host/pretix`).
   - **Organizer slug** — as in `https://…/org/<slug>/`.
   - **API token** — or leave empty and set environment variable `PRETIX_API_TOKEN` or `PRETX_TOKEN` (env wins over the saved field).
   - **Event slug** — used only by **Load lists** to query [check-in lists](https://docs.pretix.eu/en/latest/api/resources/checkinlists.html).
   - **Check-in list ID(s)** — comma-separated integers for the list(s) you scan against (use **Load lists** or copy IDs from Pretix admin).
   - **Badge text template** — Python `str.format` placeholders: `{attendee_name}`, `{company}`, `{order}`, `{item}`. Use a real newline in the field, or the two characters `\n` for a line break.
   - **Show and verify each Pretix label before printing** — after a successful check-in, a dialog shows the resolved text read-only; **Enter** confirms and prints (or use **Print label**). **Edit text** unlocks the field so you can fix typos before printing. **Cancel** skips printing (check-in already recorded in Pretix).

**QR / barcode:** USB scanners in keyboard mode usually type the ticket secret into the **Ticket secret** field; press **Enter** or click **Check in and print label**. Camera-based decoding is not included in the default build.

**“Load lists” returns HTTP 404 with an HTML “Not found” page:** Your Pretix server is almost certainly fine — that response is what the **obsolete** API path `/organizers/…/checkinlists/?event=…` returns. Update this app and reinstall (`pip install -e .` from the current tree) or use a freshly built **full** AppImage. The correct path is `/api/v1/organizers/{org}/events/{event}/checkinlists/` (see [check-in lists API](https://docs.pretix.eu/en/latest/api/resources/checkinlists.html)).

**Standalone / minimal build:** `packaging/pyinstaller-minimal.spec` excludes the Pretix package so the frozen app stays smaller; the Pretix panel is hidden and the status line notes that Pretix is unavailable. Use the main `packaging/pyinstaller.spec` (or the full AppImage from releases) for Pretix support.

## Packaging (PyInstaller + AppImage)

Build a windowed binary folder with PyInstaller:

```bash
pip install -e ".[dev]"
pyinstaller packaging/pyinstaller.spec
```

The runnable is `dist/niimbot-printer/niimbot-printer`. The spec bundles the `data/fonts` directory for the default Bitter font and includes **Pretix** integration.

For a **smaller bundle without Pretix**:

```bash
pyinstaller packaging/pyinstaller-minimal.spec
# runnable: dist/niimbot-printer-minimal/niimbot-printer
```

Wrap a bundle as an AppImage (install `appimagetool` first). Use a **plain** filename for the minimal bundle and **`APPIMAGE_VARIANT=pretix`** for the full bundle so local builds match release names:

```bash
chmod +x packaging/build-appimage.sh
# After pyinstaller packaging/pyinstaller-minimal.spec:
DIST_NAME=niimbot-printer-minimal ./packaging/build-appimage.sh
# After pyinstaller packaging/pyinstaller.spec:
APPIMAGE_VARIANT=pretix ./packaging/build-appimage.sh
```

This produces `dist/NIIMBOT-Printer-<version>-<arch>.AppImage` (standalone) and `dist/NIIMBOT-Printer-<version>-<arch>-pretix.AppImage` (with Pretix), or leaves a ready-to-use `build/AppDir` if `appimagetool` is not installed.

Release CI builds **both** AppImages when you push a version tag.

For widest GNU/Linux compatibility, build on the **oldest** distro you intend to support (glibc on the build machine sets the floor).

## Settings

- **Serial port** — e.g. `/dev/ttyACM0` (refresh lists USB serial devices when available).
- **Font file** — optional; empty uses bundled Bitter. Bold prefers a `*-Bold.ttf` next to the chosen file or common system bold fonts.
- **Label width / height** — default 384×240 pixels (width must be a multiple of 8).
- **Density / label type** — match niimctl defaults (3 and 1); adjust if your media requires it.
- **Labels per print** — how many identical labels to feed per print action (manual or Pretix); default 1. Jobs are sent in **one** USB serial session, with a short pause after the last job before closing USB, so every copy completes (closing the port immediately after the last command often drops the final label).
- **Logging** — toggle only; path is always `~/print.log` when enabled.
- **Pretix** — optional; see [Pretix check-in (optional)](#pretix-check-in-optional). The API token is stored in `config.json`; restrict file permissions on shared machines or prefer env vars.

## Thanks

- [hairymnstr/niimctl](https://github.com/hairymnstr/niimctl) for protocol reverse engineering

## License

Copyright (C) 2026 Özcan Oğuz

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
