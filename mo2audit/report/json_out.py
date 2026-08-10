"""JSON report -- the stable interface Phase 2/3 consume. Must be complete,
not just a subset of what the text report shows.
"""

from __future__ import annotations

import dataclasses
import json

from mo2audit.model import Finding

SCHEMA_VERSION = 1


def render_json(findings: list[Finding], *, mo2_base: str | None = None, profile: str | None = None) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "mo2_base": mo2_base,
        "profile": profile,
        "findings": [dataclasses.asdict(f) for f in findings],
    }
    return json.dumps(payload, indent=2)
