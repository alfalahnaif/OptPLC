from __future__ import annotations

import logging
import math
import re

from app.schemas.contracts import StructuredTextMetrics, StructuredTextMetricsDelta
from app.services.st_parser import STAstParser

logger = logging.getLogger(__name__)


class MetricsService:
    """Deterministic IEC Structured Text metrics used by optimization."""

    _parser = STAstParser()
    _block_comment_pattern = re.compile(r"\(\*.*?\*\)", re.DOTALL)
    _line_comment_pattern = re.compile(r"//.*?$", re.MULTILINE)
    _non_executable_pattern = re.compile(
        r"^(PROGRAM|END_PROGRAM|FUNCTION_BLOCK|END_FUNCTION_BLOCK|VAR|VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR_GLOBAL|END_VAR)\b",
        flags=re.IGNORECASE,
    )
    _declaration_pattern = re.compile(
        r"^[A-Za-z_][A-Za-z0-9_]*\s*:\s*(BOOL|INT|DINT|REAL|LREAL|TIME|STRING|TON|TOF|TP)\s*;",
        flags=re.IGNORECASE,
    )
    _if_elsif_pattern = re.compile(r"\b(IF|ELSIF)\b", re.IGNORECASE)
    _comparison_pattern = re.compile(r"<=|>=|<>|(?<!:)=|<|>")
    _boolean_pattern = re.compile(r"\b(AND|OR|NOT)\b", re.IGNORECASE)
    _timer_pattern = re.compile(r"\b(TON|TOF|TP)\b", re.IGNORECASE)
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

    @classmethod
    def calculate(cls, source: str) -> StructuredTextMetrics:
        uncommented = cls._strip_comments(source)
        executable_lines = cls._executable_lines(uncommented)
        normalized = uncommented.upper()

        loc = len(executable_lines)
        cyclomatic = cls._cyclomatic_complexity(source)
        scan_time = cls._estimated_scan_time_ms(normalized)
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
        without_block = MetricsService._block_comment_pattern.sub("", source)
        return MetricsService._line_comment_pattern.sub("", without_block)

    @staticmethod
    def _executable_lines(source: str) -> list[str]:
        lines: list[str] = []
        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if MetricsService._non_executable_pattern.match(line):
                continue
            if MetricsService._declaration_pattern.match(line):
                continue
            lines.append(line)
        return lines

    @staticmethod
    def _cyclomatic_complexity(source: str) -> int:
        decision_points, fallback_used = MetricsService._parser.count_decision_points_with_metadata(source)
        if fallback_used:
            logger.info("MetricsService parser fallback used for decision counting.")
        return max(1, 1 + decision_points)

    @staticmethod
    def _estimated_scan_time_ms(normalized_source: str) -> float:
        assignment_count = normalized_source.count(":=")
        if_elsif_count = len(MetricsService._if_elsif_pattern.findall(normalized_source))
        case_branch_count = MetricsService._count_case_branches(normalized_source)
        boolean_count = len(MetricsService._boolean_pattern.findall(normalized_source))
        comparison_count = len(MetricsService._comparison_pattern.findall(normalized_source))
        timer_count = len(MetricsService._timer_pattern.findall(normalized_source))

        estimate = (
            0.1
            + assignment_count * 0.07
            + if_elsif_count * 0.12
            + case_branch_count * 0.1
            + boolean_count * 0.02
            + comparison_count * 0.035
            + timer_count * 0.25
        )
        return round(estimate, 3)

    @staticmethod
    def _maintainability_index(*, loc: int, cyclomatic_complexity: int) -> int:
        safe_loc = max(1, loc)
        safe_cyclomatic = max(1, cyclomatic_complexity)
        try:
            # Keep MI within practical PLC ranges by using a logarithmic size penalty.
            # This avoids collapsing to zero for moderate-size programs.
            raw = 171.0 - (21.4 * math.log(safe_loc)) - (0.23 * safe_cyclomatic)
            score = (raw * 100.0) / 171.0
        except (ValueError, OverflowError):  # pragma: no cover - defensive fallback
            score = 0.0
        return max(0, min(100, round(score)))

    @staticmethod
    def _count_case_branches(source: str) -> int:
        total = 0
        for case_match in MetricsService._case_block_pattern.finditer(source):
            body = case_match.group("body")
            total += len(MetricsService._case_branch_pattern.findall(body))
        return total

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
