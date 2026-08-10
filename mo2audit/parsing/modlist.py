"""modlist.txt -> list[ModEntry].

CRITICAL: modlist.txt is stored in REVERSE priority order. The first line
after the header is the highest-priority mod (bottom of MO2's left pane,
wins all file conflicts). See MO2-Audit-SPEC.md section 5.1.
"""

from __future__ import annotations

from pathlib import Path

from mo2audit.model import ModEntry


def _priority_for_index(index: int, total: int) -> int:
    """First data line (index 0) gets the highest priority value."""
    return total - 1 - index


def parse_modlist(path: Path) -> list[ModEntry]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    data_lines = [line for line in lines[1:] if line.strip()]
    total = len(data_lines)

    entries: list[ModEntry] = []
    for index, line in enumerate(data_lines):
        prefix, name = line[0], line[1:]
        if prefix == "+":
            enabled, is_unmanaged = True, False
        elif prefix == "-":
            enabled, is_unmanaged = False, False
        elif prefix == "*":
            # Unmanaged entries (DLC, Creation Club, base game resources) are
            # always enabled -- MO2 gives no way to disable them from the
            # left pane. Not stated explicitly in the spec's prefix table.
            enabled, is_unmanaged = True, True
        else:
            raise ValueError(f"unrecognized modlist.txt line prefix {prefix!r} in {line!r}")

        entries.append(
            ModEntry(
                name=name,
                enabled=enabled,
                priority=_priority_for_index(index, total),
                is_separator=name.lower().endswith("_separator"),
                is_unmanaged=is_unmanaged,
                path=None,
            )
        )

    return entries
