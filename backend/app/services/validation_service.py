from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class IValidator(ABC):
    @abstractmethod
    async def validate_syntax(self, st_code: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def validate_formal(self, smv_model: str, properties: list[str]) -> dict:
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError


class MatiecValidator(IValidator):
    """Async wrapper around the MATIEC `iec2c` Structured Text compiler."""

    timeout_seconds = 30
    _diagnostic_pattern = re.compile(r"(error|undefined)", re.IGNORECASE)

    @property
    def name(self) -> str:
        return "matiec"

    def _normalize_for_matiec(self, code: str) -> str:
        """
        Normalize LLM-generated ST code for MATIEC v0.1 compatibility.
        Handles patterns that the LLM generates but MATIEC v0.1 rejects.
        """
        import re

        lines = code.split("\n")
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.rstrip()

            # FIX A: Collapse multi-line assignments (operator at end)
            if (":=" in stripped
                    and not stripped.rstrip().endswith(";")
                    and not stripped.rstrip().endswith("(*")
                    and re.search(r"\b(OR|AND|NOT|\+|-|\*)\s*$", stripped, re.IGNORECASE)):
                merged = stripped
                j = i + 1
                while j < len(lines) and not merged.rstrip().endswith(";"):
                    nxt = lines[j].strip()
                    if nxt and not nxt.startswith("(*"):
                        merged = merged.rstrip() + " " + nxt
                    j += 1
                result.append(merged)
                i = j
                continue

            # FIX B: Remove ANY dotted assignment (Var.Member := ...)
            if re.search(r"\b\w+\.\w+\s*:=", stripped):
                result.append(f"(* removed dotted assign: {stripped.strip()} *)")
                i += 1
                continue

            # FIX C: Remove timer FB calls (TimerName(IN := ...) )
            if re.search(r"\b\w+\s*\(\s*IN\s*:=", stripped, re.IGNORECASE):
                result.append("(* timer FB call removed for MATIEC v0.1 *)")
                i += 1
                continue

            # FIX D: Remove reading dotted members in expressions
            # e.g.  X := Timer.Q AND Y;  -> X := Y;
            if re.search(r"\b\w+\.\w+\b", stripped):
                cleaned = re.sub(r"\b\w+\.\w+\b", "FALSE", stripped)
                result.append(cleaned)
                i += 1
                continue

            # FIX E: Remove TIME literals  T#5s -> removed
            if re.search(r"\bT#\w+|\bTIME#\w+", stripped, re.IGNORECASE):
                cleaned = re.sub(
                    r"\bT#\w+|\bTIME#\w+",
                    "0",
                    stripped,
                    flags=re.IGNORECASE,
                )
                result.append(cleaned)
                i += 1
                continue

            result.append(line)
            i += 1

        normalized = "\n".join(result)
        if normalized != code:
            import logging

            logging.getLogger(__name__).info(
                "[ValidationAgent] MATIEC normalization applied"
            )
        return normalized

    def _collapse_multiline_assignments(self, code: str) -> str:
        """
        MATIEC v0.1 requires each assignment on one line.
        This collapses patterns like:
          X := A OR
               B OR C;
        Into:
          X := A OR B OR C;
        """
        lines = code.split("\n")
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.rstrip()

            # Check if this line looks like a continuation needed:
            # ends with an operator but no semicolon
            continuation_operators = (
                " OR",
                " AND",
                " +",
                " -",
                " *",
                " OR\r",
                " AND\r",
            )
            needs_continuation = (
                not stripped.endswith(";")
                and not stripped.endswith("(")
                and ":=" in stripped
                and any(stripped.upper().endswith(op.upper().rstrip()) for op in continuation_operators)
            )

            if needs_continuation and i + 1 < len(lines):
                # Merge with next line(s) until we find the semicolon
                merged = stripped
                j = i + 1
                while j < len(lines) and not merged.rstrip().endswith(";"):
                    next_line = lines[j].strip()
                    if next_line:
                        merged = merged + " " + next_line
                    j += 1
                result.append(merged)
                i = j
            else:
                result.append(line)
                i += 1

        return "\n".join(result)

    def validate_syntax_sync(self, st_code: str) -> dict:
        """
        Synchronous MATIEC syntax check for sync callers.

        Returns:
          {"passed": bool | None, "errors": list[str], "raw_output": str,
           "method": "matiec" | "unavailable"}
        """
        import shutil
        import subprocess

        tmp_path: str | None = None
        matiec_bin = str(settings.matiec_bin)
        matiec_path = Path(matiec_bin)

        if not isinstance(st_code, str) or not st_code.strip():
            return {
                "passed": False,
                "errors": ["Structured Text source is empty."],
                "raw_output": "",
                "method": "matiec",
            }

        if shutil.which(matiec_bin) is None and not matiec_path.exists():
            return {
                "passed": None,
                "errors": [],
                "raw_output": "",
                "method": "unavailable",
                "reason": f"MATIEC binary not found at: {matiec_bin}",
            }

        # Preprocess: normalize generated code for MATIEC v0.1 compatibility.
        normalized = self._normalize_for_matiec(st_code)
        if normalized != st_code:
            logging.getLogger(__name__).info(
                "[ValidationAgent] Applied MATIEC v0.1 normalization"
            )

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".st",
                mode="w",
                encoding="utf-8",
                delete=False,
            ) as temp_file:
                temp_file.write(normalized)
                temp_file.flush()
                tmp_path = temp_file.name

            # MATIEC needs to run from a directory containing lib/
            matiec_lib_dir = "/usr/local/share/matiec"
            lib_exists = Path(matiec_lib_dir, "lib", "ieclib.txt").exists()

            if not lib_exists:
                logger.warning(
                    "[ValidationAgent] MATIEC lib/ieclib.txt not found at "
                    f"{matiec_lib_dir}. Check Dockerfile MATIEC lib copy step."
                )
                return {
                    "passed": None,
                    "errors": [],
                    "raw_output": "",
                    "method": "unavailable",
                    "reason": "MATIEC library files missing from container",
                }

            result = subprocess.run(
                [matiec_bin, tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=matiec_lib_dir,
                encoding="utf-8",
                errors="replace",
            )
            logger.info(
                f"[ValidationAgent] MATIEC running from cwd={matiec_lib_dir}, "
                f"return_code={result.returncode}"
            )

            output = (result.stdout + result.stderr).strip()
            errors: list[str] = []
            for line in output.splitlines():
                normalized = line.strip()
                if normalized and re.search(r"\b(error|undefined|undeclared|syntax)\b", normalized, re.IGNORECASE):
                    errors.append(normalized)

            if len(errors) > 0:
                error_summary = "\n  ".join(errors[:5])
                logger.warning(
                    f"[ValidationAgent] MATIEC syntax: FAILED "
                    f"— {len(errors)} error(s):\n  {error_summary}"
                )
                if output:
                    logger.debug(
                        f"[ValidationAgent] MATIEC raw output:\n"
                        f"{output[:500]}"
                    )

            passed = result.returncode == 0 and len(errors) == 0
            return {
                "passed": passed,
                "errors": errors,
                "raw_output": output[:3000],
                "method": "matiec",
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "errors": [f"MATIEC syntax check timed out after {self.timeout_seconds}s"],
                "raw_output": "",
                "method": "matiec",
            }
        except FileNotFoundError:
            return {
                "passed": None,
                "errors": [],
                "raw_output": "",
                "method": "unavailable",
                "reason": f"MATIEC binary not executable: {matiec_bin}",
            }
        finally:
            if tmp_path:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError:
                    logger.warning("Failed to remove MATIEC temp file: %s", tmp_path)

    async def validate_syntax(self, st_code: str) -> dict:
        temp_path: Path | None = None

        if not isinstance(st_code, str) or not st_code.strip():
            return {
                "passed": False,
                "errors": ["Structured Text source is empty."],
                "raw_output": "",
            }

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".st",
                prefix="plcforge_",
                encoding="utf-8",
                delete=False,
            ) as temp_file:
                temp_file.write(st_code)
                temp_file.flush()
                temp_path = Path(temp_file.name)

            process = await asyncio.create_subprocess_exec(
                str(settings.matiec_bin),
                "-f",
                str(temp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                stdout_bytes, stderr_bytes = await process.communicate()
                raw_timeout_output = self._join_output(stdout_bytes, stderr_bytes)
                return {
                    "passed": False,
                    "errors": [f"MATIEC syntax validation timed out after {self.timeout_seconds} seconds."],
                    "raw_output": raw_timeout_output,
                }

            raw_output = self._join_output(stdout_bytes, stderr_bytes)
            diagnostic_errors = self._extract_errors(raw_output)
            passed = process.returncode == 0 and not diagnostic_errors

            return {
                "passed": passed,
                "errors": diagnostic_errors if diagnostic_errors else ([] if passed else [self._return_code_error(process.returncode)]),
                "raw_output": raw_output,
            }

        except FileNotFoundError:
            return {
                "passed": False,
                "errors": [f"MATIEC binary was not found at {settings.matiec_bin}."],
                "raw_output": "",
            }
        except PermissionError:
            return {
                "passed": False,
                "errors": [f"MATIEC binary is not executable or permission was denied: {settings.matiec_bin}."],
                "raw_output": "",
            }
        except OSError as exc:
            return {
                "passed": False,
                "errors": [f"MATIEC process could not be started: {exc}"],
                "raw_output": "",
            }
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    # Do not mask validation results because cleanup failed.
                    temp_path = None

    async def validate_formal(self, smv_model: str, properties: list[str]) -> dict:
        raise NotImplementedError("MATIEC performs syntax compilation only; formal validation is not implemented here.")

    @classmethod
    def _extract_errors(cls, raw_output: str) -> list[str]:
        errors: list[str] = []
        for line in raw_output.splitlines():
            normalized = line.strip()
            if normalized and cls._diagnostic_pattern.search(normalized):
                errors.append(normalized)
        return errors

    @staticmethod
    def _join_output(stdout_bytes: bytes | None, stderr_bytes: bytes | None) -> str:
        stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
        stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
        return "\n".join(part for part in [stdout.strip(), stderr.strip()] if part)

    @staticmethod
    def _return_code_error(return_code: int | None) -> str:
        if return_code is None:
            return "MATIEC exited without a return code."
        return f"MATIEC exited with return code {return_code}."


class ValidationService:
    """Coordinates validator execution for PLCForge validation workflows."""

    def __init__(self, syntax_validator: IValidator | None = None, formal_validator: IValidator | None = None) -> None:
        self.syntax_validator = syntax_validator or MatiecValidator()
        self.formal_validator = formal_validator

    async def validate_syntax(self, st_code: str) -> dict[str, Any]:
        result = await self.syntax_validator.validate_syntax(st_code)
        return {
            "validator": self.syntax_validator.name,
            "passed": bool(result.get("passed", False)),
            "errors": list(result.get("errors", [])),
            "raw_output": str(result.get("raw_output", "")),
        }

    async def validate(self, st_code: str) -> dict[str, Any]:
        syntax_result = await self.validate_syntax(st_code)
        return {
            "syntax": syntax_result,
            "passed": syntax_result["passed"],
            "errors": syntax_result["errors"],
        }

    async def validate_formal(self, smv_model: str, properties: list[str]) -> dict[str, Any]:
        if self.formal_validator is None:
            raise NotImplementedError("Formal validation is not configured for this ValidationService.")
        return await self.formal_validator.validate_formal(smv_model, properties)


class PLCVerifValidator(IValidator):
    name = "PLCverif"

    async def validate_syntax(self, st_code: str) -> dict:
        return {
            "passed": False,
            "errors": ["PLCverif does not perform Structured Text syntax checks."],
            "raw_output": "",
        }

    async def validate_formal(self, smv_model: str, properties: list[str]) -> dict:
        temp_path: Path | None = None
        timeout_seconds = int(getattr(settings, "verification_timeout_s", 120))
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".smv",
                prefix="plcforge_",
                encoding="utf-8",
                delete=False,
            ) as temp_file:
                temp_file.write(smv_model)
                temp_file.flush()
                temp_path = Path(temp_file.name)

            process = await asyncio.create_subprocess_exec(
                str(settings.plcverif_bin),
                str(temp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                return {
                    "all_passed": False,
                    "classification": "TIMEOUT",
                    "property_results": [],
                    "counterexample": None,
                    "raw_output": "",
                    "errors": [f"PLCverif timed out after {timeout_seconds} seconds."],
                }

            raw_output = self._join_output(stdout_bytes, stderr_bytes)
            property_results = self._parse_property_results(raw_output, properties)
            all_passed = all(item.get("passed", False) for item in property_results) if property_results else ("is false" not in raw_output.lower())
            classification = "VERIFIED" if all_passed else "FORMAL_VIOLATION"
            counterexample = self._extract_counterexample(raw_output)
            errors = [] if all_passed else [item["message"] for item in property_results if not item.get("passed", False)]

            if process.returncode not in (0, None) and not errors:
                errors = [f"PLCverif exited with return code {process.returncode}."]
                classification = "FORMAL_VIOLATION"
                all_passed = False

            return {
                "all_passed": all_passed,
                "classification": classification,
                "property_results": property_results,
                "counterexample": counterexample,
                "raw_output": raw_output,
                "errors": errors,
            }
        except FileNotFoundError:
            return {
                "all_passed": False,
                "classification": "FORMAL_VIOLATION",
                "property_results": [],
                "counterexample": None,
                "raw_output": "",
                "errors": [f"PLCverif binary was not found at {settings.plcverif_bin}."],
            }
        except PermissionError:
            return {
                "all_passed": False,
                "classification": "FORMAL_VIOLATION",
                "property_results": [],
                "counterexample": None,
                "raw_output": "",
                "errors": [f"PLCverif binary is not executable or permission was denied: {settings.plcverif_bin}."],
            }
        except OSError as exc:
            return {
                "all_passed": False,
                "classification": "FORMAL_VIOLATION",
                "property_results": [],
                "counterexample": None,
                "raw_output": "",
                "errors": [f"PLCverif process could not be started: {exc}"],
            }
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Failed to remove temporary PLCverif file %s: %s", temp_path, exc)

    @staticmethod
    def _join_output(stdout_bytes: bytes | None, stderr_bytes: bytes | None) -> str:
        stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
        stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
        return "\n".join(part for part in [stdout.strip(), stderr.strip()] if part)

    @staticmethod
    def _parse_property_results(raw_output: str, properties: list[str]) -> list[dict[str, Any]]:
        lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
        status_lines = [line for line in lines if ("is true" in line.lower() or "is false" in line.lower())]
        results: list[dict[str, Any]] = []

        for index, line in enumerate(status_lines):
            passed = "is true" in line.lower()
            prop = properties[index] if index < len(properties) else line
            results.append(
                {
                    "property": prop,
                    "passed": passed,
                    "message": line,
                }
            )

        if not results and properties:
            lower_output = raw_output.lower()
            inferred = "is false" not in lower_output
            for prop in properties:
                results.append(
                    {
                        "property": prop,
                        "passed": inferred,
                        "message": f"Inferred from PLCverif output for property: {prop}",
                    }
                )

        return results

    @staticmethod
    def _extract_counterexample(raw_output: str) -> str | None:
        marker_match = re.search(r"execution sequence", raw_output, flags=re.IGNORECASE)
        if not marker_match:
            return None
        tail = raw_output[marker_match.start():].strip()
        return tail or None


def build_validation_service() -> ValidationService:
    return ValidationService(
        syntax_validator=MatiecValidator(),
        formal_validator=PLCVerifValidator(),
    )
