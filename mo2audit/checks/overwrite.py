"""OVERWRITE_GENERATED_OUTPUT (the flagship check) and LOOSE_FILE_CONFLICT."""

from __future__ import annotations

from mo2audit.checks import register
from mo2audit.classify.types import SetupClassification
from mo2audit.checks.rules import GENERATOR_NAME_PATTERNS, OUTPUT_KEYWORD_PATTERNS, XPMSE_PATTERNS
from mo2audit.model import Finding, Setup


def _is_output_mod(name: str) -> bool:
    lowered = name.lower()
    has_generator = any(p in lowered for p in GENERATOR_NAME_PATTERNS)
    has_output_keyword = any(p in lowered for p in OUTPUT_KEYWORD_PATTERNS)
    return has_generator and has_output_keyword


def _is_xpmse(name: str) -> bool:
    lowered = name.lower()
    return any(p in lowered for p in XPMSE_PATTERNS)


def _paths_by_mod(setup: Setup) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path, contributors in setup.file_index.items():
        for name in contributors:
            result.setdefault(name, set()).add(path)
    return result


# --- Override directionality (Phase 2 spec 6.1, CLAUDE.md decision 3) -------
#
# Breadth is a property of a mod's ENTIRE contributed file set, not just the
# conflicting paths. Primary basis: distinct facegen stems (FormID-named, one
# per NPC) -- used only when BOTH mods have a facegen fingerprint. Fallback:
# total file count, which is coarser; the label says which basis was used.
# The output is a SOFT suggestion: severity stays "info" for every label.

FACEGEN_PATH_SEGMENTS = ("facegendata/facegeom/", "facegendata/facetint/")

# The broader mod must have at least this multiple of the narrower's breadth
# before the pair stops being "comparable". Calibrated against the test log's
# real tiers: Lydia 1 NPC vs Bijin ~5 (ratio 5, flags) vs Dibella's ~250
# (ratio ~50, waves through as specific-over-general).
BREADTH_RATIO = 3.0

FACEGEN_BASIS = "distinct NPCs via facegen files"
FILECOUNT_BASIS = "total file count (coarser fallback; no facegen fingerprint)"


def _facegen_stems(paths: set[str]) -> set[str]:
    """Distinct facegen file stems = distinct NPCs touched. The same FormID
    stem appearing under both facegeom (mesh) and facetint (texture) is one
    NPC, so a set of stems dedupes it naturally."""
    stems: set[str] = set()
    for path in paths:
        if any(segment in path for segment in FACEGEN_PATH_SEGMENTS):
            name = path.rsplit("/", 1)[-1]
            stems.add(name.rsplit(".", 1)[0])
    return stems


def _pair_breadth(winner_paths: set[str], loser_paths: set[str]) -> tuple[int, int, str]:
    """(winner_breadth, loser_breadth, basis) for one conflict pair."""
    winner_stems = _facegen_stems(winner_paths)
    loser_stems = _facegen_stems(loser_paths)
    if winner_stems and loser_stems:
        return len(winner_stems), len(loser_stems), FACEGEN_BASIS
    return len(winner_paths), len(loser_paths), FILECOUNT_BASIS


def _directional_fix(winner: str, loser: str, winner_breadth: int, loser_breadth: int, basis: str) -> str:
    verbose_hint = "Pass --verbose-conflicts to see the full per-file list."
    if winner_breadth >= BREADTH_RATIO * loser_breadth:
        return (
            f"Possibly unintended -- a specific mod is being overridden by a broader one "
            f"({loser}: breadth {loser_breadth} vs {winner}: breadth {winner_breadth}, "
            f"measured by {basis}); verify this is what you want. {verbose_hint}"
        )
    if loser_breadth >= BREADTH_RATIO * winner_breadth:
        return (
            f"Likely intentional -- specific-over-general ({winner}: breadth {winner_breadth} "
            f"vs {loser}: breadth {loser_breadth}, measured by {basis}). {verbose_hint}"
        )
    return f"Likely intentional; verify if unsure (comparable breadth, measured by {basis}). {verbose_hint}"


@register("OVERWRITE_GENERATED_OUTPUT")
def check_overwrite_generated_output(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    enabled_mods = [m for m in setup.mods if m.enabled and not m.is_separator]
    output_mods = [m for m in enabled_mods if _is_output_mod(m.name)]
    if not output_mods:
        return []

    paths_by_mod = _paths_by_mod(setup)
    findings: list[Finding] = []

    for output_mod in output_mods:
        output_paths = paths_by_mod.get(output_mod.name, set())
        if not output_paths:
            continue

        overriding_counts: dict[str, int] = {}
        for other in enabled_mods:
            if other.name == output_mod.name or other.priority <= output_mod.priority:
                continue
            overlap = output_paths & paths_by_mod.get(other.name, set())
            if overlap:
                overriding_counts[other.name] = len(overlap)

        if not overriding_counts:
            continue

        overriding_names = sorted(overriding_counts, key=lambda n: -overriding_counts[n])
        xpmse_hit = next((n for n in overriding_names if _is_xpmse(n)), None)

        detail = "; ".join(f"{name} overrides {count} file(s)" for name, count in overriding_counts.items())
        if xpmse_hit:
            detail += (
                f". {xpmse_hit} ships its own behavior files and must be overridden by "
                f"{output_mod.name} -- this is the most common single cause of this bug."
            )

        findings.append(
            Finding(
                check_id="OVERWRITE_GENERATED_OUTPUT",
                severity="critical",
                title=f"{output_mod.name} is outranked by mod(s) it must override",
                detail=detail,
                affected=[output_mod.name, *overriding_names],
                fix=f"Drag {output_mod.name} to the bottom of the left pane (highest priority), then regenerate it.",
                pair_keys=[(name, output_mod.name) for name in overriding_names],
            )
        )

    return findings


@register("LOOSE_FILE_CONFLICT")
def check_loose_file_conflict(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    priority_by_name = {m.name: m.priority for m in setup.mods}
    enabled = {m.name for m in setup.mods if m.enabled and not m.is_separator}

    pair_paths: dict[tuple[str, str], list[str]] = {}
    for path, contributors in setup.file_index.items():
        enabled_contributors = [c for c in contributors if c in enabled]
        if len(enabled_contributors) < 2:
            continue
        winner = max(enabled_contributors, key=lambda n: priority_by_name[n])
        for loser in enabled_contributors:
            if loser == winner:
                continue
            pair_paths.setdefault((winner, loser), []).append(path)

    paths_by_mod = _paths_by_mod(setup)

    findings: list[Finding] = []
    for (winner, loser), paths in sorted(
        pair_paths.items(), key=lambda kv: (-priority_by_name[kv[0][0]], kv[0][1])
    ):
        winner_breadth, loser_breadth, basis = _pair_breadth(
            paths_by_mod.get(winner, set()), paths_by_mod.get(loser, set())
        )
        findings.append(
            Finding(
                check_id="LOOSE_FILE_CONFLICT",
                severity="info",
                title=f"{winner} overrides {len(paths)} file(s) from {loser}",
                detail=", ".join(sorted(paths)),
                affected=[winner, loser],
                fix=_directional_fix(winner, loser, winner_breadth, loser_breadth, basis),
                pair_keys=[(winner, loser)],
            )
        )
    return findings
