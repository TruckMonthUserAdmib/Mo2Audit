"""Pure heuristic predicates over a mod's contributed files and Setup
evidence. No filesystem access -- everything works on the normalized
(lowercase, forward-slash) relative paths from Setup.file_index and the
plain-data Setup fields parsed by parsing/gameconfig.py.
"""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath

from mo2audit.classify import known


def name_matches_any(mod_name: str, patterns: tuple[str, ...]) -> str | None:
    """First matching substring pattern, or None."""
    lowered = mod_name.lower()
    for pattern in patterns:
        if pattern in lowered:
            return pattern
    return None


def is_generated_output_name(mod_name: str) -> bool:
    """Generator keyword AND output keyword -- 'FNIS - Output' yes, 'FNIS
    Behavior SE' no. Same rule as checks/rules.py."""
    return (
        name_matches_any(mod_name, known.GENERATOR_NAME_PATTERNS) is not None
        and name_matches_any(mod_name, known.OUTPUT_KEYWORD_PATTERNS) is not None
    )


def generated_signature_files(files: list[str]) -> set[str]:
    """Paths matching generated-output file signatures, any mod, any type."""
    result: set[str] = set()
    for path in files:
        basename = PurePosixPath(path).name
        if basename in known.GENERATED_OUTPUT_BASENAMES:
            result.add(path)
            continue
        if any(fnmatch.fnmatch(basename, glob) for glob in known.GENERATED_OUTPUT_BASENAME_GLOBS):
            result.add(path)
    return result


def plugin_basenames(files: list[str]) -> set[str]:
    return {PurePosixPath(p).name for p in files if p.endswith(known.PLUGIN_EXTENSIONS)}


def has_exe_without_plugins(files: list[str]) -> bool:
    """An .exe anywhere and zero plugin files -> tool-shaped. The no-plugins
    guard keeps content mods that bundle a utility exe classified as CONTENT
    (a TOOL tag would wrongly exempt their plugins from checks)."""
    has_exe = any(p.endswith(".exe") for p in files)
    return has_exe and not plugin_basenames(files)


def is_registered_executable_mod(mod_name: str, mo2_executables: list[str]) -> bool:
    """True if a registered MO2 executable's binary lives inside this mod's
    folder (path contains /mods/<mod name>/)."""
    needle = f"/mods/{mod_name.lower()}/"
    for exe_path in mo2_executables:
        normalized = exe_path.replace("\\", "/").lower()
        if needle in normalized:
            return True
    return False


def has_preset_path(files: list[str]) -> bool:
    for path in files:
        if any(segment in path.split("/") for segment in known.PRESET_PATH_SEGMENTS):
            return True
    return False


def is_config_only(files: list[str]) -> bool:
    """Every file is a config-type file; no plugins, no archives, no game
    assets. Data-free by design."""
    if not files:
        return False
    return all(path.endswith(known.CONFIG_ONLY_EXTENSIONS) for path in files)


def ships_skse_dll_without_plugin(files: list[str]) -> bool:
    has_dll = any(p.startswith("skse/plugins/") and p.endswith(".dll") for p in files)
    return has_dll and not plugin_basenames(files)


def has_game_data(files: list[str]) -> bool:
    """Recognized Data-relative top-level dir, or a plugin/archive at root --
    the same notion of 'valid game data' as NO_VALID_GAME_DATA."""
    for path in files:
        top = path.split("/", 1)[0]
        if top in known.RECOGNIZED_DATA_DIRS:
            return True
        if "/" not in path and path.endswith(known.PLUGIN_EXTENSIONS + (".bsa",)):
            return True
    return False
