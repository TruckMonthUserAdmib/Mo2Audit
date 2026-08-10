"""--explain output: every mod's classification, confidence, and reasons
(Phase 2 spec section 7). The user-trust/debugging view -- lets the user see
exactly WHY a mod was or wasn't exempted by a type-aware check.

Consuming classify/types here is forward flow in the one-way chain
parsing -> classify -> checks -> report; nothing flows backward.
"""

from __future__ import annotations

from mo2audit.classify.types import SetupClassification
from mo2audit.model import ModEntry


def render_explain(mods: list[ModEntry], classification: SetupClassification) -> str:
    """One line per mod, left-pane order (highest priority first = bottom of
    MO2's pane = wins conflicts), plus a CC-mechanism footer."""
    lines = ["=== CLASSIFICATION (--explain) ===", ""]
    for mod in sorted(mods, key=lambda m: -m.priority):
        cls = classification.mods.get(mod.name)
        if cls is None:
            continue
        state = "enabled" if mod.enabled else "DISABLED"
        line = f"[{cls.mod_type.value}] {mod.name} ({state}, confidence {cls.confidence:.2f})"
        lines.append(line)
        for reason in cls.reasons:
            lines.append(f"    reason: {reason}")
        generated = classification.generated_output_files.get(mod.name)
        if generated:
            lines.append(f"    generated-output files: {len(generated)}")
    lines.append("")
    lines.append(
        f"CC-mechanism plugins present and loadable: {len(classification.cc_provided_plugins)}"
    )
    lines.append("")
    return "\n".join(lines)
