"""walk mods dir -> per-mod file index.

Large setups have 150+ mods and 100k+ files. Build the index in a single
os.scandir pass per directory; never stat files repeatedly.
"""

from __future__ import annotations

import os
from pathlib import Path

from mo2audit.model import ModEntry

# meta.ini (spec 5.4) always lives at the mod folder's root and is MO2's own
# bookkeeping about the mod -- never Data content the mod contributes. If
# it isn't excluded here, every mod that has one (nearly all of them)
# spuriously "conflicts" with every other mod over the identical literal
# path "meta.ini", which produces false OVERWRITE_GENERATED_OUTPUT and
# LOOSE_FILE_CONFLICT findings against the highest-priority mod. Caught by
# running against a real 150-mod install (see MO2-Audit-SPEC.md history).
_EXCLUDED_ROOT_FILES = {"meta.ini"}


def scan_mod_files(mod_path: Path) -> list[str]:
    """Normalized (lowercase, forward-slash) relative paths under mod_path."""
    mod_path = Path(mod_path)
    if not mod_path.is_dir():
        return []

    results: list[str] = []

    def _walk(dir_path: Path) -> None:
        with os.scandir(dir_path) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    _walk(Path(entry.path))
                else:
                    rel = Path(entry.path).relative_to(mod_path)
                    rel_str = str(rel).replace("\\", "/").lower()
                    if rel_str in _EXCLUDED_ROOT_FILES:
                        continue
                    results.append(rel_str)

    _walk(mod_path)
    return results


def build_file_index(mods: list[ModEntry]) -> dict[str, list[str]]:
    """path -> [mod names], ordered by ascending priority.

    Indexes every mod folder present on disk regardless of ModEntry.enabled
    -- enabled-only filtering is a checks-layer concern, since several
    checks need to reason about disabled-but-present mods too. Separators
    have no folder and are skipped.
    """
    index: dict[str, list[str]] = {}
    for mod in sorted(mods, key=lambda m: m.priority):
        if mod.is_separator or mod.path is None:
            continue
        for rel_path in scan_mod_files(mod.path):
            index.setdefault(rel_path, []).append(mod.name)
    return index
