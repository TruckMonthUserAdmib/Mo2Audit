"""Cross-reference same-root-cause findings (Phase 2 spec 6.2).

Report-layer concern: checks detect independently and declare their
root-cause pairs via Finding.pair_keys; this module merges findings from
DIFFERENT checks that share a pair, keeping the higher-severity finding and
folding the lower one in as layered detail. A finding whose pairs match
nothing survives untouched -- distinct findings are never suppressed.

Imports model.py only, like the rest of report/.
"""

from __future__ import annotations

from mo2audit.model import Finding

_SEVERITY_RANK = {"critical": 2, "warning": 1, "info": 0}


def cross_reference(findings: list[Finding]) -> list[Finding]:
    """Merge duplicate root causes; order is preserved for survivors."""
    # For each pair key: the highest-severity finding claiming it.
    strongest_by_pair: dict[tuple[str, str], Finding] = {}
    for finding in findings:
        for pair in finding.pair_keys:
            current = strongest_by_pair.get(pair)
            if current is None or _SEVERITY_RANK[finding.severity] > _SEVERITY_RANK[current.severity]:
                strongest_by_pair[pair] = finding

    merged_notes: dict[int, list[str]] = {}  # id(survivor) -> folded summaries
    result: list[Finding] = []
    for finding in findings:
        survivors = {
            id(strongest_by_pair[pair])
            for pair in finding.pair_keys
            if strongest_by_pair[pair] is not finding
            and strongest_by_pair[pair].check_id != finding.check_id
        }
        # Fold only when EVERY pair this finding reports is claimed by a
        # single stronger finding from another check -- partial overlap means
        # this finding still carries information of its own, so it survives.
        if finding.pair_keys and len(survivors) == 1 and all(
            strongest_by_pair[pair] is not finding for pair in finding.pair_keys
        ):
            survivor_id = next(iter(survivors))
            merged_notes.setdefault(survivor_id, []).append(
                f"also reported by {finding.check_id}: {finding.title}"
            )
            continue
        result.append(finding)

    if not merged_notes:
        return result

    out: list[Finding] = []
    for finding in result:
        notes = merged_notes.get(id(finding))
        if notes:
            merged_detail = f"{finding.detail} [merged -- {'; '.join(notes)}]"
            finding = Finding(
                check_id=finding.check_id,
                severity=finding.severity,
                title=finding.title,
                detail=merged_detail,
                affected=finding.affected,
                fix=finding.fix,
                pair_keys=finding.pair_keys,
            )
        out.append(finding)
    return out
