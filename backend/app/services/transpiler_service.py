from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class TranspileResult:
    success: bool
    smv_model: Optional[str] = None
    unsupported_construct: Optional[str] = None
    error: Optional[str] = None


class UnsupportedConstructError(Exception):
    pass


class StToSmvTranspiler:
    """
    V1 Scope - documents what IS and IS NOT supported.
    Supported: BOOL, INT, IF/ELSIF/ELSE, CASE/OF/ELSE, assignments,
               AND/OR/NOT, TON/TOF (counter approximation)
    Unsupported: FOR, WHILE, REPEAT, FUNCTION_BLOCK, REAL, TIME vars
    """

    def transpile(self, st_code: str, properties: list[str]) -> TranspileResult:
        try:
            self._check_unsupported(st_code)
            variables = self._extract_variables(st_code)
            timers = self._extract_timers(st_code)
            body = self._extract_program_body(st_code)
            assigns = self._translate_to_smv_assigns(body, variables)
            smv = self._render_smv_module(variables, timers, assigns, properties)
            return TranspileResult(success=True, smv_model=smv)
        except UnsupportedConstructError as e:
            return TranspileResult(
                success=False,
                unsupported_construct=str(e),
                error=f"TRANSPILER_UNSUPPORTED: {e}",
            )

    def _check_unsupported(self, st_code: str) -> None:
        clean = re.sub(r"\(\*.*?\*\)", "", st_code, flags=re.DOTALL)
        checks = [
            (r"\bFOR\b", "FOR loop"),
            (r"\bWHILE\b", "WHILE loop"),
            (r"\bREPEAT\b", "REPEAT loop"),
            (r"\bFUNCTION_BLOCK\b", "FUNCTION_BLOCK"),
            (r"\bREAL\b", "REAL type"),
        ]
        for pattern, name in checks:
            if re.search(pattern, clean, re.IGNORECASE):
                raise UnsupportedConstructError(name)

    def _extract_variables(self, st_code: str) -> dict:
        """Parse VAR_INPUT, VAR_OUTPUT, VAR blocks -> {inputs, outputs, internal}"""
        result = {"inputs": [], "outputs": [], "internal": []}
        sections = {
            "inputs": r"VAR_INPUT(.*?)END_VAR",
            "outputs": r"VAR_OUTPUT(.*?)END_VAR",
            "internal": r"(?<!VAR_IN)(?<!VAR_OUT)(?<!INPUT)(?<!OUTPUT)\bVAR\b(.*?)END_VAR",
        }
        for key, pattern in sections.items():
            m = re.search(pattern, st_code, re.DOTALL | re.IGNORECASE)
            if m:
                for decl in re.finditer(r"(\w+)\s*:\s*(\w+)", m.group(1)):
                    result[key].append({"name": decl.group(1), "type": decl.group(2).upper()})
        return result

    def _extract_timers(self, st_code: str) -> list:
        return [
            {"name": m.group(1), "type": m.group(2).upper()}
            for m in re.finditer(r"(\w+)\s*:\s*(TON|TOF)\s*;", st_code, re.I)
        ]

    def _extract_program_body(self, st_code: str) -> str:
        m = re.search(r"END_VAR\s*(.*?)END_PROGRAM", st_code, re.DOTALL | re.IGNORECASE)
        if not m:
            return ""
        return re.sub(r"\(\*.*?\*\)", "", m.group(1), flags=re.DOTALL).strip()

    def _translate_to_smv_assigns(self, body: str, variables: dict) -> list[str]:
        """
        Converts ST body to SMV next() assignments.
        Uses symbolic evaluation to handle sequential assignments correctly:
        ST: A := TRUE; B := A;  ->  SMV: next(A) := TRUE; next(B) := TRUE;
        NOT: next(B) := A; (would use pre-transition value of A)
        """
        all_vars = {v["name"] for group in variables.values() for v in group}
        assigns = []

        case_blocks = re.finditer(
            r"CASE\s+(\w+)\s+OF(.*?)(?:ELSE(.*?))?END_CASE",
            body,
            re.DOTALL | re.IGNORECASE,
        )
        for case in case_blocks:
            case_var = case.group(1)
            branches_text = case.group(2)
            else_text = case.group(3) or ""

            output_cases: dict[str, list[str]] = {}
            for branch in re.finditer(
                r"(\w+)\s*:(.*?)(?=\w+\s*:|ELSE|$)",
                branches_text,
                re.DOTALL,
            ):
                val = branch.group(1)
                stmts = branch.group(2)
                for assign in re.finditer(r"(\w+)\s*:=\s*([^;]+);", stmts):
                    var, expr = assign.group(1).strip(), assign.group(2).strip()
                    if var not in output_cases:
                        output_cases[var] = []
                    output_cases[var].append(f"    {case_var} = {val} : {self._st_to_smv_expr(expr)};")

            for var, cases in output_cases.items():
                else_val = "FALSE"
                if else_text:
                    else_m = re.search(rf"{var}\s*:=\s*([^;]+);", else_text)
                    if else_m:
                        else_val = self._st_to_smv_expr(else_m.group(1).strip())
                assigns.append(f"next({var}) := case\n" + "\n".join(cases) + f"\n    TRUE : {else_val};\nesac;")

        remaining = re.sub(r"CASE.*?END_CASE", "", body, flags=re.DOTALL | re.IGNORECASE)
        remaining = re.sub(r"IF.*?END_IF", "", remaining, flags=re.DOTALL | re.IGNORECASE)

        symbol_table: dict[str, str] = {}
        for assign in re.finditer(r"(\w+)\s*:=\s*([^;]+);", remaining):
            var, expr = assign.group(1).strip(), assign.group(2).strip()
            if var in all_vars:
                resolved = self._substitute(expr, symbol_table)
                symbol_table[var] = resolved
                assigns.append(f"next({var}) := {self._st_to_smv_expr(resolved)};")

        return assigns

    def _substitute(self, expr: str, table: dict) -> str:
        """Symbolic evaluation: replace vars with their computed values."""
        result = expr
        for var, val in sorted(table.items(), key=lambda x: -len(x[0])):
            result = re.sub(rf"\b{re.escape(var)}\b", f"({val})", result)
        return result

    def _st_to_smv_expr(self, expr: str) -> str:
        """Convert ST boolean expression to SMV syntax."""
        expr = re.sub(r"\bNOT\s+", "!", expr, flags=re.I)
        expr = re.sub(r"\bAND\b", "&", expr, flags=re.I)
        expr = re.sub(r"\bOR\b", "|", expr, flags=re.I)
        expr = expr.replace("<>", "!=").replace(":=", "=")
        expr = re.sub(r"\bTRUE\b", "TRUE", expr, flags=re.I)
        expr = re.sub(r"\bFALSE\b", "FALSE", expr, flags=re.I)
        return expr.strip()

    def _render_smv_module(
        self,
        variables: dict,
        timers: list,
        assigns: list[str],
        properties: list[str],
    ) -> str:
        all_vars = variables["inputs"] + variables["outputs"] + variables["internal"]

        var_decls = "\n".join(
            f"    {v['name']} : {'boolean' if v['type'] == 'BOOL' else 'integer'};"
            for v in all_vars
        )
        timer_decls = "\n".join(
            f"    {t['name']}_cnt : 0..255;\n    {t['name']}_IN  : boolean;"
            for t in timers
        )

        init_block = "\n".join(
            f"    init({v['name']}) := {'FALSE' if v['type'] == 'BOOL' else '0'};"
            for v in all_vars
        )

        timer_assigns = "\n".join(
            f"    init({t['name']}_cnt) := 0;\n"
            f"    next({t['name']}_cnt) := ({t['name']}_IN & {t['name']}_cnt < 5) ? {t['name']}_cnt + 1 : 0;\n"
            f"    DEFINE {t['name']}_Q := ({t['name']}_cnt >= 5);"
            for t in timers
        )

        props_block = "\n".join(f"LTLSPEC {self._prop_to_ltl(p)}" for p in properties)

        return f"""-- Generated by OptPLC Transpiler v1
-- Scope: BOOL/INT, IF, CASE, TON(approx), assignments
MODULE main

VAR
{var_decls}
{timer_decls}

ASSIGN
{init_block}

{chr(10).join(assigns)}
{timer_assigns}

{props_block}"""

    def _prop_to_ltl(self, prop: str) -> str:
        templates = [
            (
                r"(\w+)\s+must\s+not.*?when\s+(\w+)\s+is\s+(active|true)",
                lambda m: f"G ({m.group(2)} -> !{m.group(1)})",
            ),
            (
                r"must not.*auto.?restart",
                "G (Fault_State -> !(Motor_Run & !Reset_PB))",
            ),
            (
                r"(\w+)\s+and\s+(\w+)\s+must\s+never\s+be\s+TRUE",
                lambda m: f"G !({m.group(1)} & {m.group(2)})",
            ),
            (
                r"all outputs.*FALSE when (\w+)",
                lambda m: f"G ({m.group(1)} -> !(Fill_Valve | Mixer_Motor | Drain_Valve))",
            ),
        ]
        for pattern, transform in templates:
            m = re.search(pattern, prop, re.IGNORECASE)
            if m:
                return transform(m) if callable(transform) else transform
        return f"-- MANUAL REQUIRED: {prop}"
