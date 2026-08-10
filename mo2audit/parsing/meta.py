"""per-mod meta.ini -> ModMeta.

Absent for manually created mods (FNIS output, BodySlide output, Overwrite).
Absence is normal -- callers should not report it.
"""

from __future__ import annotations

import configparser
from pathlib import Path

from mo2audit.model import ModMeta


def parse_meta(path: Path) -> ModMeta | None:
    path = Path(path)
    if not path.is_file():
        return None

    parser = configparser.ConfigParser()
    parser.optionxform = str  # preserve key case as documented in spec 5.4
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error:
        return None

    if not parser.has_section("General"):
        return ModMeta(nexus_mod_id=None, version=None, newest_version=None, install_file=None)

    general = parser["General"]
    modid_raw = general.get("modid")
    nexus_mod_id = int(modid_raw) if modid_raw and modid_raw.lstrip("-").isdigit() else None

    return ModMeta(
        nexus_mod_id=nexus_mod_id,
        version=general.get("version") or None,
        newest_version=general.get("newestVersion") or None,
        install_file=general.get("installationFile") or None,
    )
