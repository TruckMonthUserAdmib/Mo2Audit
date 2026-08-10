"""Data model for MO2 Load Order Auditor. Dataclasses only, no behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModEntry:
    name: str
    enabled: bool
    priority: int  # higher wins conflicts
    is_separator: bool
    is_unmanaged: bool
    path: Path | None


@dataclass
class ModMeta:
    nexus_mod_id: int | None
    version: str | None
    newest_version: str | None
    install_file: str | None


@dataclass
class PluginEntry:
    filename: str
    enabled: bool
    load_index: int
    owning_mod: str | None
    is_esm: bool
    is_esl: bool
    masters: list[str]
    parse_error: str | None = None
    hedr_num_records: int | None = None


@dataclass
class Finding:
    check_id: str  # e.g. "OVERWRITE_GENERATED_OUTPUT"
    severity: str  # "critical" | "warning" | "info"
    title: str
    detail: str
    affected: list[str]  # mod or plugin names
    fix: str  # imperative, specific, actionable
    # Root-cause keys for report-layer cross-referencing (Phase 2 spec 6.2):
    # (overriding_mod, overridden_mod) pairs this finding is about. Findings
    # from different checks sharing a pair are one root cause; the reporter
    # merges them at the higher severity. Empty = never merged.
    pair_keys: list[tuple[str, str]] = field(default_factory=list)
    # mod name -> classified type value, for affected mods where the check's
    # logic consulted classification (spec section 7: helps the user see why
    # a mod was or wasn't flagged). Empty when not relevant.
    mod_types: dict[str, str] = field(default_factory=dict)


@dataclass
class Setup:
    mo2_base: Path
    profile: str
    mods: list[ModEntry]
    plugins: list[PluginEntry]
    meta: dict[str, ModMeta]
    file_index: dict[str, list[str]]  # normalized rel path -> mod names, priority ascending
    loadorder: list[str] = field(default_factory=list)
    overwrite_files: list[str] = field(default_factory=list)
    # Phase 2 (parsing/gameconfig.py). All absent-is-normal: empty means the
    # game folder / ModOrganizer.ini evidence was unavailable, never an error.
    ccc_managed_plugins: list[str] = field(default_factory=list)  # Skyrim.ccc lines, file order
    game_data_plugins: set[str] = field(default_factory=set)  # lowercase plugin basenames in <game>/Data
    mo2_executables: list[str] = field(default_factory=list)  # registered executable binary paths
