"""wxPython main window and settings dialog."""

from __future__ import annotations

import threading
import traceback
from dataclasses import replace

import wx

from niimbot_printer import audit_log, printer, renderer, resources, settings

__all__ = ["MainFrame", "SettingsDialog", "run_app"]


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

        main.Add(grid, 1, wx.ALL | wx.EXPAND, 12)

        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(self, wx.ID_OK)
        ok.SetDefault()
        btns.AddButton(ok)
        btns.AddButton(wx.Button(self, wx.ID_CANCEL))
        btns.Realize()
        main.Add(btns, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.SetSizer(main)
        self.Fit()
        min_w = 520
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
            self._update_status_line()

    def _set_busy(self, busy: bool) -> None:
        self._printing = busy
        self.print_btn.Enable(not busy)
        self.name_ctrl.Enable(not busy)

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
        msg = f"Port: {cfg.serial_port}  |  {log_note}"
        self.status.SetLabel(msg)
        self._refresh_statistics()

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
    ) -> None:
        self._set_busy(False)
        if err is not None:
            if isinstance(err, (printer.PrinterError, OSError, ValueError)):
                wx.MessageBox(str(err), "Print failed", wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox(traceback.format_exc(), "Print failed", wx.OK | wx.ICON_ERROR)
            return

        st = settings.load_state()
        seq = st.next_seq
        st.next_seq = seq + 1
        settings.save_state(st)

        if cfg.logging_enabled:
            try:
                audit_log.record_print(cfg.effective_log_path(), name=name, seq=seq, source="manual")
            except OSError as e:
                wx.MessageBox(f"Printed OK but log write failed:\n{e}", "Log error", wx.OK | wx.ICON_WARNING)

        self._session_prints += 1
        self._update_status_line()
        self.name_ctrl.SetFocus()
        self.name_ctrl.SelectAll()


def run_app() -> None:
    app = wx.App(False)
    frame = MainFrame()
    frame.Show()
    app.MainLoop()
