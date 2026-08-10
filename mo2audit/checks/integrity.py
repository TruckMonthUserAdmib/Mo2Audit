"""MISSING_MASTER, MASTER_ORDER, MALFORMED_PLUGIN_HEADER, LOADORDER_MISMATCH."""

from __future__ import annotations

from mo2audit.checks import register
from mo2audit.classify.types import SetupClassification
from mo2audit.model import Finding, Setup

BASE_GAME_MASTERS = ("Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm")
BASE_GAME_MASTERS_LOWER = {m.lower() for m in BASE_GAME_MASTERS}


@register("MISSING_MASTER")
def check_missing_master(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    classification = classification or SetupClassification()
    # The satisfied-set has three legitimate sources (spec 1.1 cause 3):
    # base-game masters, enabled plugins.txt entries, and presence-verified
    # CC-manifest plugins. Name-blind by design -- no per-mod special cases.
    satisfied_lower = (
        BASE_GAME_MASTERS_LOWER
        | {p.filename.lower() for p in setup.plugins if p.enabled}
        | classification.cc_provided_plugins
    )
    findings: list[Finding] = []

    for plugin in setup.plugins:
        if not plugin.enabled:
            continue
        missing = [m for m in plugin.masters if m.lower() not in satisfied_lower]
        if missing:
            findings.append(
                Finding(
                    check_id="MISSING_MASTER",
                    severity="critical",
                    title=f"{plugin.filename} is missing required master(s)",
                    detail=f"Master(s) not present or not enabled: {', '.join(missing)}.",
                    affected=[plugin.filename, *missing],
                    fix=f"Install and enable {', '.join(missing)}, or disable {plugin.filename}.",
                )
            )
    return findings


@register("MASTER_ORDER")
def check_master_order(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    load_index_by_name_lower = {p.filename.lower(): p.load_index for p in setup.plugins}
    findings: list[Finding] = []

    for plugin in setup.plugins:
        if not plugin.enabled:
            continue
        for master in plugin.masters:
            master_lower = master.lower()
            if master_lower in BASE_GAME_MASTERS_LOWER:
                continue  # always present, always first
            master_index = load_index_by_name_lower.get(master_lower)
            if master_index is None:
                continue  # missing entirely -- MISSING_MASTER's concern
            if master_index >= plugin.load_index:
                findings.append(
                    Finding(
                        check_id="MASTER_ORDER",
                        severity="critical",
                        title=f"{plugin.filename} loads before its master {master}",
                        detail=f"{master} must load before {plugin.filename} in the right pane.",
                        affected=[plugin.filename, master],
                        fix=f"Move {master} above {plugin.filename} in the load order.",
                    )
                )
    return findings


@register("MALFORMED_PLUGIN_HEADER")
def check_malformed_plugin_header(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for plugin in setup.plugins:
        if plugin.parse_error:
            findings.append(
                Finding(
                    check_id="MALFORMED_PLUGIN_HEADER",
                    severity="warning",
                    title=f"{plugin.filename} could not be parsed",
                    detail=plugin.parse_error,
                    affected=[plugin.filename],
                    fix="Re-download or reinstall this plugin -- its header may be corrupt or truncated.",
                )
            )
    return findings


@register("LOADORDER_MISMATCH")
def check_loadorder_mismatch(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    if not setup.loadorder:
        return []

    loadorder_pos = {name.lower(): i for i, name in enumerate(setup.loadorder)}
    shared = [p for p in setup.plugins if p.filename.lower() in loadorder_pos]

    findings: list[Finding] = []
    for i, a in enumerate(shared):
        for b in shared[i + 1 :]:
            plugins_order = a.load_index < b.load_index
            loadorder_order = loadorder_pos[a.filename.lower()] < loadorder_pos[b.filename.lower()]
            if plugins_order != loadorder_order:
                findings.append(
                    Finding(
                        check_id="LOADORDER_MISMATCH",
                        severity="warning",
                        title=f"{a.filename} and {b.filename} disagree between plugins.txt and loadorder.txt",
                        detail="The two files should agree on the relative order of any entries they share.",
                        affected=[a.filename, b.filename],
                        fix="Re-sort with LOOT; one of these files may be stale relative to the other.",
                    )
                )
    return findings
