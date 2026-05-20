from __future__ import annotations

import asyncio
import re
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.config import settings


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
