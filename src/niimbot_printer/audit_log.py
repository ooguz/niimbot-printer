"""Append-only JSONL audit log; schema reserved for future Pretix integration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["record_print"]


def record_print(
    log_file: Path,
    *,
    name: str,
    seq: int,
    source: str = "manual",
    pretix_event_slug: str | None = None,
    pretix_order_code: str | None = None,
    pretix_position_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Append one JSON object per line. Phase 2 (Pretix) can pass non-null
    pretix_* fields and optional ``extra`` without changing callers' shape.
    """
    row: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "name": name,
        "seq": int(seq),
        "source": source,
        "pretix_event_slug": pretix_event_slug,
        "pretix_order_code": pretix_order_code,
        "pretix_position_id": pretix_position_id,
    }
    if extra:
        row.update(extra)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
