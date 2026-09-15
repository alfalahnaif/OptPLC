"""Parser check for Structured Text, used when MATIEC is unavailable (plan item P1-01, D-029).

Passing this check is NOT evidence level L1: L1 means the unmodified source compiles in MATIEC.
The check parses the IEC 61131-3 subset described by ST_GRAMMAR in st_parser.py, then reports
undeclared variables and calls to names that are neither declared nor IEC standard functions.
Messages are worded so DebuggingAgent._syntax_report maps them to its error types.
"""

from __future__ import annotations

import re
import threading
from typing import Final

from lark import Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedInput

from app.services.st_parser import STAstParser

PARSER_CHECK_LABEL: Final[str] = "parser.v1"

# IEC 61131-3 standard functions that may be called without a declaration.
# Type conversions (INT_TO_REAL, ...) are matched by _CONVERSION_FUNCTION.
IEC_STANDARD_FUNCTIONS: Final[frozenset[str]] = frozenset(
    {
        "ABS", "SQRT", "LN", "LOG", "EXP", "SIN", "COS", "TAN", "ASIN", "ACOS", "ATAN",
        "ADD", "SUB", "MUL", "DIV", "EXPT", "MOVE", "TRUNC",
        "SHL", "SHR", "ROL", "ROR",
        "SEL", "MAX", "MIN", "LIMIT", "MUX",
        "GT", "GE", "EQ", "LE", "LT", "NE",
        "LEN", "LEFT", "RIGHT", "MID", "CONCAT", "INSERT", "DELETE", "REPLACE", "FIND",
    }
)
_CONVERSION_FUNCTION = re.compile(r"^[A-Z]+_TO_[A-Z]+$")

_COMMENT_OR_STRING = re.compile(r"\(\*.*?\*\)|//[^\n\r]*|'(?:[^']|'')*'|\"(?:[^\"\\]|\\.)*\"", re.DOTALL)
_VAR_HEADER = re.compile(r"\b(?:VAR|VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR_GLOBAL|VAR_EXTERNAL)\b", re.IGNORECASE)
_END_VAR = re.compile(r"\bEND_VAR\b", re.IGNORECASE)
# The labels match the phrases DebuggingAgent looks for ("if statements", "for loops", ...).
_BLOCK_PAIRS: Final[tuple[tuple[str, str, str], ...]] = (
    ("IF", "END_IF", "IF statements"),
    ("CASE", "END_CASE", "CASE statements"),
    ("FOR", "END_FOR", "FOR loops"),
    ("WHILE", "END_WHILE", "WHILE loops"),
    ("REPEAT", "END_REPEAT", "REPEAT loops"),
)

_shared_parser: STAstParser | None = None
# Validation runs in worker threads (asyncio.to_thread, D-030), so the shared parser is guarded.
_parser_lock = threading.Lock()


def _default_parser() -> STAstParser:
    """Builds the Earley parser once per process; compiling the grammar is the slow part."""
    global _shared_parser
    with _parser_lock:
        if _shared_parser is None:
            _shared_parser = STAstParser()
    return _shared_parser


def parse_tree(source: str) -> Tree:
    """Parses source with the shared parser. Raises lark's UnexpectedInput or ValueError on failure."""
    parser = _default_parser()
    with _parser_lock:
        return parser.parse(source)


def strip_comments_and_strings(source: str) -> str:
    """Blanks out comments and string literals, keeping line breaks so line numbers stay valid."""
    return _COMMENT_OR_STRING.sub(lambda match: re.sub(r"[^\r\n]", " ", match.group()), source)


def _count_keyword(keyword: str, text: str) -> int:
    return len(re.findall(rf"\b{keyword}\b", text, re.IGNORECASE))


def _first_identifier(node: Tree) -> Token | None:
    for child in node.children:
        if isinstance(child, Tree) and child.data == "identifier":
            return child.children[0]
    return None


class ParserCheck:
    """Structural checks, then a Lark parse, then a declaration check."""

    def __init__(self, parser: STAstParser | None = None) -> None:
        self._parser = parser

    def check(self, source: str) -> list[str]:
        if not isinstance(source, str) or not source.strip():
            return ["CodeArtifact source is empty."]

        structural = self._structural_errors(strip_comments_and_strings(source))
        if structural:
            return structural

        parser = self._parser or _default_parser()
        try:
            with _parser_lock:
                tree = parser.parse(source)
        except UnexpectedInput as exc:
            return [self._parse_error_message(exc)]
        return self._declaration_errors(tree)

    @staticmethod
    def _structural_errors(text: str) -> list[str]:
        errors: list[str] = []
        has_program = _count_keyword("PROGRAM", text) > 0
        has_function_block = _count_keyword("FUNCTION_BLOCK", text) > 0
        if not has_program and not has_function_block:
            errors.append("Missing PROGRAM or FUNCTION_BLOCK declaration")
        if has_program and _count_keyword("END_PROGRAM", text) == 0:
            errors.append("Missing END_PROGRAM")
        if has_function_block and _count_keyword("END_FUNCTION_BLOCK", text) == 0:
            errors.append("Missing END_FUNCTION_BLOCK")

        headers = len(_VAR_HEADER.findall(text))
        end_vars = len(_END_VAR.findall(text))
        if headers != end_vars:
            errors.append(
                f"Unbalanced variable blocks: {headers} VAR/VAR_INPUT/VAR_OUTPUT header(s) vs {end_vars} END_VAR"
            )

        for opener, closer, label in _BLOCK_PAIRS:
            opened, closed = _count_keyword(opener, text), _count_keyword(closer, text)
            if opened != closed:
                errors.append(f"Unbalanced {label}: {opened} {opener} vs {closed} {closer}")

        # MATIEC rejects SFC keywords as variable names, e.g. Step (P1-03, D-006).
        sfc_keywords = {"STEP", "INITIAL_STEP", "END_STEP", "TRANSITION", "END_TRANSITION", "ACTION", "END_ACTION"}
        for line_number, line in enumerate(text.splitlines(), start=1):
            declaration = re.match(r"\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*:(?!=)", line)
            if declaration is None:
                continue
            for name in re.split(r"\s*,\s*", declaration.group(1)):
                if name.upper() in sfc_keywords:
                    errors.append(
                        f"Variable name '{name}' is a reserved IEC 61131-3 keyword (SFC); MATIEC rejects it "
                        f"(line {line_number})."
                    )
        return errors

    @staticmethod
    def _parse_error_message(exc: UnexpectedInput) -> str:
        if isinstance(exc, UnexpectedEOF):
            return f"Parser check ({PARSER_CHECK_LABEL}) failed: unexpected end of input."
        if isinstance(exc, UnexpectedCharacters):
            found = exc.char
        else:
            found = str(getattr(exc, "token", "?"))
        return (
            f"Parser check ({PARSER_CHECK_LABEL}) failed at line {exc.line}, column {exc.column}: "
            f"unexpected {found!r}."
        )

    @staticmethod
    def _declaration_errors(tree: Tree) -> list[str]:
        declared: set[str] = set()
        for node in tree.iter_subtrees():
            if node.data == "declaration":
                for identifier in node.children[0].children:
                    declared.add(str(identifier.children[0]).upper())

        # Collect every occurrence first: iter_subtrees() does not follow source order,
        # and each name must be reported once, at its first position in the source.
        occurrences: list[tuple[int, int, str, str]] = []
        for node in tree.iter_subtrees():
            if node.data in ("variable", "for_stmt"):
                token = _first_identifier(node)
                if token is not None and str(token).upper() not in declared:
                    occurrences.append(
                        (
                            token.line,
                            token.column,
                            str(token).upper(),
                            f"Variable '{token}' is not declared in any VAR block (line {token.line}).",
                        )
                    )
            elif node.data == "case_label_list":
                # MATIEC rejects named constants as CASE labels (D-006); only literals are accepted.
                for child in node.children:
                    if isinstance(child, Tree) and child.data == "identifier":
                        token = child.children[0]
                        if str(token).upper() in declared:
                            occurrences.append(
                                (
                                    token.line,
                                    token.column,
                                    f"CASE-LABEL:{str(token).upper()}",
                                    f"CASE label '{token}' is a named constant; MATIEC accepts only literal labels "
                                    f"(line {token.line}).",
                                )
                            )
            elif node.data == "function_call":
                token = _first_identifier(node)
                if token is None:
                    continue
                name = str(token).upper()
                if name not in declared and name not in IEC_STANDARD_FUNCTIONS and not _CONVERSION_FUNCTION.match(name):
                    occurrences.append(
                        (
                            token.line,
                            token.column,
                            name,
                            f"Called name '{token}' is not declared and is not an IEC 61131-3 standard function "
                            f"(line {token.line}).",
                        )
                    )

        errors: list[str] = []
        reported: set[str] = set()
        for _line, _column, key, message in sorted(occurrences):
            if key not in reported:
                reported.add(key)
                errors.append(message)
        return errors
