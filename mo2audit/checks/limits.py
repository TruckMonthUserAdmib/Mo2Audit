"""PLUGIN_LIMIT, NO_VALID_GAME_DATA."""

from __future__ import annotations

import math

from mo2audit.checks import register
from mo2audit.classify.types import ModType, SetupClassification
from mo2audit.checks.integrity import BASE_GAME_MASTERS
from mo2audit.model import Finding, Setup

NON_ESL_LIMIT = 254
ESL_LIMIT = 4096
ESL_CANDIDATE_RECORD_THRESHOLD = 2048
ESL_CANDIDATE_SURFACE_THRESHOLD = 200

RECOGNIZED_TOP_LEVEL_DIRS = {
    "meshes",
    "textures",
    "scripts",
    "sound",
    "music",
    "interface",
    "seq",
    "shadersfx",
    "grass",
    "lodsettings",
    "dialogueviews",
    "skse",
    "strings",
    "video",
}
RECOGNIZED_ROOT_EXTENSIONS = (".esp", ".esm", ".esl", ".bsa")


def _tier(count: int, limit: int) -> str | None:
    if count >= limit:
        return "critical"
    if count >= math.ceil(0.9 * limit):
        return "warning"
    return None


@register("PLUGIN_LIMIT")
def check_plugin_limit(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    enabled = [p for p in setup.plugins if p.enabled]
    non_esl = [p for p in enabled if not p.is_esl]
    esl = [p for p in enabled if p.is_esl]

    # Base game masters count toward the 254 ceiling even though they're
    # absent from plugins.txt.
    non_esl_count = len(non_esl) + len(BASE_GAME_MASTERS)
    esl_count = len(esl)

    findings: list[Finding] = []

    non_esl_tier = _tier(non_esl_count, NON_ESL_LIMIT)
    if non_esl_tier:
        findings.append(
            Finding(
                check_id="PLUGIN_LIMIT",
                severity=non_esl_tier,
                title=f"{non_esl_count}/{NON_ESL_LIMIT} non-ESL plugin slots used",
                detail="Includes the 5 base game masters, which always count toward this ceiling.",
                affected=[],
                fix="Flag more plugins ESL/ESPFE where possible, or remove unused plugins.",
            )
        )

    esl_tier = _tier(esl_count, ESL_LIMIT)
    if esl_tier:
        findings.append(
            Finding(
                check_id="PLUGIN_LIMIT",
                severity=esl_tier,
                title=f"{esl_count}/{ESL_LIMIT} ESL-flagged plugin slots used",
                detail="",
                affected=[],
                fix="Remove or merge unused ESL-flagged plugins.",
            )
        )

    if non_esl_count > ESL_CANDIDATE_SURFACE_THRESHOLD:
        candidates = sorted(
            p.filename
            for p in non_esl
            if p.hedr_num_records is not None and p.hedr_num_records < ESL_CANDIDATE_RECORD_THRESHOLD
        )
        if candidates:
            findings.append(
                Finding(
                    check_id="PLUGIN_LIMIT",
                    severity="info",
                    title=f"{len(candidates)} plugin(s) may be ESL candidate(s) (heuristic)",
                    detail="Record count under 2048 per HEDR.numRecords. Not validated further; Phase 1 never flags automatically.",
                    affected=candidates,
                    fix="Review with xEdit/SSEEdit and flag as ESL/ESPFE if genuinely safe.",
                )
            )

    return findings


@register("NO_VALID_GAME_DATA")
def check_no_valid_game_data(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    classification = classification or SetupClassification()
    # Bucket file_index by mod in a single pass -- must stay cheap at 100k+ files.
    recognized_by_mod: dict[str, set[str]] = {}
    for path, contributors in setup.file_index.items():
        parts = path.split("/", 1)
        top = parts[0]
        is_root_file = len(parts) == 1
        for mod_name in contributors:
            bucket = recognized_by_mod.setdefault(mod_name, set())
            if is_root_file and top.endswith(RECOGNIZED_ROOT_EXTENSIONS):
                bucket.add("__valid_root_file__")
            elif top in RECOGNIZED_TOP_LEVEL_DIRS:
                bucket.add(top)

    findings: list[Finding] = []
    for mod in setup.mods:
        if mod.is_separator or mod.is_unmanaged or not mod.enabled:
            continue
        # Bug B fix (spec 5.3): only CONTENT mods can be "broken" by having
        # no game data. TOOL / PRESET_CONFIG / RESOURCE_FRAMEWORK /
        # GENERATED_OUTPUT are data-free or self-shaped by design.
        # effective_type maps UNKNOWN and unclassified to CONTENT, so a
        # genuinely mis-installed nested mod still fires -- the exemption is
        # type-based, never blanket.
        if classification.effective_type(mod.name) is not ModType.CONTENT:
            continue
        if not recognized_by_mod.get(mod.name):
            findings.append(
                Finding(
                    check_id="NO_VALID_GAME_DATA",
                    severity="warning",
                    title=f"{mod.name} has no recognized game-data content",
                    detail="No meshes/textures/scripts/etc folder and no .esp/.esm/.esl/.bsa at root.",
                    affected=[mod.name],
                    fix="Reinstall, checking the archive's internal folder structure -- the Data folder is likely nested one level too deep.",
                    mod_types={mod.name: classification.effective_type(mod.name).value},
                )
            )
    return findings
