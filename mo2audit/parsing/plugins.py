"""plugins.txt / loadorder.txt -> raw plugin data.

Polarity warning (spec 5.2): plugins.txt uses `*` = enabled, no prefix =
disabled. This is the OPPOSITE of modlist.txt's `+`/`-` convention -- do not
unify the two parsers.
"""

from __future__ import annotations

from pathlib import Path


def _data_lines(path: Path) -> list[str]:
    """Non-blank, non-comment lines. Every '#'-prefixed line is a comment,
    wherever it appears -- MO2/the game may write one OR two header lines
    ('# This file was automatically generated...', '# Please do not modify
    this file.'). Phase 1 blindly skipped only the first line, so the
    two-comment pre-LOOT state leaked '# Please do not modify this file.'
    through as a plugin (Bug C, PHASE2 spec 5.6)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line.strip() and not line.lstrip().startswith("#")]


def parse_plugins(path: Path) -> list[tuple[str, bool, int]]:
    """Returns (filename, enabled, load_index) tuples, in file order."""
    result: list[tuple[str, bool, int]] = []
    for index, line in enumerate(_data_lines(path)):
        if line.startswith("*"):
            enabled, filename = True, line[1:]
        else:
            enabled, filename = False, line
        result.append((filename, enabled, index))
    return result


def parse_loadorder(path: Path) -> list[str]:
    """Full load order including base game masters, no enable flags."""
    return _data_lines(path)
