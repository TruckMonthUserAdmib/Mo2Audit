"""Plain text report: a severity summary, a per-check-ID count summary,
then findings grouped by severity (critical first) and sub-grouped by
check ID. Repeated findings of the same check ID are capped at 10 shown
by default; --full (report layer's `full=True`) disables the cap.
"""

from __future__ import annotations

from collections import defaultdict

from mo2audit.model import Finding

SEVERITY_ORDER = ("critical", "warning", "info")
DEFAULT_CAP = 10

_COLOR_CODES = {"critical": "\033[91m", "warning": "\033[93m", "info": "\033[94m"}
_RESET = "\033[0m"


def _colorize(text: str, severity: str, color: bool) -> str:
    return f"{_COLOR_CODES[severity]}{text}{_RESET}" if color else text


def _group_by_check_id(findings: list[Finding]) -> list[tuple[str, list[Finding]]]:
    by_check: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_check[finding.check_id].append(finding)
    # Worst offenders first; alphabetical tiebreak for determinism.
    return sorted(by_check.items(), key=lambda kv: (-len(kv[1]), kv[0]))


def _render_summary(findings: list[Finding], color: bool) -> list[str]:
    lines = ["=== SUMMARY ===", ""]
    counts_by_severity = {sev: sum(1 for f in findings if f.severity == sev) for sev in SEVERITY_ORDER}
    for sev in SEVERITY_ORDER:
        label = _colorize(sev.capitalize(), sev, color)
        lines.append(f"{label}: {counts_by_severity[sev]}")
    lines.append(f"Total: {len(findings)}")
    lines.append("")

    lines.append("By check:")
    for sev in SEVERITY_ORDER:
        group = [f for f in findings if f.severity == sev]
        if not group:
            continue
        for check_id, check_findings in _group_by_check_id(group):
            lines.append(f"  {check_id}: {len(check_findings)}")
    lines.append("")
    return lines


def _render_finding(finding: Finding, verbose_conflicts: bool) -> list[str]:
    lines = [f"[{finding.check_id}] {finding.title}"]
    if finding.affected:
        # Annotate affected mods with their classified type when the check
        # consulted classification (spec section 7).
        annotated = [
            f"{name} ({finding.mod_types[name]})" if name in finding.mod_types else name
            for name in finding.affected
        ]
        lines.append(f"  Affected: {', '.join(annotated)}")
    show_detail = finding.detail and (finding.check_id != "LOOSE_FILE_CONFLICT" or verbose_conflicts)
    if show_detail:
        lines.append(f"  Detail: {finding.detail}")
    lines.append(f"  Fix: {finding.fix}")
    lines.append("")
    return lines


def render_text(
    findings: list[Finding],
    *,
    verbose_conflicts: bool = False,
    color: bool = False,
    full: bool = False,
) -> str:
    if not findings:
        return "No findings. Your load order looks clean.\n"

    lines: list[str] = _render_summary(findings, color)

    for severity in SEVERITY_ORDER:
        group = [f for f in findings if f.severity == severity]
        if not group:
            continue

        header = _colorize(severity.upper(), severity, color)
        lines.append(f"=== {header} ({len(group)}) ===")
        lines.append("")

        for check_id, check_findings in _group_by_check_id(group):
            lines.append(f"--- {check_id} ({len(check_findings)}) ---")
            lines.append("")

            shown = check_findings if full else check_findings[:DEFAULT_CAP]
            for finding in shown:
                lines.extend(_render_finding(finding, verbose_conflicts))

            remaining = len(check_findings) - len(shown)
            if remaining > 0:
                lines.append(f"... and {remaining} more (use --full to show all)")
                lines.append("")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
