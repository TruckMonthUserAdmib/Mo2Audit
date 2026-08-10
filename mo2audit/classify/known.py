"""Declarative classification data (Skyrim SE/AE). Committed, in-repo, no
network. Structured so a future multi-game phase can swap in a per-game set;
implement Skyrim only (spec 4.4).

Name patterns are lowercase substrings matched against mod names. The
generator/output pattern pair MUST stay a superset of checks/rules.py's
(classification's output-mod detection may never be narrower than Phase 1's
-- CLAUDE.md Phase 2 decision 1); tests/test_classifier.py asserts parity.
"""

from __future__ import annotations

# A mod name is generated output when it contains a generator keyword AND an
# output keyword ("FNIS - Output" yes; "FNIS Behavior SE" no -- that's the
# tool). Mirrors checks/rules.py, duplicated because classify/ may not
# import checks/.
GENERATOR_NAME_PATTERNS = ("fnis", "nemesis", "bodyslide", "dyndolod", "texgen")
OUTPUT_KEYWORD_PATTERNS = ("output", "overwrite")

# Frameworks are checked BEFORE tools so "SSE Engine Fixes" matches
# "engine fixes" here rather than the broader "sse fixes" tool pattern, and
# "DynDOLOD Resources" matches here rather than the "dyndolod" tool pattern.
KNOWN_FRAMEWORK_PATTERNS = (
    "address library",
    "papyrusutil",
    "jcontainers",
    "dyndolod resources",
    "engine fixes",
)

KNOWN_TOOL_PATTERNS = (
    "bodyslide",
    "outfit studio",
    "fnis behavior",  # deliberately NOT bare "fnis": FNIS Sexy Move / FNIS
    # Spells are content mods shipping plugins; a TOOL tag would wrongly
    # exempt them from plugin checks.
    "nemesis",
    "xlodgen",
    "dyndolod",
    "texgen",
    "sse fixes",
    "shadercache",
)

# CC auto-load fallback for when the Skyrim.ccc manifest is unreadable (game
# folder moved / not AE). The manifest is always primary when present --
# _resourcepack.esl is the proof the pattern alone is insufficient.
CC_PLUGIN_NAME_PREFIX = "cc"
CC_EXTRA_MANIFEST_PLUGINS = ("_resourcepack.esl",)

# File-level generated-output signatures, matched against any mod's files
# regardless of the mod's primary type (CLAUDE.md Phase 2 decision 1).
GENERATED_OUTPUT_BASENAMES = (
    "animationdatasinglefile.txt",
    "animationsetdatasinglefile.txt",
)
GENERATED_OUTPUT_BASENAME_GLOBS = (
    "fnis_*.pex",
    "dyndolod_*",
    "texgen_*",
)

# Preset/config detection.
PRESET_PATH_SEGMENTS = ("sliderpresets",)
CONFIG_ONLY_EXTENSIONS = (".xml", ".ini", ".json", ".txt", ".jslot", ".preset")

# Spec 7.7's recognized Data-relative top-level entries (duplicated from
# checks/limits.py's domain knowledge -- classify/ may not import checks/).
RECOGNIZED_DATA_DIRS = (
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
)

PLUGIN_EXTENSIONS = (".esp", ".esm", ".esl")
