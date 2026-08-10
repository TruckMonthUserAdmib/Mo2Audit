"""Check registry. checks/*.py may import from model.py and classify/types.py
only -- never from parsing/, never any other classify module, never touch a
file path or MO2 API. Every check is a pure function
(Setup, SetupClassification) -> list[Finding]; classification arrives as an
explicit plain-data argument (never by mutating Setup) and defaults to empty
so hand-built test Setups keep working. Adding a check requires no changes
to the CLI.
"""

from __future__ import annotations

from typing import Callable

from mo2audit.classify.types import SetupClassification
from mo2audit.model import Finding, Setup

CheckFn = Callable[[Setup, SetupClassification], list[Finding]]
_REGISTRY: dict[str, CheckFn] = {}


def register(check_id: str) -> Callable[[CheckFn], CheckFn]:
    def decorator(fn: CheckFn) -> CheckFn:
        if check_id in _REGISTRY:
            raise ValueError(f"check {check_id!r} is already registered")
        _REGISTRY[check_id] = fn
        return fn

    return decorator


def list_checks() -> list[str]:
    return sorted(_REGISTRY)


def run_all(
    setup: Setup,
    classification: SetupClassification | None = None,
    only: set[str] | None = None,
    skip: set[str] | None = None,
) -> list[Finding]:
    """`only` restricts to the named checks; `skip` then removes checks from
    whatever `only` selected (or from all). The two compose -- no error."""
    if classification is None:
        classification = SetupClassification()
    findings: list[Finding] = []
    for check_id, fn in _REGISTRY.items():
        if only is not None and check_id not in only:
            continue
        if skip is not None and check_id in skip:
            continue
        findings.extend(fn(setup, classification))
    return findings


# Import submodules so their @register(...) decorators populate _REGISTRY.
# Must come after `register` is defined above.
from mo2audit.checks import overwrite as _overwrite  # noqa: E402,F401
from mo2audit.checks import plugins as _plugins  # noqa: E402,F401
from mo2audit.checks import integrity as _integrity  # noqa: E402,F401
from mo2audit.checks import limits as _limits  # noqa: E402,F401
from mo2audit.checks import rules as _rules  # noqa: E402,F401
from mo2audit.checks import hygiene as _hygiene  # noqa: E402,F401
