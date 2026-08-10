"""ENABLED_MOD_NO_PLUGIN, ORPHANED_PLUGIN / PLUGIN_IN_OVERWRITE,
DISABLED_MOD_ENABLED_PLUGIN.

Ownership matrix so these don't double-report the same root cause (also
covers MISSING_MASTER/MASTER_ORDER/MALFORMED_PLUGIN_HEADER in integrity.py):

  mod enabled? | plugin on disk? | plugin listed? | plugin enabled? | check
  ------------ | --------------- | --------------- | --------------- | -----
  yes          | yes             | no              | -               | ENABLED_MOD_NO_PLUGIN
  -            | no              | yes             | -               | ORPHANED_PLUGIN / PLUGIN_IN_OVERWRITE
  yes          | yes             | yes             | no              | DISABLED_MOD_ENABLED_PLUGIN
  no           | yes             | yes             | yes             | DISABLED_MOD_ENABLED_PLUGIN
"""

from __future__ import annotations

from pathlib import PurePosixPath

from mo2audit.checks import register
from mo2audit.classify.types import SetupClassification
from mo2audit.model import Finding, Setup

PLUGIN_EXTENSIONS = (".esp", ".esm", ".esl")


def _mod_plugin_basenames(setup: Setup, mod_name: str) -> set[str]:
    result = set()
    for path, contributors in setup.file_index.items():
        if mod_name not in contributors:
            continue
        if path.endswith(PLUGIN_EXTENSIONS):
            result.add(PurePosixPath(path).name)
    return result


@register("ENABLED_MOD_NO_PLUGIN")
def check_enabled_mod_no_plugin(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    classification = classification or SetupClassification()
    listed_lower = {p.filename.lower() for p in setup.plugins}
    # Plugins the game auto-loads via the CC manifest mechanism are visible
    # to the game without a plugins.txt line -- their absence from the list
    # is normal, not "MO2 cannot see it" (spec 1.1 cause 1).
    visible_lower = listed_lower | classification.cc_provided_plugins
    findings: list[Finding] = []

    for mod in setup.mods:
        if not mod.enabled or mod.is_separator:
            continue
        missing = sorted(b for b in _mod_plugin_basenames(setup, mod.name) if b not in visible_lower)
        if missing:
            findings.append(
                Finding(
                    check_id="ENABLED_MOD_NO_PLUGIN",
                    severity="warning",
                    title=f"{mod.name} ships a plugin MO2 cannot see",
                    detail=f"Plugin file(s) {', '.join(missing)} exist in this mod's folder but are absent from plugins.txt.",
                    affected=[mod.name, *missing],
                    fix="Check the archive's folder structure -- the plugin is likely nested one directory level too deep, or was deselected in a FOMOD.",
                    mod_types={mod.name: classification.effective_type(mod.name).value},
                )
            )
    return findings


@register("ORPHANED_PLUGIN")
def check_orphaned_plugin(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    classification = classification or SetupClassification()
    enabled_mod_names = {m.name for m in setup.mods if m.enabled and not m.is_separator}
    # overwrite_files carries full relative paths (Phase 2); compare plugin
    # BASENAMES -- which also keeps bare-basename hand-built Setups working.
    overwrite_lower = {
        PurePosixPath(f).name.lower() for f in setup.overwrite_files if f.lower().endswith(PLUGIN_EXTENSIONS)
    }

    owners: dict[str, set[str]] = {}
    for path, contributors in setup.file_index.items():
        if not path.endswith(PLUGIN_EXTENSIONS):
            continue
        basename = PurePosixPath(path).name
        for name in contributors:
            if name in enabled_mod_names:
                owners.setdefault(basename, set()).add(name)

    findings: list[Finding] = []
    for plugin in setup.plugins:
        basename_lower = plugin.filename.lower()
        if owners.get(basename_lower):
            continue
        if basename_lower in classification.cc_provided_plugins:
            # Present via the CC mechanism (game Data / manifest), just not
            # owned by a mod folder. cc_provided is presence-verified, so a
            # listed cc* plugin whose files exist NOWHERE still falls
            # through to ORPHANED_PLUGIN below (the 1.5.97 case).
            continue

        if basename_lower in overwrite_lower:
            findings.append(
                Finding(
                    check_id="PLUGIN_IN_OVERWRITE",
                    severity="info",
                    title=f"{plugin.filename} lives in the Overwrite folder",
                    detail="Not owned by any enabled mod -- likely generated loose into Overwrite.",
                    affected=[plugin.filename],
                    fix="Pack it into a proper mod, or confirm this is intentional generated output.",
                )
            )
        else:
            findings.append(
                Finding(
                    check_id="ORPHANED_PLUGIN",
                    severity="warning",
                    title=f"{plugin.filename} is listed but not owned by any enabled mod",
                    detail="Usually left over from a removed or disabled mod.",
                    affected=[plugin.filename],
                    fix=f"Remove {plugin.filename} from plugins.txt, or re-enable the mod that provides it.",
                )
            )
    return findings


@register("DISABLED_MOD_ENABLED_PLUGIN")
def check_disabled_mod_enabled_plugin(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    plugin_by_filename_lower = {p.filename.lower(): p for p in setup.plugins}
    findings: list[Finding] = []

    for mod in setup.mods:
        if mod.is_separator:
            continue
        for basename in _mod_plugin_basenames(setup, mod.name):
            plugin = plugin_by_filename_lower.get(basename)
            if plugin is None:
                continue  # ENABLED_MOD_NO_PLUGIN's concern, not this check's

            if mod.enabled and not plugin.enabled:
                findings.append(
                    Finding(
                        check_id="DISABLED_MOD_ENABLED_PLUGIN",
                        severity="warning",
                        title=f"{mod.name} is enabled but its plugin {plugin.filename} is disabled",
                        detail="Partial toggle: the mod is active in the left pane but its plugin is unchecked in plugins.txt.",
                        affected=[mod.name, plugin.filename],
                        fix=f"Enable {plugin.filename} in the right pane, or disable {mod.name} if it isn't meant to be active.",
                    )
                )
            elif not mod.enabled and plugin.enabled:
                findings.append(
                    Finding(
                        check_id="DISABLED_MOD_ENABLED_PLUGIN",
                        severity="warning",
                        title=f"{mod.name} is disabled but its plugin {plugin.filename} is enabled",
                        detail="Partial toggle: the mod is inactive in the left pane but its plugin is still checked in plugins.txt.",
                        affected=[mod.name, plugin.filename],
                        fix=f"Disable {plugin.filename} in the right pane, or re-enable {mod.name} if it's meant to be active.",
                    )
                )
    return findings
