from __future__ import annotations

import re
from typing import Final

from lark import Lark, Tree, Visitor
from lark.exceptions import LarkError


ST_GRAMMAR: Final[str] = r"""
    start: compilation_unit

    compilation_unit: pou+

    pou: program_block
       | function_block

    program_block: PROGRAM identifier declaration_block* statement_list? END_PROGRAM

    function_block: FUNCTION_BLOCK identifier declaration_block* statement_list? END_FUNCTION_BLOCK


    declaration_block: var_header declaration* END_VAR

    var_header: VAR
              | VAR_INPUT
              | VAR_OUTPUT
              | VAR_IN_OUT
              | VAR_TEMP
              | VAR_GLOBAL

    declaration: identifier_list ":" type_spec initializer? ";"

    identifier_list: identifier ("," identifier)*

    type_spec: primitive_type
             | timer_type
             | identifier

    primitive_type: BOOL
                  | INT
                  | DINT
                  | REAL
                  | LREAL
                  | TIME
                  | STRING

    timer_type: TON
              | TOF
              | TP

    initializer: ASSIGN expr


    statement_list: statement*

    ?statement: assignment_stmt ";"+
              | if_stmt
              | case_stmt
              | for_stmt
              | while_stmt
              | function_call ";"+
              | ";"

    assignment_stmt: variable ASSIGN expr

    if_stmt: IF expr THEN statement_list elsif_clause* else_clause? END_IF ";"*

    elsif_clause: ELSIF expr THEN statement_list

    else_clause: ELSE statement_list

    case_stmt: CASE expr OF case_branch+ else_clause? END_CASE ";"*

    case_branch: case_label_list ":" statement_list

    case_label_list: case_label ("," case_label)*

    ?case_label: literal
               | identifier
               | range

    range: literal RANGE literal

    for_stmt: FOR identifier ASSIGN expr TO expr (BY expr)? DO statement_list END_FOR ";"*

    while_stmt: WHILE expr DO statement_list END_WHILE ";"*


    ?expr: or_expr

    ?or_expr: and_expr (OR and_expr)*

    ?and_expr: comparison_expr (AND comparison_expr)*

    ?comparison_expr: add_expr (COMPOP add_expr)*

    ?add_expr: mul_expr ((PLUS | MINUS) mul_expr)*

    ?mul_expr: unary_expr ((MUL | DIV) unary_expr)*

    ?unary_expr: NOT unary_expr
               | MINUS unary_expr
               | atom

    ?atom: literal
         | function_call
         | variable
         | "(" expr ")"

    function_call: identifier "(" argument_list? ")"

    argument_list: argument ("," argument)*

    ?argument: identifier ASSIGN expr -> named_argument
             | expr

    variable: identifier selector*

    selector: "." identifier
            | "[" expr "]"

    ?literal: BOOL_LITERAL
            | TIME_LITERAL
            | STRING_LITERAL
            | SIGNED_NUMBER

    identifier: IDENT


    PROGRAM: /(?i:PROGRAM)\b/
    END_PROGRAM: /(?i:END_PROGRAM)\b/
    FUNCTION_BLOCK: /(?i:FUNCTION_BLOCK)\b/
    END_FUNCTION_BLOCK: /(?i:END_FUNCTION_BLOCK)\b/

    VAR_INPUT: /(?i:VAR_INPUT)\b/
    VAR_OUTPUT: /(?i:VAR_OUTPUT)\b/
    VAR_IN_OUT: /(?i:VAR_IN_OUT)\b/
    VAR_TEMP: /(?i:VAR_TEMP)\b/
    VAR_GLOBAL: /(?i:VAR_GLOBAL)\b/
    VAR: /(?i:VAR)\b/
    END_VAR: /(?i:END_VAR)\b/

    IF: /(?i:IF)\b/
    THEN: /(?i:THEN)\b/
    ELSIF: /(?i:ELSIF)\b/
    ELSE: /(?i:ELSE)\b/
    END_IF: /(?i:END_IF)\b/

    CASE: /(?i:CASE)\b/
    OF: /(?i:OF)\b/
    END_CASE: /(?i:END_CASE)\b/

    FOR: /(?i:FOR)\b/
    TO: /(?i:TO)\b/
    BY: /(?i:BY)\b/
    DO: /(?i:DO)\b/
    END_FOR: /(?i:END_FOR)\b/

    WHILE: /(?i:WHILE)\b/
    END_WHILE: /(?i:END_WHILE)\b/

    BOOL: /(?i:BOOL)\b/
    INT: /(?i:INT)\b/
    DINT: /(?i:DINT)\b/
    REAL: /(?i:REAL)\b/
    LREAL: /(?i:LREAL)\b/
    TIME: /(?i:TIME)\b/
    STRING: /(?i:STRING)\b/
    TON: /(?i:TON)\b/
    TOF: /(?i:TOF)\b/
    TP: /(?i:TP)\b/

    AND: /(?i:AND)\b/
    OR: /(?i:OR)\b/
    NOT: /(?i:NOT)\b/

    BOOL_LITERAL: /(?i:TRUE|FALSE)\b/
    TIME_LITERAL: /(?i:(?:T|TIME)#[0-9]+(?:\.[0-9]+)?(?:MS|S|M|H|D)(?:[0-9]+(?:\.[0-9]+)?(?:MS|S|M|H|D))*)/
    STRING_LITERAL: /'([^']|'')*'|"(?:[^"\\]|\\.)*"/
    IDENT: /[A-Za-z_][A-Za-z0-9_]*/

    ASSIGN: ":="
    RANGE: ".."
    COMPOP: "<=" | ">=" | "<>" | "=" | "<" | ">"
    PLUS: "+"
    MINUS: "-"
    MUL: "*"
    DIV: "/"

    ML_COMMENT: /\(\*(.|\n|\r)*?\*\)/
    SL_COMMENT: /\/\/[^\n\r]*/

    %import common.SIGNED_NUMBER
    %import common.WS
    %ignore WS
    %ignore ML_COMMENT
    %ignore SL_COMMENT
"""


class DecisionCounter(Visitor):
    """Counts IEC 61131-3 Structured Text decision points from a Lark AST."""

    def __init__(self) -> None:
        self.count = 0

    def if_stmt(self, _: Tree) -> None:
        self.count += 1

    def elsif_clause(self, _: Tree) -> None:
        self.count += 1

    def case_branch(self, _: Tree) -> None:
        self.count += 1

    def for_stmt(self, _: Tree) -> None:
        self.count += 1

    def while_stmt(self, _: Tree) -> None:
        self.count += 1


class STAstParser:
    """Parser and analysis helper for IEC 61131-3 Structured Text programs."""

    _block_comment_pattern = re.compile(r"\(\*.*?\*\)", re.DOTALL)
    _line_comment_pattern = re.compile(r"//.*?$", re.MULTILINE)
    _fallback_decision_pattern = re.compile(r"\b(IF|ELSIF|FOR|WHILE)\b", re.IGNORECASE)
    _case_block_pattern = re.compile(r"\bCASE\b(?P<body>.*?)\bEND_CASE\b", re.IGNORECASE | re.DOTALL)
    _case_branch_pattern = re.compile(
        r"""(?imx)
        ^\s*
        (?!ELSE\b)
        (?:
            [A-Za-z_][A-Za-z0-9_]*
            | TRUE
            | FALSE
            | [-+]?\d+(?:\.\d+)?
            | '(?:[^']|'')*'
            | "(?:[^"\\]|\\.)*"
        )
        (?:
            \s*(?:,|\.\.)\s*
            (?:
                [A-Za-z_][A-Za-z0-9_]*
                | TRUE
                | FALSE
                | [-+]?\d+(?:\.\d+)?
                | '(?:[^']|'')*'
                | "(?:[^"\\]|\\.)*"
            )
        )*
        \s*:
        """,
    )

    def __init__(self) -> None:
        self._parser = Lark(
            ST_GRAMMAR,
            parser="earley",
            ambiguity="resolve",
            maybe_placeholders=False,
        )

    def parse(self, st_code: str) -> Tree:
        if not isinstance(st_code, str) or not st_code.strip():
            raise ValueError("Structured Text source must be a non-empty string.")
        return self._parser.parse(st_code)

    def count_decision_points(self, st_code: str) -> int:
        count, _fallback_used = self.count_decision_points_with_metadata(st_code)
        return count

    def count_decision_points_with_metadata(self, st_code: str) -> tuple[int, bool]:
        try:
            tree = self.parse(st_code)
            counter = DecisionCounter()
            counter.visit(tree)
            return counter.count, False
        except (LarkError, ValueError, TypeError):
            return self._fallback_count_decision_points(st_code), True

    @classmethod
    def _fallback_count_decision_points(cls, st_code: str) -> int:
        if not isinstance(st_code, str) or not st_code.strip():
            return 0

        source = cls._strip_comments(st_code)
        direct_decisions = len(cls._fallback_decision_pattern.findall(source))
        case_branches = cls._count_case_branches(source)
        return direct_decisions + case_branches

    @classmethod
    def _strip_comments(cls, st_code: str) -> str:
        without_blocks = cls._block_comment_pattern.sub("", st_code)
        return cls._line_comment_pattern.sub("", without_blocks)

    @classmethod
    def _count_case_branches(cls, st_code: str) -> int:
        total = 0
        for case_match in cls._case_block_pattern.finditer(st_code):
            body = case_match.group("body")
            total += len(cls._case_branch_pattern.findall(body))
        return total
