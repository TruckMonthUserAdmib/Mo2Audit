"""Classification types for the Phase 2 mod-classification layer.

Plain data only. checks/ may import THIS module (plus model.py) and nothing
else from classify/ -- never classifier.py, heuristics.py, or known.py. See
CLAUDE.md "The architectural invariant (extended for Phase 2)"; enforced by
tests/test_architecture.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ModType(Enum):
    """Primary role of a left-pane mod. Closed set -- do not add members
    without updating the Phase 2 spec and CLAUDE.md."""

    CONTENT = "content"                      # normal mod; the default
    TOOL = "tool"                            # app MO2 runs, not loaded as content
    GENERATED_OUTPUT = "generated_output"    # produced by a TOOL (FNIS/BodySlide/...)
    PRESET_CONFIG = "preset_config"          # data-free by design (presets, configs)
    RESOURCE_FRAMEWORK = "resource_framework"  # library other mods depend on
    SEPARATOR = "separator"                  # MO2 organizational divider
    CC_CONTENT = "cc_content"                # Creation Club, non-standard load path
    UNKNOWN = "unknown"                      # unclassifiable; treated as CONTENT


@dataclass
class ModClassification:
    mod_name: str
    mod_type: ModType
    confidence: float          # 0.0-1.0; heuristic certainty
    reasons: list[str]         # human-readable why, for the report/--explain
    is_data_free_by_design: bool


@dataclass
class SetupClassification:
    """Plain-data classification results for a whole Setup.

    mods: one primary classification per mod name.
    cc_provided_plugins: lowercased plugin FILENAMES provided via the CC
        mechanism -- plugin-level granularity, because MISSING_MASTER resolves
        plugin names and one bundle mod can provide dozens of cc* plugins.
    generated_output_files: mod name -> normalized rel paths in that mod
        matching generated-output signatures. File-level, deliberately
        independent of the mod's primary type: the FNIS mod is TOOL yet
        contains animationsetdatasinglefile.txt, and OVERWRITE_GENERATED_OUTPUT
        must protect generated files wherever they sit.
    """

    mods: dict[str, ModClassification] = field(default_factory=dict)
    cc_provided_plugins: set[str] = field(default_factory=set)
    generated_output_files: dict[str, set[str]] = field(default_factory=dict)

    def effective_type(self, mod_name: str) -> ModType:
        """Type a check should treat a mod as. UNKNOWN and unclassified mods
        are CONTENT: a misclassification may only ever add a false positive,
        never suppress a real finding. This bias lives here and only here."""
        classification = self.mods.get(mod_name)
        if classification is None or classification.mod_type is ModType.UNKNOWN:
            return ModType.CONTENT
        return classification.mod_type
