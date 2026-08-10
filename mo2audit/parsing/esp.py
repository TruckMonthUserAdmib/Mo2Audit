"""TES4 header reader -> masters, ESM/ESL flags.

Reads only the first ~4KB of each file, never a full plugin. Any malformance
raises PluginParseError -- callers turn that into a Finding, never let it
propagate as a bare traceback (spec 5.5, 11).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

TES4_MAGIC = b"TES4"
FLAG_ESM = 0x00000001
FLAG_ESL = 0x00000200
HEADER_READ_SIZE = 4096
HEADER_FIXED_SIZE = 24


class PluginParseError(Exception):
    pass


@dataclass
class PluginHeaderInfo:
    is_esm: bool
    is_esl: bool
    masters: list[str]
    hedr_num_records: int | None


def parse_plugin_header(path: Path) -> PluginHeaderInfo:
    try:
        data = Path(path).read_bytes()[:HEADER_READ_SIZE]
    except OSError as exc:
        raise PluginParseError(f"could not read {path}: {exc}") from exc

    if len(data) < HEADER_FIXED_SIZE or data[0:4] != TES4_MAGIC:
        raise PluginParseError(f"{path}: missing TES4 header")

    try:
        return _parse_header_bytes(data)
    except struct.error as exc:
        raise PluginParseError(f"{path}: truncated or malformed subrecord data") from exc


def _parse_header_bytes(data: bytes) -> PluginHeaderInfo:
    data_size, flags = struct.unpack_from("<II", data, 4)
    is_esm = bool(flags & FLAG_ESM)
    is_esl = bool(flags & FLAG_ESL)

    masters: list[str] = []
    hedr_num_records: int | None = None

    offset = HEADER_FIXED_SIZE
    end = min(HEADER_FIXED_SIZE + data_size, len(data))

    while offset + 6 <= end:
        sub_type = data[offset : offset + 4]
        (sub_size,) = struct.unpack_from("<H", data, offset + 4)
        payload_start = offset + 6
        payload_end = payload_start + sub_size
        if payload_end > len(data):
            # Declared subrecord runs past what we read (4KB window, or a
            # genuinely truncated file) -- stop rather than read past the
            # buffer. Whatever we collected so far still stands.
            break
        payload = data[payload_start:payload_end]

        if sub_type == b"HEDR" and len(payload) >= 12:
            _version, num_records, _next_object_id = struct.unpack_from("<fiI", payload, 0)
            hedr_num_records = num_records
        elif sub_type == b"MAST":
            masters.append(payload.split(b"\x00", 1)[0].decode("utf-8", errors="replace"))

        offset = payload_end

    return PluginHeaderInfo(
        is_esm=is_esm,
        is_esl=is_esl,
        masters=masters,
        hedr_num_records=hedr_num_records,
    )
