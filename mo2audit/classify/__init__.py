"""Mod-classification layer (Phase 2).

Sits between parsing/ and checks/ in the one-way dependency chain
parsing -> classify -> checks -> report. May import from model.py only;
never from checks/, never from parsing/ modules, never the filesystem.
"""

from mo2audit.classify.types import ModClassification, ModType, SetupClassification

__all__ = ["ModClassification", "ModType", "SetupClassification"]
