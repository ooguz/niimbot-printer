"""Pretix REST API (stdlib HTTP)."""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

__all__ = ["PretixAPIError", "RedeemResult", "fetch_checkin_lists", "redeem"]


class PretixAPIError(Exception):
    """HTTP, network, or unexpected response errors."""


@dataclass
class RedeemResult:
    http_status: int
    data: dict[str, Any]


def _headers(token: str, *, json_body: bool) -> dict[str, str]:
    h = {"Authorization": f"Token {token}", "Accept": "application/json"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _read_json_response(resp) -> Any:
    raw = resp.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _request_json(
    method: str,
    url: str,
    token: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float = 45.0,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers=_headers(token, json_body=body is not None),
        method=method,
    )
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            status = getattr(resp, "status", 200)
            payload = _read_json_response(resp)
            return int(status), payload
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as je:
            raise PretixAPIError(f"Pretix HTTP {e.code}: {raw[:500]}") from je
        return int(e.code), payload
    except URLError as e:
        raise PretixAPIError(str(e.reason if hasattr(e, "reason") else e)) from e


def redeem(
    base_url: str,
    organizer: str,
    token: str,
    secret: str,
    list_ids: list[int],
    *,
    questions_supported: bool = False,
) -> RedeemResult:
    if not list_ids:
        raise PretixAPIError("At least one check-in list ID is required.")
    url = f"{base_url.rstrip('/')}/api/v1/organizers/{organizer}/checkinrpc/redeem/"
    body: dict[str, Any] = {
        "secret": secret,
        "source_type": "barcode",
        "lists": list_ids,
        "nonce": str(uuid4()),
        "questions_supported": questions_supported,
    }
    status, payload = _request_json("POST", url, token, body=body)
    if not isinstance(payload, dict):
        raise PretixAPIError("Unexpected Pretix response shape.")
    return RedeemResult(http_status=status, data=payload)


def fetch_checkin_lists(
    base_url: str,
    organizer: str,
    token: str,
    event_slug: str,
) -> list[dict[str, Any]]:
    if not event_slug.strip():
        raise PretixAPIError("Event slug is required to load check-in lists.")
    org = quote(organizer.strip(), safe="")
    ev = quote(event_slug.strip(), safe="")
    url = (
        f"{base_url.rstrip('/')}/api/v1/organizers/{org}/events/{ev}/checkinlists/"
    )
    status, payload = _request_json("GET", url, token, body=None)
    if status >= 400:
        hint = ""
        if status == 404:
            hint = (
                " Check the organizer slug, event slug, and base URL "
                "(include any path prefix where Pretix is mounted, e.g. https://host/pretix)."
            )
        raise PretixAPIError(
            f"Failed to load check-in lists (HTTP {status}): {payload!r}.{hint}"
        )
    if not isinstance(payload, dict):
        raise PretixAPIError("Unexpected check-in lists response.")
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    return [r for r in results if isinstance(r, dict)]
