"""ModOrganizer.ini / game-folder evidence -> Setup fields.

Reads three things, all feeding the Phase 2 classification layer:
- gamePath from ModOrganizer.ini (the instance's game install).
- <gamePath>/Skyrim.ccc -- the manifest of plugins the game auto-loads with
  no plugins.txt line (all cc* content plus _ResourcePack.esl). This is the
  root mechanism behind Bug A; see MO2-Audit-PHASE2-SPEC.md section 1.1.
- Plugin basenames present in <gamePath>/Data (one scandir, non-recursive).
- Registered executable binary paths from [customExecutables] (TOOL heuristic).

Everything here is read-only and absent-is-normal: a moved game folder, a
non-AE build with no Skyrim.ccc, or a missing ModOrganizer.ini must degrade
to empty results, never an error.
"""

from __future__ import annotations

import os
from pathlib import Path

PLUGIN_EXTENSIONS = (".esp", ".esm", ".esl")

# MO2 wraps path values as @ByteArray(C:\\escaped\\path).
_BYTEARRAY_PREFIX = "@ByteArray("


def _read_ini_lines(ini_path: Path) -> list[str]:
    try:
        return Path(ini_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _unwrap_value(value: str) -> str:
    value = value.strip()
    if value.startswith(_BYTEARRAY_PREFIX) and value.endswith(")"):
        value = value[len(_BYTEARRAY_PREFIX) : -1]
    return value.replace("\\\\", "\\")


def read_game_path(ini_path: Path) -> Path | None:
    """gamePath from ModOrganizer.ini's [General] section, or None.

    Parsed by hand rather than configparser: MO2's ini uses @ByteArray
    wrappers, backslash escapes, and %-sequences that break strict parsers.
    """
    section = ""
    for line in _read_ini_lines(ini_path):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].lower()
            continue
        if section == "general" and stripped.lower().startswith("gamepath="):
            value = _unwrap_value(stripped.split("=", 1)[1])
            return Path(value) if value else None
    return None


def read_registered_executables(ini_path: Path) -> list[str]:
    """Binary paths from [customExecutables] (keys like `1\\binary=...`)."""
    section = ""
    result: list[str] = []
    for line in _read_ini_lines(ini_path):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].lower()
            continue
        if section == "customexecutables" and "=" in stripped:
            key, value = stripped.split("=", 1)
            if key.lower().endswith("\\binary"):
                value = _unwrap_value(value)
                if value:
                    result.append(value)
    return result


def parse_ccc(ccc_path: Path) -> list[str]:
    """Skyrim.ccc manifest lines, verbatim, in file order. Empty if absent."""
    try:
        lines = Path(ccc_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip()]


def scan_game_data_plugins(game_path: Path) -> set[str]:
    """Lowercase plugin basenames at the top level of <game>/Data."""
    data_dir = Path(game_path) / "Data"
    result: set[str] = set()
    try:
        with os.scandir(data_dir) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(PLUGIN_EXTENSIONS):
                    result.add(entry.name.lower())
    except OSError:
        return set()
    return result


def read_game_config(mo2_base: Path) -> tuple[list[str], set[str], list[str]]:
    """(ccc_managed_plugins, game_data_plugins, mo2_executables) for a base dir."""
    ini_path = Path(mo2_base) / "ModOrganizer.ini"
    executables = read_registered_executables(ini_path)
    game_path = read_game_path(ini_path)
    if game_path is None:
        return [], set(), executables
    return parse_ccc(game_path / "Skyrim.ccc"), scan_game_data_plugins(game_path), executables


def resolve_overwrite_dir(mo2_base: Path) -> Path:
    """The instance's Overwrite folder. MO2 lets [Settings]
    overwrite_directory relocate it (with %BASE_DIR% meaning the instance
    base); default is <mo2_base>/overwrite. Never hard-code the default at a
    call site -- Phase 3 swaps this provider for an MO2-API-backed one
    (CLAUDE.md Phase 2 decision 4)."""
    mo2_base = Path(mo2_base)
    section = ""
    for line in _read_ini_lines(mo2_base / "ModOrganizer.ini"):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].lower()
            continue
        if section == "settings" and stripped.lower().startswith("overwrite_directory="):
            value = _unwrap_value(stripped.split("=", 1)[1])
            if value:
                return Path(value.replace("%BASE_DIR%", str(mo2_base)))
    return mo2_base / "overwrite"


def read_overwrite_files(mo2_base: Path) -> list[str]:
    """Normalized relative paths of every file in Overwrite. The filesystem
    implementation behind the swappable Overwrite provider seam; checks only
    ever see the resulting plain list on Setup.overwrite_files."""
    from mo2audit.parsing.filescan import scan_mod_files

    return scan_mod_files(resolve_overwrite_dir(mo2_base))
