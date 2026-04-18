"""About dialog — edit the constants below, then commit."""

from __future__ import annotations

from pathlib import Path

import wx

from niimbot_printer import __version__
from niimbot_printer import resources

# --- Customize before release (then: git add this file + gui.py and commit) ---
APP_DISPLAY_NAME = "NIIMBOT Printer"

DEVELOPER = "Özcan Oğuz <ozcan@oyd.org.tr>"

HOMEPAGE_URL = "https://github.com/ooguz/niimbot-printer"

SUPPORT_URL = "https://buymeacoffee.com/ooguz"

LICENSE_NAME = "GNU General Public License v3.0 or later"

DESCRIPTION = (
    "Print name labels on a NIIMBOT B1 over USB serial.\n"
    "Optional Pretix check-in integration."
)

_ABOUT_ICON_MAX = 128


def _about_bitmap(path: Path | str) -> wx.Bitmap | None:
    img = wx.Image(str(path), wx.BITMAP_TYPE_PNG)
    if not img.IsOk():
        return None
    w, h = img.GetWidth(), img.GetHeight()
    m = max(w, h)
    if m > _ABOUT_ICON_MAX and m > 0:
        r = _ABOUT_ICON_MAX / m
        img = img.Scale(int(w * r), int(h * r), wx.IMAGE_QUALITY_HIGH)
    return wx.Bitmap(img)


def show_about_dialog(parent: wx.Window | None) -> None:
    try:
        import wx.adv
    except ImportError:
        text = (
            f"{APP_DISPLAY_NAME} {__version__}\n\n{DESCRIPTION}\n\n"
            f"Developer: {DEVELOPER}\n\n{resources.gpl_license_full_text()}\n\n"
            f"{HOMEPAGE_URL}\n{SUPPORT_URL}"
        )
        wx.MessageBox(text, f"About {APP_DISPLAY_NAME}", wx.OK | wx.ICON_INFORMATION, parent)
        return

    dlg = wx.Dialog(
        parent,
        title=f"About {APP_DISPLAY_NAME}",
        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        size=(560, 520),
    )
    icon_path = resources.app_icon_path()
    if icon_path is not None:
        ic = wx.Icon(str(icon_path), wx.BITMAP_TYPE_PNG)
        if ic.IsOk():
            dlg.SetIcon(ic)
    root = wx.BoxSizer(wx.VERTICAL)
    top = wx.BoxSizer(wx.HORIZONTAL)

    if icon_path is not None:
        bmp = _about_bitmap(icon_path)
        if bmp is not None and bmp.IsOk():
            top.Add(wx.StaticBitmap(dlg, bitmap=bmp), 0, wx.ALL, 12)

    text_col = wx.BoxSizer(wx.VERTICAL)
    title = wx.StaticText(dlg, label=APP_DISPLAY_NAME)
    title_font = title.GetFont()
    title_font.SetPointSize(title_font.GetPointSize() + 4)
    title_font.SetWeight(wx.FONTWEIGHT_BOLD)
    title.SetFont(title_font)
    text_col.Add(title, 0, wx.BOTTOM, 4)

    text_col.Add(wx.StaticText(dlg, label=f"Version {__version__}"), 0, wx.BOTTOM, 8)
    text_col.Add(wx.StaticText(dlg, label=DESCRIPTION), 0, wx.BOTTOM, 8)
    text_col.Add(wx.StaticText(dlg, label=f"© {DEVELOPER}"), 0, wx.BOTTOM, 8)

    link_row = wx.BoxSizer(wx.HORIZONTAL)
    link_git = wx.adv.HyperlinkCtrl(dlg, wx.ID_ANY, "Source on GitHub", HOMEPAGE_URL)
    link_bmc = wx.adv.HyperlinkCtrl(dlg, wx.ID_ANY, "Buy me a coffee", SUPPORT_URL)
    link_row.Add(link_git, 0, wx.RIGHT, 16)
    link_row.Add(link_bmc, 0)
    text_col.Add(link_row, 0, wx.BOTTOM, 12)

    top.Add(text_col, 1, wx.EXPAND | wx.TOP | wx.RIGHT, 12)
    root.Add(top, 0, wx.EXPAND)

    lic_lbl = wx.StaticText(dlg, label=LICENSE_NAME)
    lic_font = lic_lbl.GetFont()
    lic_font.SetWeight(wx.FONTWEIGHT_BOLD)
    lic_lbl.SetFont(lic_font)
    root.Add(lic_lbl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

    lic_body = wx.TextCtrl(
        dlg,
        value=resources.gpl_license_full_text(),
        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_SUNKEN,
    )
    lic_body.SetMinSize((520, 220))
    root.Add(lic_body, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)

    btn_row = wx.BoxSizer(wx.HORIZONTAL)
    btn_row.AddStretchSpacer(1)
    ok = wx.Button(dlg, wx.ID_OK, label="Close")
    ok.SetDefault()
    btn_row.Add(ok, 0, wx.ALL, 8)
    root.Add(btn_row, 0, wx.EXPAND)

    dlg.SetSizer(root)
    dlg.Layout()
    dlg.CentreOnParent()
    dlg.ShowModal()
    dlg.Destroy()
