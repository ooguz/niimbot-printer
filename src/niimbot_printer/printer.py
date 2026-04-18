"""NIIMBOT B1 serial protocol (derived from hairymnstr/niimctl)."""

from __future__ import annotations

import struct
import time
from typing import Callable

import serial

__all__ = [
    "PrinterError",
    "send_packet",
    "recv_packet",
    "print_raster",
]


class PrinterError(Exception):
    """Raised when the printer protocol fails or the device misbehaves."""


def send_packet(port: serial.Serial, cmd: int, payload: bytes) -> None:
    packet = bytes([0x55, 0x55, cmd, len(payload)]) + payload
    cks = 0
    for b in packet[2:]:
        cks ^= b
    packet += bytes([cks, 0xAA, 0xAA])
    port.write(packet)


def recv_packet(port: serial.Serial, timeout: float = 1.0) -> tuple[int, bytes] | None:
    port.timeout = timeout
    state = "idle"
    cmd = 0
    payload_len = 0
    payload = b""

    while True:
        c = port.read(1)
        if c == b"":
            return None
        if state == "idle":
            if c == b"\x55":
                state = "started"
        elif state == "started":
            if c == b"\x55":
                state = "cmd"
            else:
                state = "idle"
        elif state == "cmd":
            cmd = c[0]
            state = "payload_len"
        elif state == "payload_len":
            payload_len = c[0]
            payload = b""
            state = "payload"
        elif state == "payload":
            payload += c
            if len(payload) == payload_len:
                state = "checksum"
        elif state == "checksum":
            cks = cmd ^ payload_len
            for x in payload:
                cks ^= x
            if cks != c[0]:
                return None
            state = "end"
        elif state == "end":
            if c != b"\xAA":
                return None
            state = "end2"
        elif state == "end2":
            if c != b"\xAA":
                return None
            break

    return (cmd, payload)


def _expect_ok(
    port: serial.Serial,
    debug: Callable[[str], None] | None,
    label: str,
) -> tuple[int, bytes]:
    p = recv_packet(port)
    if p is None:
        raise PrinterError(f"{label}: no response or bad packet")
    if debug:
        debug(f"{label}: {p!r}")
    return p


def _is_busy_nak(p: tuple[int, bytes] | None) -> bool:
    """True if the device is not ready (common 1-byte NAK)."""
    if p is None:
        return True
    pl = p[1]
    return pl == b"\x00" or pl == b""


def _send_until_ack(
    port: serial.Serial,
    cmd: int,
    payload: bytes,
    label: str,
    debug: Callable[[str], None] | None,
    *,
    recv_timeout: float = 0.45,
    max_attempts: int = 80,
    retry_delay_s: float = 0.12,
) -> tuple[int, bytes]:
    """
    Retry command until we get a non-NAK reply. After 0xF3 the B1 often returns
    ``b'\\x00'`` for 0x21/0x23/0x01 if queried too soon (still feeding/cutting).
    """
    for attempt in range(max_attempts):
        send_packet(port, cmd, payload)
        p = recv_packet(port, timeout=recv_timeout)
        if debug:
            debug(f"{label} attempt {attempt}: {p!r}")
        if p is not None and not _is_busy_nak(p):
            return p
        time.sleep(retry_delay_s)
    raise PrinterError(f"{label}: printer busy (NAK) after {max_attempts} attempts")


def _drain_pending_packets(
    port: serial.Serial,
    debug: Callable[[str], None] | None,
    *,
    rounds: int = 24,
    timeout: float = 0.06,
) -> None:
    """Consume framed replies until idle (clears multi-copy tail after 0xF3)."""
    for _ in range(rounds):
        p = recv_packet(port, timeout=timeout)
        if p is None:
            break
        if debug:
            debug(f"drain packet: {p!r}")


def _drain_raw_rx(port: serial.Serial, chunk: int = 512, idle_timeout: float = 0.02) -> None:
    """Discard any stray bytes not consumed by ``recv_packet``."""
    old = port.timeout
    try:
        port.timeout = idle_timeout
        while True:
            b = port.read(chunk)
            if not b:
                break
    finally:
        port.timeout = old


def _print_one_label_session(
    s: serial.Serial,
    width: int,
    height: int,
    rows: list[list[int]],
    *,
    debug: Callable[[str], None] | None,
    status_polls: int,
    status_interval_s: float,
    status_recv_timeout: float,
) -> None:
    """One print job (0x01…0xF3) on an already-open port."""
    _send_until_ack(
        s,
        0x01,
        struct.pack(">HIB", 1, 0, 0),
        "print start (0x01)",
        debug,
    )

    send_packet(s, 0x03, b"\x01")
    p = _expect_ok(s, debug, "page start (0x03)")
    if _is_busy_nak(p):
        raise PrinterError("page start (0x03): device returned NAK")

    send_packet(s, 0x13, struct.pack(">HHH", height, width, 1))
    p = _expect_ok(s, debug, "set page size (0x13)")
    if _is_busy_nak(p):
        raise PrinterError("set page size (0x13): device returned NAK")

    blank_rows = 0
    blank_start = -1
    for row_num, row in enumerate(rows):
        if sum(row) == 0:
            if blank_rows == 0:
                blank_start = row_num
            blank_rows += 1
        else:
            if blank_rows:
                send_packet(s, 0x84, struct.pack(">HB", blank_start, blank_rows))
                blank_rows = 0
            printpx = 0
            for b in row:
                for bit in range(8):
                    if b & (1 << bit):
                        printpx += 1
            payload = struct.pack(">HHH", row_num, printpx, 1) + bytes(row)
            send_packet(s, 0x85, payload)

    if blank_rows:
        send_packet(s, 0x84, struct.pack(">HB", blank_start, blank_rows))

    p = recv_packet(s)
    if debug:
        debug(f"pre page end 1: {p!r}")
    p = recv_packet(s)
    if debug:
        debug(f"pre page end 2: {p!r}")

    send_packet(s, 0xE3, b"\x01")
    p = recv_packet(s)
    if debug:
        debug(f"after 0xe3: {p!r}")

    for _ in range(status_polls):
        send_packet(s, 0xA3, b"")
        p = recv_packet(s, timeout=status_recv_timeout)
        if debug:
            debug(f"status 0xa3: {p!r}")
        time.sleep(status_interval_s)

    send_packet(s, 0xF3, b"\x01")
    # Read F3 reply and clear RX so the next copy's 0x01 is not confused with
    # leftover frames (otherwise every second label is often skipped).
    p = recv_packet(s, timeout=1.0)
    if debug:
        debug(f"after 0xf3: {p!r}")
    _drain_pending_packets(s, debug, rounds=16, timeout=0.05)
    _drain_raw_rx(s)


def print_raster(
    port_path: str,
    width: int,
    height: int,
    rows: list[list[int]],
    *,
    copies: int = 1,
    density: int = 3,
    label_type: int = 1,
    status_polls: int = 12,
    status_interval_s: float = 0.05,
    status_recv_timeout: float = 0.2,
    inter_copy_delay_s: float = 0.55,
    flush_before_close_s: float = 0.55,
    debug: Callable[[str], None] | None = None,
) -> None:
    """
    Send a 1-bit raster to the printer.

    ``rows`` is a list of length ``height``; each row is a list of byte values
    (length width/8) with MSB-first pixels, matching niimctl packing.

    Multiple ``copies`` are sent in a **single** serial session (re-opening the
    port between jobs often results in only one physical label).

    ``flush_before_close_s`` waits after the last job so the final label can
    finish before the USB handle is closed (otherwise the last copy is often lost).

    Before each copy, 0x21 / 0x23 (and the session’s 0x01) are **retried** until the
    printer returns a non-``\\x00`` ack — the B1 often NAKs if still busy right after 0xF3.
    The line is drained after each 0xF3 so the next job does not read stale packets.
    """
    if width > 400:
        raise PrinterError("Image must be at most 400 pixels wide")
    if width % 8:
        raise PrinterError("Image width must be a multiple of 8")
    expected_row_len = width // 8
    if len(rows) != height:
        raise PrinterError(f"Expected {height} rows, got {len(rows)}")
    for i, row in enumerate(rows):
        if len(row) != expected_row_len:
            raise PrinterError(f"Row {i}: expected {expected_row_len} bytes, got {len(row)}")

    n_copies = max(1, min(99, int(copies)))
    density_b = max(1, min(5, int(density))) & 0xFF
    label_type_b = max(1, min(3, int(label_type))) & 0xFF

    s = serial.Serial(port_path)

    try:
        for i in range(n_copies):
            _send_until_ack(
                s,
                0x21,
                bytes([density_b]),
                "set density (0x21)",
                debug,
            )
            _send_until_ack(
                s,
                0x23,
                bytes([label_type_b]),
                "set label type (0x23)",
                debug,
            )

            _print_one_label_session(
                s,
                width,
                height,
                rows,
                debug=debug,
                status_polls=status_polls,
                status_interval_s=status_interval_s,
                status_recv_timeout=status_recv_timeout,
            )
            if i + 1 < n_copies and inter_copy_delay_s > 0:
                time.sleep(inter_copy_delay_s)
        try:
            s.flush()
        except (OSError, AttributeError):
            pass
        if flush_before_close_s > 0:
            time.sleep(flush_before_close_s)
    finally:
        s.close()


def image_to_rows(im) -> tuple[int, int, list[list[int]]]:
    """Convert a PIL Image (mode '1' or 'L') to niimctl row bytes."""
    im = im.convert("1")
    width, height = im.size
    if width % 8:
        raise PrinterError("Image width must be a multiple of 8")
    xim = im.load()
    rows: list[list[int]] = []
    for y in range(height):
        row_bytes = [0] * (width // 8)
        for x in range(width):
            p = xim[x, y]
            if isinstance(p, tuple):
                dark = p[0] == 0
            else:
                dark = p == 0
            if dark:
                row_bytes[x // 8] |= 1 << (7 - (x % 8))
        rows.append(row_bytes)
    return width, height, rows
