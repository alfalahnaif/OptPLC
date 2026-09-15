"""A minimal scan-cycle interpreter for behavior tests of the generated templates (P1-22, D-031).

It runs one PROGRAM scan by scan: inputs are applied, the statement list executes top to bottom,
and outputs are read back. It covers the subset the templates use: BOOL/INT/REAL variables with
initializers, assignments, IF/ELSIF/ELSE, CASE with integer labels, the usual operators, and the
function blocks R_TRIG, F_TRIG, TON, TOF, and CTU with a fixed scan time.

This is a test oracle for that subset, NOT evidence level L3: it is not a PLC runtime and has no
arrays, strings, or timing jitter. The real simulator is planned for Phase 2.
"""

from __future__ import annotations

from lark import Token, Tree

from app.services.st_syntax_check import parse_tree

FUNCTION_BLOCKS = {"R_TRIG", "F_TRIG", "TON", "TOF", "CTU"}


class ScanSim:
    def __init__(self, source: str, dt_ms: int = 100) -> None:
        self.dt_ms = dt_ms
        self.vars: dict[str, object] = {}
        self.names: dict[str, str] = {}
        self.fbs: dict[str, dict] = {}
        self.inputs: list[str] = []
        self.outputs: list[str] = []
        pou = next(parse_tree(source).find_data("program_block"))
        for block in pou.find_data("declaration_block"):
            kind = block.children[0].children[0].type
            for declaration in block.children:
                if isinstance(declaration, Tree) and declaration.data == "declaration":
                    self._declare(kind, declaration)
        self.body = [child for child in pou.children if isinstance(child, Tree) and child.data == "statement_list"]

    def _declare(self, kind: str, declaration: Tree) -> None:
        names = [str(identifier.children[0]) for identifier in declaration.children[0].children]
        type_name = self._type_name(declaration.children[1])
        initializer = next(
            (child.children[1] for child in declaration.children[2:] if isinstance(child, Tree) and child.data == "initializer"),
            None,
        )
        for name in names:
            key = name.upper()
            self.names[key] = name
            if type_name in FUNCTION_BLOCKS:
                self.fbs[key] = {"type": type_name, "Q": False, "ET": 0, "CV": 0, "prev": False}
            else:
                self.vars[key] = self.eval(initializer) if initializer is not None else self._default(type_name)
            if kind == "VAR_INPUT":
                self.inputs.append(key)
            elif kind == "VAR_OUTPUT":
                self.outputs.append(key)

    @staticmethod
    def _type_name(type_spec: Tree) -> str:
        node: object = type_spec
        while isinstance(node, Tree):
            node = node.children[0]
        return str(node).upper()

    @staticmethod
    def _default(type_name: str) -> object:
        if type_name == "BOOL":
            return False
        return 0.0 if type_name in {"REAL", "LREAL"} else 0

    def scan(self, **inputs: object) -> dict[str, object]:
        """Applies the given inputs (they persist until changed), runs one scan, and returns the outputs."""
        for name, value in inputs.items():
            key = name.upper()
            if key not in self.inputs:
                raise KeyError(f"{name} is not a VAR_INPUT of this program")
            self.vars[key] = value
        for statements in self.body:
            self._run(statements)
        return {self.names[key]: self.vars[key] for key in self.outputs}

    def peek(self, name: str) -> object:
        """Reads any variable, including internal state."""
        return self.vars[name.upper()]

    def _run(self, statements: Tree) -> None:
        for statement in statements.children:
            if isinstance(statement, Tree):
                self._exec(statement)

    def _exec(self, statement: Tree) -> None:
        kind = statement.data
        if kind == "assignment_stmt":
            target, _assign, expression = statement.children
            key = str(target.children[0].children[0]).upper()
            if key not in self.vars:
                raise KeyError(f"assignment to undeclared variable {key}")
            self.vars[key] = self.eval(expression)
        elif kind == "if_stmt":
            if self.eval(statement.children[1]):
                self._run(statement.children[3])
                return
            for clause in statement.children[4:]:
                if isinstance(clause, Tree) and clause.data == "elsif_clause":
                    if self.eval(clause.children[1]):
                        self._run(clause.children[3])
                        return
                elif isinstance(clause, Tree) and clause.data == "else_clause":
                    self._run(clause.children[1])
                    return
        elif kind == "case_stmt":
            selector = self.eval(statement.children[1])
            for branch in statement.children[3:]:
                if isinstance(branch, Tree) and branch.data == "case_branch":
                    if selector in [int(str(label)) for label in branch.children[0].children]:
                        self._run(branch.children[1])
                        return
                elif isinstance(branch, Tree) and branch.data == "else_clause":
                    self._run(branch.children[1])
                    return
        elif kind == "function_call":
            self._call(statement)
        elif kind == "statement":
            # Lark keeps this wrapper for the empty statement after END_IF; run whatever it holds.
            for child in statement.children:
                if isinstance(child, Tree):
                    self._exec(child)
        else:
            raise NotImplementedError(f"statement {kind} is outside the supported subset")

    def _call(self, call: Tree) -> None:
        fb = self.fbs[str(call.children[0].children[0]).upper()]
        args: dict[str, object] = {}
        if len(call.children) > 1:
            for argument in call.children[1].children:
                args[str(argument.children[0].children[0]).upper()] = self.eval(argument.children[2])
        kind = fb["type"]
        if kind in {"R_TRIG", "F_TRIG"}:
            clk = bool(args.get("CLK", False))
            fb["Q"] = (clk and not fb["prev"]) if kind == "R_TRIG" else (not clk and fb["prev"])
            fb["prev"] = clk
        elif kind == "TON":
            running = bool(args.get("IN", False))
            fb["ET"] = min(fb["ET"] + self.dt_ms, args["PT"]) if running else 0
            fb["Q"] = running and fb["ET"] >= args["PT"]
        elif kind == "TOF":
            if args.get("IN", False):
                fb["Q"], fb["ET"] = True, 0
            elif fb["Q"]:
                fb["ET"] = min(fb["ET"] + self.dt_ms, args["PT"])
                fb["Q"] = fb["ET"] < args["PT"]
        elif kind == "CTU":
            pulse = bool(args.get("CU", False))
            if args.get("R", False):
                fb["CV"] = 0
            elif pulse and not fb["prev"]:
                fb["CV"] += 1
            fb["prev"] = pulse
            fb["Q"] = fb["CV"] >= args.get("PV", 0)

    def eval(self, node: object) -> object:
        if isinstance(node, Token):
            text = str(node)
            if node.type == "BOOL_LITERAL":
                return text.upper() == "TRUE"
            if node.type == "SIGNED_NUMBER":
                return float(text) if any(c in text for c in ".eE") else int(text)
            if node.type == "TIME_LITERAL":
                value = text.split("#", 1)[1].lower()
                return int(float(value[:-2])) if value.endswith("ms") else int(float(value[:-1]) * 1000)
            raise NotImplementedError(f"literal {node.type} is outside the supported subset")
        kind = node.data
        if kind == "variable":
            key = str(node.children[0].children[0]).upper()
            if len(node.children) > 1:
                return self.fbs[key][str(node.children[1].children[0].children[0]).upper()]
            if key not in self.vars:
                raise KeyError(f"read of undeclared variable {key}")
            return self.vars[key]
        if kind == "unary_expr":
            operator, value = str(node.children[0]).upper(), self.eval(node.children[1])
            return (not value) if operator == "NOT" else -value
        if kind in {"or_expr", "xor_expr", "and_expr", "comparison_expr", "add_expr", "mul_expr", "power_expr"}:
            children = node.children
            value = self.eval(children[0])
            for index in range(1, len(children), 2):
                value = _apply(str(children[index]).upper(), value, self.eval(children[index + 1]))
            return value
        raise NotImplementedError(f"expression {kind} is outside the supported subset")


def _apply(operator: str, a, b):
    if operator == "OR":
        return bool(a) or bool(b)
    if operator == "XOR":
        return bool(a) != bool(b)
    if operator in {"AND", "&"}:
        return bool(a) and bool(b)
    return {
        "=": lambda: a == b,
        "<>": lambda: a != b,
        "<": lambda: a < b,
        ">": lambda: a > b,
        "<=": lambda: a <= b,
        ">=": lambda: a >= b,
        "+": lambda: a + b,
        "-": lambda: a - b,
        "*": lambda: a * b,
        "/": lambda: a / b,
        "MOD": lambda: a % b,
        "**": lambda: a**b,
    }[operator]()
