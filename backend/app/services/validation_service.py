from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
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
    """Runs the MATIEC `iec2c` compiler on Structured Text exactly as written.

    The source is never normalized first (D-005), so a pass is evidence level L1 for the
    delivered code. Each compile gets its own temporary directory for the input file and the
    generated C, so concurrent compiles never share files (P1-02, D-030).
    """

    timeout_seconds = 30
    _diagnostic_pattern = re.compile(r"\b(error|undefined|undeclared|syntax)\b", re.IGNORECASE)

    @property
    def name(self) -> str:
        return "matiec"

    @staticmethod
    def build_command(source_path: Path, output_dir: Path) -> list[str]:
        """-f prints full token locations; -I points at the IEC library; -T keeps the C output private."""
        return [
            str(settings.matiec_bin),
            "-f",
            "-I",
            str(settings.matiec_lib_dir),
            "-T",
            str(output_dir),
            str(source_path),
        ]

    def validate_syntax_sync(self, st_code: str) -> dict:
        """
        Compiles st_code with iec2c. Blocking: async callers run it through asyncio.to_thread.

        Returns:
          {"passed": bool | None, "errors": list[str], "raw_output": str,
           "method": "matiec" | "unavailable", "return_code": int (when iec2c ran),
           "reason": str (when unavailable)}
        """
        if not isinstance(st_code, str) or not st_code.strip():
            return {
                "passed": False,
                "errors": ["Structured Text source is empty."],
                "raw_output": "",
                "method": "matiec",
            }

        matiec_bin = str(settings.matiec_bin)
        if shutil.which(matiec_bin) is None and not Path(matiec_bin).exists():
            return self._unavailable(f"MATIEC binary not found at: {matiec_bin}")
        if not Path(settings.matiec_lib_dir, "ieclib.txt").exists():
            return self._unavailable(f"MATIEC library not found at: {settings.matiec_lib_dir}")

        with tempfile.TemporaryDirectory(prefix="optplc_iec2c_") as work:
            work_dir = Path(work)
            source_path = work_dir / "input.st"
            output_dir = work_dir / "out"
            output_dir.mkdir()
            source_path.write_text(st_code, encoding="utf-8")
            try:
                result = subprocess.run(
                    self.build_command(source_path, output_dir),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_seconds,
                    cwd=work_dir,
                )
            except subprocess.TimeoutExpired:
                return {
                    "passed": False,
                    "errors": [f"MATIEC syntax check timed out after {self.timeout_seconds}s"],
                    "raw_output": "",
                    "method": "matiec",
                }
            except OSError as exc:
                return self._unavailable(f"MATIEC could not be started: {exc}")

        output = self._join_output(result.stdout, result.stderr)
        errors = self._extract_errors(output)
        passed = result.returncode == 0 and not errors
        if not passed and not errors:
            errors = [self._return_code_error(result.returncode)]
        logger.info("[MatiecValidator] iec2c return_code=%s errors=%s", result.returncode, len(errors))
        return {
            "passed": passed,
            "errors": errors,
            "raw_output": output[:3000],
            "method": "matiec",
            "return_code": result.returncode,
        }

    async def validate_syntax(self, st_code: str) -> dict:
        """Async entry point: the same compile, in a worker thread so the event loop is not blocked."""
        return await asyncio.to_thread(self.validate_syntax_sync, st_code)

    async def validate_formal(self, smv_model: str, properties: list[str]) -> dict:
        raise NotImplementedError("MATIEC performs syntax compilation only; formal validation is not implemented here.")

    @staticmethod
    def _unavailable(reason: str) -> dict:
        return {"passed": None, "errors": [], "raw_output": "", "method": "unavailable", "reason": reason}

    @classmethod
    def _extract_errors(cls, raw_output: str) -> list[str]:
        errors: list[str] = []
        for line in raw_output.splitlines():
            normalized = line.strip()
            if normalized and cls._diagnostic_pattern.search(normalized):
                errors.append(normalized)
        return errors

    @staticmethod
    def _join_output(stdout: str | None, stderr: str | None) -> str:
        return "\n".join(part for part in [(stdout or "").strip(), (stderr or "").strip()] if part)

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
        errors = list(result.get("errors", []))
        if not errors and result.get("reason"):
            errors = [str(result["reason"])]
        return {
            "validator": self.syntax_validator.name,
            "passed": bool(result.get("passed", False)),
            "errors": errors,
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
