"""Light tests for Pretix helpers (no network)."""

from __future__ import annotations

import unittest

from niimbot_printer.pretix.badge_text import build_badge_text, position_context
from niimbot_printer.pretix.parse_secret import normalize_secret


class PretixHelpersTest(unittest.TestCase):
    def test_normalize_secret_plain(self) -> None:
        self.assertEqual(normalize_secret("  abc123  "), "abc123")

    def test_normalize_secret_query(self) -> None:
        u = "https://kayit.example.org/t/?secret=xyz789"
        self.assertEqual(normalize_secret(u), "xyz789")

    def test_badge_template(self) -> None:
        pos = {"attendee_name": "Ada", "company": "ACME"}
        self.assertIn("Ada", build_badge_text(pos, "{attendee_name} — {company}"))
        ctx = position_context(pos)
        self.assertEqual(ctx["attendee_name"], "Ada")
        self.assertEqual(ctx["company"], "ACME")


if __name__ == "__main__":
    unittest.main()
