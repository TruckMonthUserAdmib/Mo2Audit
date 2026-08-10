"""OVERWRITE_HYGIENE -- the three-tier Overwrite model (Phase 2 spec 6.3).

Tiers, checked in order:
- NOISE: logs and housekeeping (SKSE logs, FNIS "don't ask again" txt).
  Never flagged -- flagging these would cry wolf on nearly every install.
- SUBSTANTIVE: generated content that should become a managed mod so its
  priority is explicit (generator output signatures, plugins/BSAs, built
  meshes/textures, xEdit cache). Warning.
- AMBIGUOUS CONFIG: everything else, surfaced gently at info -- generated
  configs like GrassControl.ini hold real settings but may be regenerated;
  only the user's workflow knows. Unmatched files land here deliberately
  (false-positive over false-negative: never silently ignored).

Known limitation (spec 6.3 design note, proven in Test 6): generator output
does NOT reliably land in Overwrite -- a BodySlide build can go straight
into the source mod. This check covers the Overwrite case only; detecting
generated output absorbed into content mods is future work.

The generated-output signatures duplicate classify/known.py's (checks may
import classify/types only); tests/test_acceptance_hygiene.py asserts
parity so they cannot drift.
"""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath

from mo2audit.checks import register
from mo2audit.classify.types import SetupClassification
from mo2audit.model import Finding, Setup

NOISE_EXTENSIONS = (".log",)
NOISE_PATH_SEGMENTS = ("logs/", "crashdumps/")
NOISE_BASENAME_GLOBS = ("*dontask*", "*logfile*")

# Must stay a superset of classify/known.py's generated-output signatures.
SUBSTANTIVE_BASENAMES = (
    "animationdatasinglefile.txt",
    "animationsetdatasinglefile.txt",
)
SUBSTANTIVE_BASENAME_GLOBS = (
    "fnis_*.pex",
    "dyndolod_*",
    "texgen_*",
)
SUBSTANTIVE_EXTENSIONS = (".esp", ".esm", ".esl", ".bsa", ".refcache")
SUBSTANTIVE_TOP_DIRS = ("meshes", "textures")
SUBSTANTIVE_PATH_SEGMENTS = ("edit cache/",)


def classify_overwrite_path(path: str) -> str:
    """'noise' | 'substantive' | 'ambiguous' for one normalized rel path."""
    basename = PurePosixPath(path).name
    if (
        path.endswith(NOISE_EXTENSIONS)
        or any(segment in path for segment in NOISE_PATH_SEGMENTS)
        or any(fnmatch.fnmatch(basename, glob) for glob in NOISE_BASENAME_GLOBS)
    ):
        return "noise"
    if (
        basename in SUBSTANTIVE_BASENAMES
        or any(fnmatch.fnmatch(basename, glob) for glob in SUBSTANTIVE_BASENAME_GLOBS)
        or path.endswith(SUBSTANTIVE_EXTENSIONS)
        or path.split("/", 1)[0] in SUBSTANTIVE_TOP_DIRS
        or any(segment in path for segment in SUBSTANTIVE_PATH_SEGMENTS)
    ):
        return "substantive"
    return "ambiguous"


@register("OVERWRITE_HYGIENE")
def check_overwrite_hygiene(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    substantive: list[str] = []
    ambiguous: list[str] = []
    for path in setup.overwrite_files:
        tier = classify_overwrite_path(path)
        if tier == "substantive":
            substantive.append(path)
        elif tier == "ambiguous":
            ambiguous.append(path)

    findings: list[Finding] = []
    if substantive:
        findings.append(
            Finding(
                check_id="OVERWRITE_HYGIENE",
                severity="warning",
                title=f"Overwrite holds {len(substantive)} file(s) of substantive generated content",
                detail=", ".join(sorted(substantive)),
                affected=["Overwrite"],
                fix=(
                    "Use 'Create Mod from Overwrite' (right-click Overwrite) to save this as a "
                    "named, positioned mod -- loose in Overwrite it always wins priority, which "
                    "hides the ordering problems the OVERWRITE_GENERATED_OUTPUT check exists to catch."
                ),
            )
        )
    if ambiguous:
        findings.append(
            Finding(
                check_id="OVERWRITE_HYGIENE",
                severity="info",
                title=f"Generated config sitting in Overwrite ({len(ambiguous)} file(s))",
                detail=", ".join(sorted(ambiguous)),
                affected=["Overwrite"],
                fix=(
                    "You may want to save this as a mod to keep the settings, or it may simply be "
                    "regenerated next run -- check the generating tool's workflow. Harmless either way."
                ),
            )
        )
    return findings
