"""Fences user-written text inside prompt tags (P1-08, D-032).

A partial mitigation for prompt injection, not a defense: requirement and constraint text is wrapped
in tags the prompt describes as data, and tags inside the text are escaped so it cannot close them.
"""

from __future__ import annotations

import re

_TAG = re.compile(r"<(/?\s*(?:requirement|constraint)\b)", re.IGNORECASE)


def fence_user_text(value: str) -> str:
    """Escapes <requirement> and <constraint> tags inside user text so it cannot open or close them."""
    return _TAG.sub(r"&lt;\1", value)
