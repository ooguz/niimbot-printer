"""wxPython main window and settings dialog."""

from __future__ import annotations

import importlib
import threading
import traceback
from dataclasses import replace

import wx

from niimbot_printer import audit_log, printer, renderer, resources, settings

__all__ = ["MainFrame", "SettingsDialog", "run_app"]


def _pretix_module_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("niimbot_printer.pretix.client") is not None


def _parse_list_ids_field(s: str) -> list[int]:
    out: list[int] = []
    for part in s.replace(";", ",").split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.append(int(p))
        except ValueError:
            continue
    return out


def _pretix_failure_message(data: dict) -> str:
    status = data.get("status")
    if status == "incomplete":
        return (
            "Check-in incomplete: Pretix expects answers to check-in questions. "
            "Change the check-in list in Pretix or enable question handling in a future version."
        )
    if status == "error":
        reason = str(data.get("reason") or "unknown")
        expl = (data.get("reason_explanation") or "").strip()
        friendly = {
            "already_redeemed": "This ticket has already been checked in.",
            "invalid": "Invalid or unknown ticket.",
            "canceled": "This order has been canceled.",
            "unpaid": "Order is not paid.",
            "revoked": "This ticket has been revoked.",
            "blocked": "This ticket is blocked.",
            "ambiguous": "Multiple matching tickets; narrow check-in lists in Settings.",
            "rules": "Check-in rules blocked this ticket.",
            "incomplete": "Order or attendee data is incomplete.",
            "product": "Product rules prevent check-in.",
            "unapproved": "Order is not approved yet.",
            "invalid_time": "Check-in is not allowed at this time.",
        }.get(reason, "")
        base = friendly or f"Pretix error ({reason})."
        if expl:
            return f"{base}\n{expl}"
        return base
    return f"Unexpected Pretix response: {data!r}"


def _set_frame_icon(frame: wx.Frame) -> None:
    path = resources.app_icon_path()
    if path is None:
        return
    icon = wx.Icon(str(path), wx.BITMAP_TYPE_PNG)
    if icon.IsOk():
        frame.SetIcon(icon)


class SettingsDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, cfg: settings.AppSettings):
        super().__init__(parent, title="Settings", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._cfg = cfg
        self._result: settings.AppSettings | None = None

        main = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(0, 2, 8, 8)
        grid.AddGrowableCol(1, 1)

        grid.Add(wx.StaticText(self, label="Serial port:"), 0, wx.ALIGN_CENTER_VERTICAL)
        port_row = wx.BoxSizer(wx.HORIZONTAL)
        self.port_combo = wx.ComboBox(self, style=wx.CB_DROPDOWN)
        self._refresh_ports(select=cfg.serial_port)
        port_row.Add(self.port_combo, 1, wx.EXPAND)
        btn_refresh = wx.Button(self, label="Refresh")
        btn_refresh.Bind(wx.EVT_BUTTON, self._on_refresh_ports)
        port_row.Add(btn_refresh, 0, wx.LEFT, 6)
        grid.Add(port_row, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Font file (optional):"), 0, wx.ALIGN_CENTER_VERTICAL)
        font_row = wx.BoxSizer(wx.HORIZONTAL)
        self.font_path = wx.TextCtrl(self, value=cfg.font_path)
        font_row.Add(self.font_path, 1, wx.EXPAND)
        btn_font = wx.Button(self, label="Browse…")
        btn_font.Bind(wx.EVT_BUTTON, self._on_browse_font)
        font_row.Add(btn_font, 0, wx.LEFT, 6)
        grid.Add(font_row, 1, wx.EXPAND)
        grid.Add(wx.StaticText(self, label=""), 0)
        grid.Add(
            wx.StaticText(
                self,
                label="Leave empty to use bundled Bitter (SIL Open Font License 1.1).",
            ),
            0,
            wx.EXPAND,
        )

        grid.Add(wx.StaticText(self, label="Font size:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.font_size = wx.SpinCtrl(self, min=8, max=200, initial=cfg.font_size)
        grid.Add(self.font_size, 0, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Bold:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.bold = wx.CheckBox(self, label="Prefer bold variant when available")
        self.bold.SetValue(cfg.bold)
        grid.Add(self.bold, 0, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Label width (px):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.width_px = wx.SpinCtrl(self, min=8, max=400, initial=cfg.label_width_px)
        grid.Add(self.width_px, 0, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Label height (px):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.height_px = wx.SpinCtrl(self, min=16, max=2000, initial=cfg.label_height_px)
        grid.Add(self.height_px, 0, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Density (1–5):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.density = wx.SpinCtrl(self, min=1, max=5, initial=cfg.density)
        grid.Add(self.density, 0, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Label type (1–3):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.label_type = wx.SpinCtrl(self, min=1, max=3, initial=cfg.label_type)
        grid.Add(self.label_type, 0, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Logging:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.logging_on = wx.CheckBox(
            self,
            label="Log each print to ~/print.log (JSON Lines: time, name, seq, …)",
        )
        self.logging_on.SetValue(cfg.logging_enabled)
        grid.Add(self.logging_on, 0, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Debug serial:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.debug_serial = wx.CheckBox(self, label="Print protocol debug to stderr")
        self.debug_serial.SetValue(cfg.debug_serial)
        grid.Add(self.debug_serial, 0, wx.EXPAND)

        main.Add(grid, 0, wx.ALL | wx.EXPAND, 12)

        pretix_box = wx.StaticBox(self, label="Pretix (optional)")
        pretix_sz = wx.StaticBoxSizer(pretix_box, wx.VERTICAL)
        pgrid = wx.FlexGridSizer(0, 2, 8, 8)
        pgrid.AddGrowableCol(1, 1)

        self.pretix_enabled = wx.CheckBox(self, label="Enable Pretix check-in and badge printing")
        self.pretix_enabled.SetValue(cfg.pretix_enabled)
        pgrid.Add(self.pretix_enabled, 0, wx.EXPAND)
        pgrid.Add(wx.StaticText(self, label=""), 0)

        pgrid.Add(wx.StaticText(self, label="Pretix base URL:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pretix_base_url = wx.TextCtrl(self, value=cfg.pretix_base_url)
        self.pretix_base_url.SetHint("https://kayit.oyd.org.tr")
        pgrid.Add(self.pretix_base_url, 0, wx.EXPAND)

        pgrid.Add(wx.StaticText(self, label="Organizer slug:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pretix_organizer = wx.TextCtrl(self, value=cfg.pretix_organizer_slug)
        pgrid.Add(self.pretix_organizer, 0, wx.EXPAND)

        pgrid.Add(wx.StaticText(self, label="API token:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pretix_token = wx.TextCtrl(self, value=cfg.pretix_api_token, style=wx.TE_PASSWORD)
        pgrid.Add(self.pretix_token, 0, wx.EXPAND)

        pgrid.Add(wx.StaticText(self, label=""), 0)
        pgrid.Add(
            wx.StaticText(
                self,
                label="Token can be set via env PRETIX_API_TOKEN or PRETX_TOKEN instead of saving here.",
            ),
            0,
            wx.EXPAND,
        )

        pgrid.Add(wx.StaticText(self, label="Event slug:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pretix_event = wx.TextCtrl(self, value=cfg.pretix_event_slug)
        self.pretix_event.SetHint("Used by “Load lists” only")
        pgrid.Add(self.pretix_event, 0, wx.EXPAND)

        pgrid.Add(wx.StaticText(self, label="Check-in list ID(s):"), 0, wx.ALIGN_CENTER_VERTICAL)
        list_row = wx.BoxSizer(wx.HORIZONTAL)
        ids_display = ", ".join(str(i) for i in cfg.pretix_checkin_list_ids)
        self.pretix_list_ids = wx.TextCtrl(self, value=ids_display)
        self.pretix_list_ids.SetHint("Comma-separated, e.g. 1 or 1, 2")
        list_row.Add(self.pretix_list_ids, 1, wx.EXPAND)
        self.pretix_load_lists = wx.Button(self, label="Load lists")
        self.pretix_load_lists.Bind(wx.EVT_BUTTON, self._on_load_checkin_lists)
        list_row.Add(self.pretix_load_lists, 0, wx.LEFT, 6)
        pgrid.Add(list_row, 1, wx.EXPAND)

        pgrid.Add(wx.StaticText(self, label="Badge text template:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pretix_badge_tpl = wx.TextCtrl(self, value=cfg.pretix_badge_template)
        self.pretix_badge_tpl.SetHint("{attendee_name} or {attendee_name}\\n{company}")
        pgrid.Add(self.pretix_badge_tpl, 0, wx.EXPAND)

        pretix_sz.Add(pgrid, 0, wx.ALL | wx.EXPAND, 8)
        main.Add(pretix_sz, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)

        pretix_avail = _pretix_module_available()
        if not pretix_avail:
            self.pretix_load_lists.Enable(False)
            self.pretix_load_lists.SetToolTip("This build does not include the Pretix module.")

        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(self, wx.ID_OK)
        ok.SetDefault()
        btns.AddButton(ok)
        btns.AddButton(wx.Button(self, wx.ID_CANCEL))
        btns.Realize()
        main.Add(btns, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.SetSizer(main)
        self.Fit()
        min_w = 600
        self.SetSizeHints(min_w, -1)
        self.SetClientSize(self.GetBestSize().Width, self.GetBestSize().Height)

        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        _set_frame_icon(self)

    def _refresh_ports(self, select: str | None = None) -> None:
        self.port_combo.Clear()
        ports = settings.list_serial_ports()
        chosen = -1
        for i, (dev, desc) in enumerate(ports):
            label = f"{dev}" + (f" — {desc}" if desc else "")
            self.port_combo.Append(label, dev)
            if select and dev == select:
                chosen = i
        if self.port_combo.IsEmpty() and select:
            self.port_combo.Append(select, select)
            chosen = 0
        if chosen >= 0:
            self.port_combo.SetSelection(chosen)
        elif self.port_combo.GetCount() > 0:
            self.port_combo.SetSelection(0)

    def _on_refresh_ports(self, _evt: wx.CommandEvent) -> None:
        cur = self._current_port_device()
        self._refresh_ports(select=cur)

    def _current_port_device(self) -> str | None:
        idx = self.port_combo.GetSelection()
        if idx != wx.NOT_FOUND:
            dev = self.port_combo.GetClientData(idx)
            if dev is not None:
                return str(dev)
        typed = self.port_combo.GetValue().strip()
        return typed or None

    def _on_browse_font(self, _evt: wx.CommandEvent) -> None:
        with wx.FileDialog(
            self,
            "Choose font",
            wildcard="Font files (*.ttf;*.otf)|*.ttf;*.otf|All files|*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            self.font_path.SetValue(dlg.GetPath())

    def _on_load_checkin_lists(self, _evt: wx.CommandEvent) -> None:
        if not _pretix_module_available():
            wx.MessageBox(
                "This application build does not include Pretix support.",
                "Pretix",
                wx.OK | wx.ICON_INFORMATION,
            )
            return
        import os

        base = self.pretix_base_url.GetValue().strip()
        org = self.pretix_organizer.GetValue().strip()
        ev = self.pretix_event.GetValue().strip()
        token = (
            os.environ.get("PRETIX_API_TOKEN", "").strip()
            or os.environ.get("PRETX_TOKEN", "").strip()
            or self.pretix_token.GetValue().strip()
        )
        if not base.startswith("https://"):
            wx.MessageBox(
                "Set a valid HTTPS Pretix base URL first.",
                "Pretix",
                wx.OK | wx.ICON_WARNING,
            )
            return
        if not org or not token:
            wx.MessageBox(
                "Organizer slug and API token are required.",
                "Pretix",
                wx.OK | wx.ICON_WARNING,
            )
            return
        if not ev:
            wx.MessageBox("Enter the event slug to load lists.", "Pretix", wx.OK | wx.ICON_WARNING)
            return

        self.pretix_load_lists.Enable(False)

        def worker() -> None:
            try:
                client = importlib.import_module("niimbot_printer.pretix.client")
                rows = client.fetch_checkin_lists(base, org, token, ev)
                wx.CallAfter(self._on_checkin_lists_loaded, rows, None)
            except Exception as e:
                wx.CallAfter(self._on_checkin_lists_loaded, None, e)

        threading.Thread(target=worker, daemon=True).start()

    def _on_checkin_lists_loaded(self, rows: list | None, err: Exception | None) -> None:
        self.pretix_load_lists.Enable(True)
        if err is not None:
            wx.MessageBox(str(err), "Could not load check-in lists", wx.OK | wx.ICON_ERROR)
            return
        if not rows:
            wx.MessageBox("No check-in lists returned for this event.", "Pretix", wx.OK | wx.ICON_INFORMATION)
            return
        lines = [f"{r.get('id')}: {r.get('name', '')}" for r in rows if isinstance(r, dict)]
        self.pretix_list_ids.SetValue(", ".join(str(r.get("id")) for r in rows if isinstance(r, dict)))
        wx.MessageBox(
            "Check-in list IDs were filled in. Details:\n\n" + "\n".join(lines[:40])
            + ("\n…" if len(lines) > 40 else ""),
            "Check-in lists",
            wx.OK | wx.ICON_INFORMATION,
        )

    def _on_ok(self, _evt: wx.CommandEvent) -> None:
        port = self._current_port_device()
        if not port:
            wx.MessageBox("Set a serial port.", "Settings", wx.OK | wx.ICON_WARNING)
            return
        w = int(self.width_px.GetValue())
        h = int(self.height_px.GetValue())
        if w % 8:
            wx.MessageBox("Label width must be a multiple of 8.", "Settings", wx.OK | wx.ICON_WARNING)
            return

        pretix_on = self.pretix_enabled.GetValue()
        pretix_url = self.pretix_base_url.GetValue().strip()
        if pretix_on and pretix_url and not pretix_url.startswith("https://"):
            wx.MessageBox(
                "Pretix base URL must use https://",
                "Settings",
                wx.OK | wx.ICON_WARNING,
            )
            return

        list_ids = _parse_list_ids_field(self.pretix_list_ids.GetValue())
        if pretix_on and not list_ids:
            wx.MessageBox(
                "Pretix is enabled but no check-in list IDs were set. "
                "Add at least one numeric ID (or disable Pretix).",
                "Settings",
                wx.OK | wx.ICON_WARNING,
            )
            return

        self._result = settings.AppSettings(
            serial_port=port,
            font_path=self.font_path.GetValue().strip(),
            font_size=int(self.font_size.GetValue()),
            bold=self.bold.GetValue(),
            label_width_px=w,
            label_height_px=h,
            density=int(self.density.GetValue()),
            label_type=int(self.label_type.GetValue()),
            logging_enabled=self.logging_on.GetValue(),
            debug_serial=self.debug_serial.GetValue(),
            pretix_enabled=pretix_on,
            pretix_base_url=pretix_url,
            pretix_organizer_slug=self.pretix_organizer.GetValue().strip(),
            pretix_api_token=self.pretix_token.GetValue().strip(),
            pretix_event_slug=self.pretix_event.GetValue().strip(),
            pretix_checkin_list_ids=list_ids,
            pretix_badge_template=self.pretix_badge_tpl.GetValue().strip() or "{attendee_name}",
        )
        self.EndModal(wx.ID_OK)

    def get_result(self) -> settings.AppSettings | None:
        return self._result


class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="NIIMBOT B1 printer", size=(580, 420))
        self._settings = settings.load_settings()
        self._session_prints = 0
        self._printing = False

        bar = wx.MenuBar()
        file_m = wx.Menu()
        file_m.Append(wx.ID_PREFERENCES, "Settings…\tCtrl+,")
        file_m.AppendSeparator()
        file_m.Append(wx.ID_EXIT, "Quit\tCtrl+Q")
        bar.Append(file_m, "&File")
        self.SetMenuBar(bar)
        self.Bind(wx.EVT_MENU, self._on_settings, id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, self._on_quit, id=wx.ID_EXIT)
        _set_frame_icon(self)

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        root.Add(wx.StaticText(panel, label="Label text:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.name_ctrl = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.name_ctrl.SetHint("Type text and press Enter or Print")
        root.Add(self.name_ctrl, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.print_btn = wx.Button(panel, label="Print label")
        self.print_btn.Bind(wx.EVT_BUTTON, self._on_print)
        btn_row.Add(self.print_btn, 0, wx.RIGHT, 8)
        btn_row.AddStretchSpacer(1)
        root.Add(btn_row, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)

        # Children must use the StaticBox as parent on GTK so the group clips and lays out correctly.
        self._pretix_box = wx.StaticBox(panel, label="Pretix")
        pretix_root = wx.StaticBoxSizer(self._pretix_box, wx.VERTICAL)
        self._pretix_secret_lbl = wx.StaticText(
            self._pretix_box,
            label="Ticket secret (scan or paste QR payload):",
        )
        pretix_root.Add(self._pretix_secret_lbl, 0, wx.TOP, 4)
        self.pretix_secret_ctrl = wx.TextCtrl(self._pretix_box, style=wx.TE_PROCESS_ENTER)
        self.pretix_secret_ctrl.SetHint("USB scanners often type the secret here; then press Enter")
        pretix_root.Add(self.pretix_secret_ctrl, 0, wx.EXPAND | wx.TOP, 6)
        self.pretix_checkin_btn = wx.Button(self._pretix_box, label="Check in and print label")
        self.pretix_checkin_btn.Bind(wx.EVT_BUTTON, self._on_pretix_print)
        pretix_root.Add(self.pretix_checkin_btn, 0, wx.TOP, 8)
        root.Add(pretix_root, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)

        stats_box = wx.StaticBox(panel, label="Statistics")
        stats_sizer = wx.StaticBoxSizer(stats_box, wx.VERTICAL)
        stat_font = wx.Font(wx.FontInfo(11))
        stat_em = wx.Font(wx.FontInfo(12).Bold())

        self.stat_total = wx.StaticText(panel, label="")
        self.stat_total.SetFont(stat_em)
        stats_sizer.Add(self.stat_total, 0, wx.BOTTOM, 6)

        self.stat_session = wx.StaticText(panel, label="")
        self.stat_session.SetFont(stat_font)
        stats_sizer.Add(self.stat_session, 0, wx.BOTTOM, 4)

        self.stat_next = wx.StaticText(panel, label="")
        self.stat_next.SetFont(stat_font)
        stats_sizer.Add(self.stat_next, 0)

        root.Add(stats_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)

        self.status = wx.StaticText(panel, label="")
        self.status.SetForegroundColour(wx.Colour(60, 60, 60))
        root.Add(self.status, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)

        panel.SetSizer(root)
        self.pretix_secret_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_pretix_print)
        self._sync_pretix_panel()
        self._update_status_line()
        self.name_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_print)
        self.Centre()

    def _on_quit(self, _evt: wx.CommandEvent) -> None:
        self.Close()

    def _on_settings(self, _evt: wx.CommandEvent) -> None:
        dlg = SettingsDialog(self, self._settings)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        res = dlg.get_result()
        dlg.Destroy()
        if res:
            self._settings = res
            settings.save_settings(self._settings)
            self._sync_pretix_panel()
            self._update_status_line()

    def _sync_pretix_panel(self) -> None:
        show = bool(self._settings.pretix_enabled and _pretix_module_available())
        self._pretix_box.Show(show)
        self._pretix_secret_lbl.Show(show)
        self.pretix_secret_ctrl.Show(show)
        self.pretix_checkin_btn.Show(show)
        self.Layout()

    def _set_busy(self, busy: bool) -> None:
        self._printing = busy
        self.print_btn.Enable(not busy)
        self.name_ctrl.Enable(not busy)
        if self.pretix_secret_ctrl.IsShown():
            self.pretix_secret_ctrl.Enable(not busy)
            self.pretix_checkin_btn.Enable(not busy)

    def _refresh_statistics(self) -> None:
        st = settings.load_state()
        next_seq = st.next_seq
        total_done = max(0, next_seq - 1)
        self.stat_total.SetLabel(f"All-time labels printed: {total_done}")
        self.stat_session.SetLabel(f"This session: {self._session_prints}")
        self.stat_next.SetLabel(f"Next sequence number: {next_seq}")
        self.Layout()

    def _update_status_line(self) -> None:
        cfg = self._settings
        log_note = "logging on → ~/print.log" if cfg.logging_enabled else "logging off (no file writes)"
        if cfg.pretix_enabled and not _pretix_module_available():
            pt = "Pretix requested but this build has no Pretix module"
        elif cfg.pretix_enabled:
            pt = "Pretix on"
        else:
            pt = "Pretix off"
        msg = f"Port: {cfg.serial_port}  |  {pt}  |  {log_note}"
        self.status.SetLabel(msg)
        self._refresh_statistics()

    def _on_pretix_print(self, _evt: wx.CommandEvent | wx.KeyEvent) -> None:
        if self._printing:
            return
        if not self._settings.pretix_enabled:
            return
        if not _pretix_module_available():
            wx.MessageBox(
                "This build was compiled without Pretix support.",
                "Pretix",
                wx.OK | wx.ICON_INFORMATION,
            )
            return
        raw = self.pretix_secret_ctrl.GetValue().strip()
        if not raw:
            wx.MessageBox(
                "Enter or scan the ticket secret first.",
                "Pretix",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        cfg_snapshot = replace(self._settings)
        base = cfg_snapshot.pretix_base_url.strip()
        org = cfg_snapshot.pretix_organizer_slug.strip()
        token = cfg_snapshot.effective_pretix_token()
        lists = cfg_snapshot.pretix_lists()
        if not base.startswith("https://"):
            wx.MessageBox("Set a valid HTTPS Pretix URL in Settings.", "Pretix", wx.OK | wx.ICON_WARNING)
            return
        if not org or not token:
            wx.MessageBox(
                "Configure organizer slug and API token in Settings (or use env).",
                "Pretix",
                wx.OK | wx.ICON_WARNING,
            )
            return
        if not lists:
            wx.MessageBox("Add at least one check-in list ID in Settings.", "Pretix", wx.OK | wx.ICON_WARNING)
            return

        self._set_busy(True)

        def worker() -> None:
            try:
                parse_secret = importlib.import_module("niimbot_printer.pretix.parse_secret")
                badge_text = importlib.import_module("niimbot_printer.pretix.badge_text")
                client = importlib.import_module("niimbot_printer.pretix.client")

                secret = parse_secret.normalize_secret(raw)
                if not secret:
                    raise ValueError("Empty ticket secret after parsing.")

                result = client.redeem(
                    base,
                    org,
                    token,
                    secret,
                    lists,
                    questions_supported=False,
                )
                data = result.data
                if data.get("status") != "ok":
                    raise client.PretixAPIError(_pretix_failure_message(data))

                position = data.get("position")
                if not isinstance(position, dict):
                    raise client.PretixAPIError("Pretix did not return attendee data.")

                label = badge_text.build_badge_text(position, cfg_snapshot.pretix_badge_template)
                list_info = data.get("list") if isinstance(data.get("list"), dict) else {}
                ev_slug = list_info.get("event")
                ev_slug_s = str(ev_slug).strip() if ev_slug else None
                ctx = badge_text.position_context(position)
                order_code = ctx.get("order") or None
                pid = position.get("id")
                try:
                    pos_id = int(pid) if pid is not None else None
                except (TypeError, ValueError):
                    pos_id = None

                fp = cfg_snapshot.effective_font_path()
                im = renderer.render_name_label(
                    label,
                    cfg_snapshot.label_width_px,
                    cfg_snapshot.label_height_px,
                    font_path=fp,
                    font_size=cfg_snapshot.font_size,
                    bold=cfg_snapshot.bold,
                )
                w, h, rows = printer.image_to_rows(im)

                def dbg(s: str) -> None:
                    print(s, flush=True)

                printer.print_raster(
                    cfg_snapshot.serial_port,
                    w,
                    h,
                    rows,
                    density=cfg_snapshot.density,
                    label_type=cfg_snapshot.label_type,
                    debug=dbg if cfg_snapshot.debug_serial else None,
                )
            except Exception as e:
                wx.CallAfter(
                    self._on_print_finished,
                    "",
                    cfg_snapshot,
                    e,
                )
            else:
                wx.CallAfter(
                    self._on_print_finished,
                    label,
                    cfg_snapshot,
                    None,
                    source="pretix",
                    pretix_event_slug=ev_slug_s,
                    pretix_order_code=order_code,
                    pretix_position_id=pos_id,
                    clear_pretix_field=True,
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_print(self, _evt: wx.CommandEvent | wx.KeyEvent) -> None:
        if self._printing:
            return
        name = self.name_ctrl.GetValue().strip()
        if not name:
            wx.MessageBox("Enter text to print.", "Print", wx.OK | wx.ICON_INFORMATION)
            return

        cfg_snapshot = replace(self._settings)
        self._set_busy(True)

        def worker() -> None:
            try:
                fp = cfg_snapshot.effective_font_path()
                im = renderer.render_name_label(
                    name,
                    cfg_snapshot.label_width_px,
                    cfg_snapshot.label_height_px,
                    font_path=fp,
                    font_size=cfg_snapshot.font_size,
                    bold=cfg_snapshot.bold,
                )
                w, h, rows = printer.image_to_rows(im)

                def dbg(s: str) -> None:
                    print(s, flush=True)

                printer.print_raster(
                    cfg_snapshot.serial_port,
                    w,
                    h,
                    rows,
                    density=cfg_snapshot.density,
                    label_type=cfg_snapshot.label_type,
                    debug=dbg if cfg_snapshot.debug_serial else None,
                )
            except Exception as e:
                wx.CallAfter(self._on_print_finished, name, cfg_snapshot, e)
            else:
                wx.CallAfter(self._on_print_finished, name, cfg_snapshot, None)

        threading.Thread(target=worker, daemon=True).start()

    def _on_print_finished(
        self,
        name: str,
        cfg: settings.AppSettings,
        err: Exception | None,
        *,
        source: str = "manual",
        pretix_event_slug: str | None = None,
        pretix_order_code: str | None = None,
        pretix_position_id: int | None = None,
        clear_pretix_field: bool = False,
    ) -> None:
        self._set_busy(False)
        if err is not None:
            pretix_err: type | None = None
            if _pretix_module_available():
                pretix_err = getattr(
                    importlib.import_module("niimbot_printer.pretix.client"),
                    "PretixAPIError",
                )
            known = isinstance(err, (printer.PrinterError, OSError, ValueError)) or (
                pretix_err is not None and isinstance(err, pretix_err)
            )
            if known:
                title = (
                    "Pretix"
                    if pretix_err is not None and isinstance(err, pretix_err)
                    else "Print failed"
                )
                wx.MessageBox(str(err), title, wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox(traceback.format_exc(), "Print failed", wx.OK | wx.ICON_ERROR)
            return

        st = settings.load_state()
        seq = st.next_seq
        st.next_seq = seq + 1
        settings.save_state(st)

        if cfg.logging_enabled:
            try:
                if source == "pretix":
                    audit_log.record_print(
                        cfg.effective_log_path(),
                        name=name,
                        seq=seq,
                        source="pretix",
                        pretix_event_slug=pretix_event_slug,
                        pretix_order_code=pretix_order_code,
                        pretix_position_id=pretix_position_id,
                    )
                else:
                    audit_log.record_print(cfg.effective_log_path(), name=name, seq=seq, source="manual")
            except OSError as e:
                wx.MessageBox(f"Printed OK but log write failed:\n{e}", "Log error", wx.OK | wx.ICON_WARNING)

        self._session_prints += 1
        self._update_status_line()
        if clear_pretix_field:
            self.pretix_secret_ctrl.SetValue("")
            self.pretix_secret_ctrl.SetFocus()
        else:
            self.name_ctrl.SetFocus()
            self.name_ctrl.SelectAll()


def run_app() -> None:
    app = wx.App(False)
    frame = MainFrame()
    frame.Show()
    app.MainLoop()
