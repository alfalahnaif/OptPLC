"""Semantic checks over the Lark parse tree for the static domain rules.

Text-pattern rules misjudge code in both directions (C-14): MC-2 accepted a motor template that can
never run and rejected a correct one. These helpers read program structure instead. They are the
first step of the rule catalog rework (P1-05), introduced for MC-2 in P1-22 (D-031).
"""

from __future__ import annotations

from lark import Token, Tree
from lark.exceptions import LarkError

from app.services.st_syntax_check import parse_tree

# Identifier fragments that mark a stop, safety, or fault condition.
GUARD_WORDS = ("STOP", "EMERGENCY", "FAULT", "SAFETY", "OVERLOAD", "TRIP")


def _identifiers(node: object) -> set[str]:
    if not isinstance(node, Tree):
        return set()
    return {str(sub.children[0]).upper() for sub in node.iter_subtrees() if sub.data == "identifier"}


def _mentions(node: object, words: tuple[str, ...]) -> bool:
    return any(word in name for name in _identifiers(node) for word in words)


def _assigned(statements: Tree, literal: str) -> set[str]:
    """Names assigned the BOOL literal `literal` anywhere inside the statements."""
    names: set[str] = set()
    for node in statements.iter_subtrees():
        if node.data == "assignment_stmt":
            value = node.children[2]
            if isinstance(value, Token) and value.type == "BOOL_LITERAL" and str(value).upper() == literal:
                names.add(str(node.children[0].children[0].children[0]).upper())
    return names


def start_paths_guarded(source: str) -> bool | None:
    """Checks every IF branch that starts something: a condition naming START that assigns TRUE.

    A start branch is guarded when its own condition names a stop, safety, or fault signal, or when an
    earlier branch of the same IF has such a condition and assigns FALSE to the same variables (the
    stop-dominant form: IF NOT Stop_PB OR Fault THEN Run := FALSE; ELSIF Start THEN Run := TRUE).

    Returns True when every start branch is guarded, False when one is not, and None when the source
    does not parse or has no start branch, so the caller keeps its own verdict.
    """
    try:
        tree = parse_tree(source)
    except (LarkError, ValueError):
        return None

    found = False
    for node in tree.iter_subtrees():
        if node.data != "if_stmt":
            continue
        branches: list[tuple[object | None, Tree]] = [(node.children[1], node.children[3])]
        for clause in node.children[4:]:
            if isinstance(clause, Tree) and clause.data == "elsif_clause":
                branches.append((clause.children[1], clause.children[3]))
            elif isinstance(clause, Tree) and clause.data == "else_clause":
                branches.append((None, clause.children[1]))

        cleared_by_guard: set[str] = set()
        for condition, statements in branches:
            started = _assigned(statements, "TRUE") if _mentions(condition, ("START",)) else set()
            if started:
                found = True
                if not _mentions(condition, GUARD_WORDS) and not started <= cleared_by_guard:
                    return False
            if _mentions(condition, GUARD_WORDS):
                cleared_by_guard |= _assigned(statements, "FALSE")
    return True if found else None
