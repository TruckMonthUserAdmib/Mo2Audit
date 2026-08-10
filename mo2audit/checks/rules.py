"""Declarative pattern/rule tables, plus the KNOWN_ORDER_RULE check that
interprets ORDER_RULES. Data lives here; overwrite.py imports the pattern
constants directly.
"""

from __future__ import annotations

import fnmatch

from mo2audit.checks import register
from mo2audit.classify.types import SetupClassification
from mo2audit.model import Finding, Setup

# A mod is a generated-output mod if its name contains a generator keyword
# AND an output keyword. Bare generator-name matching alone is too broad --
# "FNIS Behavior SE" and "FNIS Spells SE" contain "fnis" but are the FNIS
# tool/component mods themselves, not its generated output; matching "fnis"
# alone misclassified them and produced a nonsense finding (caught by the
# flagship acceptance test in tests/test_checks_overwrite.py).
GENERATOR_NAME_PATTERNS = ("fnis", "nemesis", "bodyslide", "dyndolod", "texgen")
OUTPUT_KEYWORD_PATTERNS = ("output", "overwrite")

# XPMSE gets its own pattern set: it's never an output mod itself, but spec
# 7.1 calls out its behavior files as the single most common thing an
# output mod loses to, and real installs name it by full name, not the
# acronym -- match both.
XPMSE_PATTERNS = ("xpmse", "xp32")

# Closed two-value relation enum for Phase 1 -- do not add more without
# confirming first. A "*" target is documentation/aspirational only and is
# never evaluated (no numeric threshold is defined for it).
ORDER_RULES: list[tuple[str, str, str]] = [
    ("Unofficial Skyrim Special Edition Patch", "*", "should_be_early"),
    ("*occlusion*", "JK's Skyrim", "should_load_after"),
]


def _name_matches(pattern: str, name: str) -> bool:
    return fnmatch.fnmatch(name.lower(), pattern.lower())


@register("KNOWN_ORDER_RULE")
def check_known_order_rule(setup: Setup, classification: SetupClassification | None = None) -> list[Finding]:
    enabled_mods = [m for m in setup.mods if m.enabled and not m.is_separator]
    findings: list[Finding] = []

    for subject_pattern, target_pattern, relation in ORDER_RULES:
        if target_pattern == "*":
            continue  # informational only -- never evaluated in Phase 1

        subjects = [m for m in enabled_mods if _name_matches(subject_pattern, m.name)]
        targets = [m for m in enabled_mods if _name_matches(target_pattern, m.name)]

        for subject in subjects:
            for target in targets:
                if subject.name == target.name:
                    continue

                if relation == "should_load_after":
                    # "loads after" = wins conflicts = higher priority.
                    violated = subject.priority <= target.priority
                elif relation == "should_be_early":
                    # Inverse framing: subject should sit at lower priority
                    # (nearer the top of the pane) than target.
                    violated = subject.priority >= target.priority
                else:  # pragma: no cover -- unreachable given the closed enum
                    continue

                if violated:
                    findings.append(
                        Finding(
                            check_id="KNOWN_ORDER_RULE",
                            severity="warning",
                            title=f"{subject.name} {relation.replace('_', ' ')} {target.name}",
                            detail=f"Known-order rule: {subject_pattern!r} {relation} {target_pattern!r}.",
                            affected=[subject.name, target.name],
                            fix=(
                                f"Move {subject.name} to a higher priority than {target.name} in the left pane."
                                if relation == "should_load_after"
                                else f"Move {subject.name} to a lower priority than {target.name} in the left pane."
                            ),
                        )
                    )
    return findings
