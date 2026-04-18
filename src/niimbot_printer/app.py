"""Application entry."""

from __future__ import annotations

__all__ = ["main"]


def main() -> None:
    from niimbot_printer.gui import run_app

    run_app()
