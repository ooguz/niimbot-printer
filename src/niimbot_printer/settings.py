"""XDG-based JSON configuration."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from niimbot_printer.resources import bundled_bitter_font_path

__all__ = [
    "AppSettings",
    "State",
    "config_path",
    "state_path",
    "load_settings",
    "save_settings",
    "load_state",
    "save_state",
    "list_serial_ports",
    "audit_log_path",
]


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def _xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def config_path() -> Path:
    return _xdg_config_home() / "niimbot-printer" / "config.json"


def state_path() -> Path:
    return _xdg_data_home() / "niimbot-printer" / "state.json"


def audit_log_path() -> Path:
    """Fixed location for print audit log (JSON Lines)."""
    return Path.home() / "print.log"


@dataclass
class AppSettings:
    serial_port: str = "/dev/ttyACM0"
    font_path: str = ""
    font_size: int = 36
    bold: bool = False
    label_width_px: int = 384
    label_height_px: int = 240
    density: int = 3
    label_type: int = 1
    logging_enabled: bool = True
    debug_serial: bool = False
    pretix_enabled: bool = False
    pretix_base_url: str = ""
    pretix_organizer_slug: str = ""
    pretix_api_token: str = ""
    pretix_event_slug: str = ""
    pretix_checkin_list_ids: list[int] = field(default_factory=list)
    pretix_badge_template: str = "{attendee_name}"

    def effective_font_path(self) -> str | None:
        if self.font_path.strip():
            return self.font_path.strip()
        bundled = bundled_bitter_font_path()
        return str(bundled) if bundled is not None else None

    def effective_log_path(self) -> Path:
        return audit_log_path()

    def effective_pretix_token(self) -> str:
        """API token from env (``PRETIX_API_TOKEN`` or ``PRETX_TOKEN``) or config."""
        env_tok = (
            os.environ.get("PRETIX_API_TOKEN", "").strip()
            or os.environ.get("PRETX_TOKEN", "").strip()
        )
        if env_tok:
            return env_tok
        return self.pretix_api_token.strip()

    def pretix_lists(self) -> list[int]:
        return list(self.pretix_checkin_list_ids)


@dataclass
class State:
    next_seq: int = 1


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_settings() -> AppSettings:
    path = config_path()
    if not path.is_file():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()
    return _settings_from_dict(data)


def _coerce_checkin_list_ids(raw: Any) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[int] = []
        for x in raw:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out
    return []


def _settings_from_dict(data: dict[str, Any]) -> AppSettings:
    base = AppSettings()
    names = {f.name for f in fields(AppSettings)}
    for key, value in data.items():
        if key not in names:
            continue
        if key == "pretix_checkin_list_ids":
            setattr(base, key, _coerce_checkin_list_ids(value))
        else:
            setattr(base, key, value)
    return base


def save_settings(s: AppSettings) -> None:
    path = config_path()
    _ensure_parent(path)
    path.write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")


def load_state() -> State:
    path = state_path()
    if not path.is_file():
        return State()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return State()
    seq = data.get("next_seq", 1)
    try:
        n = int(seq)
    except (TypeError, ValueError):
        n = 1
    return State(next_seq=max(1, n))


def save_state(st: State) -> None:
    path = state_path()
    _ensure_parent(path)
    path.write_text(json.dumps({"next_seq": st.next_seq}, indent=2), encoding="utf-8")


def list_serial_ports() -> list[tuple[str, str | None]]:
    """Return (device, description) for available serial ports."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    out: list[tuple[str, str | None]] = []
    for p in list_ports.comports():
        out.append((p.device, p.description))
    return out
