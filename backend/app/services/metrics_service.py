from __future__ import annotations

import re

from app.schemas.contracts import StructuredTextMetrics, StructuredTextMetricsDelta


class MetricsService:
    """Deterministic IEC Structured Text metrics used by optimization."""

    @classmethod
    def calculate(cls, source: str) -> StructuredTextMetrics:
        uncommented = cls._strip_comments(source)
        executable_lines = cls._executable_lines(uncommented)
        upper = uncommented.upper()

        loc = len(executable_lines)
        cyclomatic = cls._cyclomatic_complexity(upper)
        scan_time = cls._estimated_scan_time_ms(upper)
        maintainability = cls._maintainability_index(loc=loc, cyclomatic_complexity=cyclomatic)

        return StructuredTextMetrics(
            loc=loc,
            cyclomaticComplexity=cyclomatic,
            maintainabilityIndex=maintainability,
            estimatedScanTimeMs=scan_time,
        )

    @staticmethod
    def delta(before: StructuredTextMetrics, after: StructuredTextMetrics) -> StructuredTextMetricsDelta:
        return StructuredTextMetricsDelta(
            loc=after.loc - before.loc,
            cyclomaticComplexity=after.cyclomaticComplexity - before.cyclomaticComplexity,
            maintainabilityIndex=after.maintainabilityIndex - before.maintainabilityIndex,
            estimatedScanTimeMs=round(after.estimatedScanTimeMs - before.estimatedScanTimeMs, 3),
            locReductionPercent=MetricsService._reduction_percent(before.loc, after.loc),
            cyclomaticReductionPercent=MetricsService._reduction_percent(before.cyclomaticComplexity, after.cyclomaticComplexity),
            maintainabilityGainPercent=MetricsService._gain_percent(before.maintainabilityIndex, after.maintainabilityIndex),
            scanTimeReductionPercent=MetricsService._reduction_percent(before.estimatedScanTimeMs, after.estimatedScanTimeMs),
        )

    @staticmethod
    def _strip_comments(source: str) -> str:
        without_block = re.sub(r"\(\*.*?\*\)", "", source, flags=re.DOTALL)
        return re.sub(r"//.*", "", without_block)

    @staticmethod
    def _executable_lines(source: str) -> list[str]:
        non_executable = re.compile(
            r"^(PROGRAM|END_PROGRAM|FUNCTION_BLOCK|END_FUNCTION_BLOCK|VAR|VAR_INPUT|VAR_OUTPUT|END_VAR)\b",
            flags=re.IGNORECASE,
        )
        declaration = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*:\s*(BOOL|INT|REAL|TIME|STRING)\s*;", flags=re.IGNORECASE)

        lines: list[str] = []
        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if non_executable.match(line):
                continue
            if declaration.match(line):
                continue
            lines.append(line)
        return lines

    @staticmethod
    def _cyclomatic_complexity(upper_source: str) -> int:
        tokens = ["IF", "ELSIF", "CASE", "FOR", "WHILE", "REPEAT"]
        count = sum(len(re.findall(rf"\b{token}\b", upper_source)) for token in tokens)
        return max(1, 1 + count)

    @staticmethod
    def _estimated_scan_time_ms(upper_source: str) -> float:
        assignment_count = upper_source.count(":=")
        boolean_count = sum(len(re.findall(rf"\b{token}\b", upper_source)) for token in ["AND", "OR", "NOT"])
        comparison_count = len(re.findall(r"<=|>=|<>|(?<!:)=|<|>", upper_source))
        branch_count = sum(len(re.findall(rf"\b{token}\b", upper_source)) for token in ["IF", "ELSIF", "CASE"])
        loop_count = sum(len(re.findall(rf"\b{token}\b", upper_source)) for token in ["FOR", "WHILE", "REPEAT"])
        timer_count = sum(len(re.findall(rf"\b{token}\b", upper_source)) for token in ["TON", "TOF", "TP"])

        estimate = (
            0.1
            + assignment_count * 0.08
            + boolean_count * 0.02
            + comparison_count * 0.04
            + branch_count * 0.1
            + loop_count * 0.5
            + timer_count * 0.25
        )
        return round(estimate, 3)

    @staticmethod
    def _maintainability_index(*, loc: int, cyclomatic_complexity: int) -> int:
        score = 100 - (loc * 1.4) - (cyclomatic_complexity * 4.5)
        return max(0, min(100, round(score)))

    @staticmethod
    def _reduction_percent(before: float, after: float) -> float:
        if before == 0:
            return 0.0
        return round(((before - after) / before) * 100, 1)

    @staticmethod
    def _gain_percent(before: float, after: float) -> float:
        if before == 0:
            return 0.0
        return round(((after - before) / before) * 100, 1)
