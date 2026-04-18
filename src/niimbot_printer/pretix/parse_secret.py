"""Normalize QR / scanner payload into a Pretix ticket ``secret`` string."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

__all__ = ["normalize_secret"]


def normalize_secret(raw: str) -> str:
    s = raw.strip()
    if not s:
        return ""
    if "://" not in s:
        return s

    parsed = urlparse(s)
    query = parse_qs(parsed.query)
    for key in ("secret", "p", "code"):
        vals = query.get(key)
        if vals and vals[0].strip():
            return vals[0].strip()

    path = parsed.path.strip("/")
    if path:
        last = path.split("/")[-1]
        if len(last) >= 12 and last.replace("_", "").replace("-", "").isalnum():
            return last

    return s
