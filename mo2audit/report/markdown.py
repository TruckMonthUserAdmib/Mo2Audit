"""Markdown report -- meant to be pasted into a forum post (e.g. r/skyrimmods)."""

from __future__ import annotations

from mo2audit.model import Finding

SEVERITY_ORDER = ("critical", "warning", "info")


def render_markdown(findings: list[Finding]) -> str:
    lines = ["# MO2 Load Order Audit Report", ""]

    if not findings:
        lines.append("No findings. Your load order looks clean.")
        return "\n".join(lines) + "\n"

    counts = {sev: sum(1 for f in findings if f.severity == sev) for sev in SEVERITY_ORDER}
    lines.append(f"**Summary:** {counts['critical']} critical, {counts['warning']} warning, {counts['info']} info")
    lines.append("")

    for severity in SEVERITY_ORDER:
        group = [f for f in findings if f.severity == severity]
        if not group:
            continue

        lines.append(f"## {severity.capitalize()} ({len(group)})")
        lines.append("")
        for finding in group:
            lines.append(f"### `{finding.check_id}`: {finding.title}")
            if finding.affected:
                lines.append(f"- **Affected:** {', '.join(finding.affected)}")
            if finding.detail:
                lines.append(f"- **Detail:** {finding.detail}")
            lines.append(f"- **Fix:** {finding.fix}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
