"""Build label text from a Pretix order ``position`` object."""

from __future__ import annotations

from typing import Any

__all__ = ["build_badge_text", "position_context"]


def position_context(position: dict[str, Any]) -> dict[str, str]:
    name = (position.get("attendee_name") or "").strip() or "Guest"
    company = (
        position.get("company")
        or position.get("attendee_company")
        or ""
    )
    if isinstance(company, str):
        company = company.strip()
    else:
        company = str(company).strip() if company else ""

    order = _order_code(position) or ""
    item = position.get("item")
    item_s = ""
    if isinstance(item, str):
        item_s = item.strip()
    elif isinstance(item, dict):
        item_s = str(item.get("name") or "").strip()

    return {
        "attendee_name": name,
        "company": company,
        "order": order,
        "item": item_s,
    }


def _order_code(position: dict[str, Any]) -> str | None:
    o = position.get("order")
    if isinstance(o, str) and o.strip():
        s = o.strip()
        if "/orders/" in s:
            tail = s.split("/orders/")[-1].rstrip("/")
            return tail.split("/")[0] or None
        return s
    return None


def build_badge_text(position: dict[str, Any], template: str) -> str:
    ctx = position_context(position)
    tpl = (template or "{attendee_name}").strip() or "{attendee_name}"
    tpl = tpl.replace("\\n", "\n")
    try:
        out = tpl.format(**ctx)
    except (KeyError, ValueError, IndexError):
        out = ctx["attendee_name"]
    return out.strip() or ctx["attendee_name"]
