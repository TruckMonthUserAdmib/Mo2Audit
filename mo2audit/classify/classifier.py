"""Orchestrates classification: Setup in, SetupClassification out.

Pure function of the parsed Setup -- no filesystem, no MO2 API. Precedence
is ordered most-specific-first; the FIRST rule that fires assigns the
primary type. Declarative name knowledge outranks structural guesses, and
generated-output NAMES are checked before tool names so "FNIS - Output"
classifies as GENERATED_OUTPUT while "FNIS Behavior SE" classifies as TOOL
(the file-level generated_output_files channel covers the tool's own
generated files either way -- CLAUDE.md Phase 2 decision 1).
"""

from __future__ import annotations

from pathlib import PurePosixPath

from mo2audit.classify import heuristics, known
from mo2audit.classify.types import ModClassification, ModType, SetupClassification
from mo2audit.model import ModEntry, Setup

_DATA_FREE_TYPES = {ModType.TOOL, ModType.PRESET_CONFIG, ModType.RESOURCE_FRAMEWORK, ModType.SEPARATOR}


def _mod_files(setup: Setup) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {mod.name: [] for mod in setup.mods}
    for path, contributors in setup.file_index.items():
        for name in contributors:
            if name in result:
                result[name].append(path)
    return result


def _cc_mechanism_names(setup: Setup, present_plugins: set[str]) -> tuple[set[str], str]:
    """(lowercase plugin names loadable via the CC mechanism, reason).

    Manifest primary; cc* pattern + known extras as offline fallback. The
    fallback can only ever name PRESENT files -- with no manifest there is
    no evidence for anything absent."""
    if setup.ccc_managed_plugins:
        return {name.lower() for name in setup.ccc_managed_plugins}, "Skyrim.ccc manifest"
    fallback = {
        name
        for name in present_plugins
        if name.startswith(known.CC_PLUGIN_NAME_PREFIX) or name in known.CC_EXTRA_MANIFEST_PLUGINS
    }
    return fallback, "cc* name-pattern fallback (no Skyrim.ccc manifest available)"


def _classify_mod(
    mod: ModEntry,
    files: list[str],
    cc_names: set[str],
    cc_reason: str,
    mo2_executables: list[str],
) -> ModClassification:
    def result(mod_type: ModType, confidence: float, reason: str) -> ModClassification:
        return ModClassification(
            mod_name=mod.name,
            mod_type=mod_type,
            confidence=confidence,
            reasons=[reason],
            is_data_free_by_design=mod_type in _DATA_FREE_TYPES,
        )

    if mod.is_separator:
        return result(ModType.SEPARATOR, 1.0, "MO2 separator entry")

    if heuristics.is_generated_output_name(mod.name):
        return result(ModType.GENERATED_OUTPUT, 0.9, "name matches generator + output keyword pattern")

    framework = heuristics.name_matches_any(mod.name, known.KNOWN_FRAMEWORK_PATTERNS)
    if framework is not None:
        return result(ModType.RESOURCE_FRAMEWORK, 0.9, f"known framework name ({framework!r})")

    if heuristics.is_config_only(files) and ("preset" in mod.name.lower() or heuristics.has_preset_path(files)):
        return result(ModType.PRESET_CONFIG, 0.8, "config-type files only, preset name/path")

    tool = heuristics.name_matches_any(mod.name, known.KNOWN_TOOL_PATTERNS)
    if tool is not None:
        return result(ModType.TOOL, 0.9, f"known tool name ({tool!r})")

    if heuristics.is_registered_executable_mod(mod.name, mo2_executables):
        return result(ModType.TOOL, 0.85, "registered as an MO2 executable")

    mod_plugins = {name.lower() for name in heuristics.plugin_basenames(files)}
    if mod_plugins and mod_plugins <= cc_names:
        return result(ModType.CC_CONTENT, 0.9, f"all plugin files load via the CC mechanism ({cc_reason})")

    if heuristics.has_exe_without_plugins(files):
        return result(ModType.TOOL, 0.7, "ships an executable and no plugins")

    if heuristics.generated_signature_files(files):
        return result(ModType.GENERATED_OUTPUT, 0.7, "contains generated-output signature files")

    if heuristics.is_config_only(files):
        return result(ModType.PRESET_CONFIG, 0.6, "config-type files only")

    if heuristics.ships_skse_dll_without_plugin(files):
        return result(ModType.RESOURCE_FRAMEWORK, 0.6, "SKSE DLL plugin, no esp")

    if heuristics.has_game_data(files) or mod_plugins:
        return result(ModType.CONTENT, 0.5, "ships game data and/or plugins")

    if files:
        return result(ModType.UNKNOWN, 0.0, "files present but no signal matched (treated as CONTENT)")
    return result(ModType.UNKNOWN, 0.0, "no files indexed (treated as CONTENT)")


def classify_setup(setup: Setup) -> SetupClassification:
    """Classify every mod in setup; emit cc_provided_plugins (presence-
    verified CC-mechanism plugins) and generated_output_files (file-level)."""
    mod_files = _mod_files(setup)

    enabled_mods = {m.name for m in setup.mods if m.enabled and not m.is_separator}
    present_plugins = set(setup.game_data_plugins)
    for path, contributors in setup.file_index.items():
        if path.endswith(known.PLUGIN_EXTENSIONS) and any(name in enabled_mods for name in contributors):
            present_plugins.add(PurePosixPath(path).name)

    cc_names, cc_reason = _cc_mechanism_names(setup, present_plugins)
    cc_provided = cc_names & present_plugins

    mods: dict[str, ModClassification] = {}
    generated_output_files: dict[str, set[str]] = {}
    for mod in setup.mods:
        files = mod_files.get(mod.name, [])
        mods[mod.name] = _classify_mod(mod, files, cc_names, cc_reason, setup.mo2_executables)
        signatures = heuristics.generated_signature_files(files)
        if signatures:
            generated_output_files[mod.name] = signatures

    return SetupClassification(
        mods=mods,
        cc_provided_plugins=cc_provided,
        generated_output_files=generated_output_files,
    )
