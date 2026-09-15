"""Canonical PlanObject domain names shared by planning and code generation (P1-22, C-13).

The planning agent and the code generator used to compare raw domain strings separately, so the
domain "Safety Interlock" (singular) got an interlock plan but the generic code template, whose
signals are not in that plan (C-13). Both now route through canonical_domain().
"""

from __future__ import annotations

_ALIASES = {
    "safety interlock": "safety interlocks",
    "interlock": "safety interlocks",
    "interlocks": "safety interlocks",
    "tank": "process control",
    "tank control": "process control",
    "sequential batches": "sequential batch",
    "batch": "sequential batch",
    "traffic": "traffic control",
    "motor": "motor control",
}


def canonical_domain(domain: str | None) -> str:
    """Lower-cases, collapses whitespace, and maps known aliases to one canonical name."""
    normalized = " ".join(str(domain or "").strip().lower().split())
    return _ALIASES.get(normalized, normalized)
