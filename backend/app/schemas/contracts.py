from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def _read_legacy_verified(value: object) -> object:
    """Reports stored before D-033 say VERIFIED. It only ever meant that the checks passed."""
    return "CHECKS_PASSED" if value == "VERIFIED" else value


ProjectStatus = Literal["draft", "planned", "generated", "validated", "optimized", "failed"]
AgentStatus = Literal["pending", "running", "completed", "failed"]
SignalType = Literal["BOOL", "INT", "REAL", "TIME", "STRING"]
ValidationStatus = Annotated[
    Literal["CHECKS_PASSED", "SYNTAX_ERROR", "FORMAL_VIOLATION", "TIMEOUT"],
    BeforeValidator(_read_legacy_verified),
]
DebuggingStatus = Literal["NOT_REQUIRED", "PATCH_ADVICE_GENERATED", "CANNOT_DEBUG"]
RepairLoopFinalStatus = Annotated[
    Literal["CHECKS_PASSED", "FAILED", "ITERATION_LIMIT_REACHED"],
    BeforeValidator(_read_legacy_verified),
]
# Evidence ladder L0-L6 (D-003, D-033). Only L4 and above may be called verified.
EvidenceLevel = Literal[
    "GENERATED",
    "COMPILES",
    "STATIC_RULES_PASSED",
    "SIMULATION_TESTED",
    "PROPERTIES_PROVEN",
    "HIL_PASSED",
    "ENGINEER_APPROVED",
]
OptimizationStatus = Literal["OPTIMIZED", "NO_CHANGES", "ROLLED_BACK", "CANNOT_OPTIMIZE"]
OptimizationPassStatus = Literal["applied", "rolled_back", "no_changes"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Project(ContractModel):
    id: str
    name: str
    domain: str
    description: str
    standard: Literal["IEC 61131-3"]
    targetLanguage: Literal["Structured Text"]
    status: ProjectStatus
    createdAt: str
    updatedAt: str


# Input size limits (P1-08, D-032). Oversized input is rejected with 422 before any LLM call.
MAX_PROJECT_NAME_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 2_000
MAX_DOMAIN_LENGTH = 80
MAX_REQUIREMENT_LENGTH = 8_000
MAX_CONSTRAINT_LENGTH = 500
MAX_CONSTRAINTS = 30
MAX_SIGNAL_NAME_LENGTH = 64
MAX_SIGNALS = 100


def _check_item_lengths(values: list[str], limit: int, label: str) -> list[str]:
    for value in values:
        if len(value) > limit:
            raise ValueError(f"Each {label} must be at most {limit} characters.")
    return values


class CreateProjectRequest(ContractModel):
    name: str = Field(min_length=1, max_length=MAX_PROJECT_NAME_LENGTH)
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_LENGTH)
    domain: str = Field(min_length=1, max_length=MAX_DOMAIN_LENGTH)
    targetLanguage: Literal["Structured Text"]
    complexityTier: Literal["simple", "medium", "complex"]


class PerformanceTargets(ContractModel):
    maxScanTimeMs: float = 5
    maxCyclomaticComplexity: int = 8
    minMaintainabilityIndex: int = 75
    maxIterations: int = 5


class RequirementInput(ContractModel):
    projectId: str
    text: str = Field(min_length=1, max_length=MAX_REQUIREMENT_LENGTH)
    safetyConstraints: list[str] = Field(
        default_factory=list,
        max_length=MAX_CONSTRAINTS,
        validation_alias=AliasChoices("safetyConstraints", "safety_constraints"),
        serialization_alias="safetyConstraints",
    )
    performanceTargets: PerformanceTargets = Field(
        validation_alias=AliasChoices("performanceTargets", "performance_targets"),
        serialization_alias="performanceTargets",
    )
    confirmedOutputs: list[str] = Field(
        default_factory=list,
        max_length=MAX_SIGNALS,
        validation_alias=AliasChoices("confirmedOutputs", "confirmed_outputs"),
        serialization_alias="confirmedOutputs",
    )
    confirmedInputs: list[str] = Field(
        default_factory=list,
        max_length=MAX_SIGNALS,
        validation_alias=AliasChoices("confirmedInputs", "confirmed_inputs"),
        serialization_alias="confirmedInputs",
    )
    domain: str | None = Field(default=None, max_length=MAX_DOMAIN_LENGTH)
    complexityTier: str | None = Field(
        default=None,
        validation_alias=AliasChoices("complexityTier", "complexity_tier"),
        serialization_alias="complexityTier",
    )

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Requirement text must not be empty.")
        return value

    @field_validator("safetyConstraints")
    @classmethod
    def constraints_within_limit(cls, value: list[str]) -> list[str]:
        return _check_item_lengths(value, MAX_CONSTRAINT_LENGTH, "safety constraint")

    @field_validator("confirmedOutputs", "confirmedInputs")
    @classmethod
    def signal_names_within_limit(cls, value: list[str]) -> list[str]:
        return _check_item_lengths(value, MAX_SIGNAL_NAME_LENGTH, "signal name")


class AnalyzeRequirementRequest(ContractModel):
    """Body of POST /api/projects/{id}/analyze-requirement. It was a free dict before P1-08 (S-05)."""

    text: str = Field(default="", max_length=MAX_REQUIREMENT_LENGTH)
    safetyConstraints: list[str] = Field(default_factory=list, max_length=MAX_CONSTRAINTS)

    @field_validator("safetyConstraints")
    @classmethod
    def constraints_within_limit(cls, value: list[str]) -> list[str]:
        return _check_item_lengths(value, MAX_CONSTRAINT_LENGTH, "safety constraint")


class AnalysisSignal(BaseModel):
    """A signal proposed by the requirement analysis. Mirrors AnalysisSignal in src/lib/api-contracts/types.ts."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=MAX_SIGNAL_NAME_LENGTH)
    type: Literal["BOOL", "INT", "REAL", "TIME"]
    source: Literal["Operator", "Safety", "Sensor", "Timer"] | None = None
    description: str | None = None
    confirmed: bool | None = None

    @field_validator("type", mode="before")
    @classmethod
    def type_upper_case(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("source", mode="before")
    @classmethod
    def unknown_source_is_dropped(cls, value: object) -> object:
        # source is optional display metadata, so an unknown label is dropped instead of failing the reply
        return value if value in {"Operator", "Safety", "Sensor", "Timer"} else None


class RequirementAnalysis(BaseModel):
    """Validated requirement analysis (P1-08, D-032). Mirrors AnalysisResult in src/lib/api-contracts/types.ts."""

    model_config = ConfigDict(extra="ignore")

    domain: str = Field(max_length=MAX_DOMAIN_LENGTH)
    confidence: float = Field(ge=0.0, le=1.0)
    inferred_inputs: list[AnalysisSignal] = Field(default_factory=list, max_length=MAX_SIGNALS)
    suggested_outputs: list[AnalysisSignal] = Field(default_factory=list, max_length=MAX_SIGNALS)
    suggested_internals: list[AnalysisSignal] = Field(default_factory=list, max_length=MAX_SIGNALS)
    safety_constraints: list[str] = Field(default_factory=list)
    suggested_constraints: list[str] = Field(default_factory=list, max_length=MAX_CONSTRAINTS)
    projectId: str | None = None
    analyzedAt: str | None = None
    source: Literal["llm", "heuristic", "empty"] | None = None


class RequirementPayload(ContractModel):
    projectId: str
    text: str
    safetyConstraints: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("safetyConstraints", "safety_constraints"),
        serialization_alias="safetyConstraints",
    )
    confirmedOutputs: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("confirmedOutputs", "confirmed_outputs"),
        serialization_alias="confirmedOutputs",
    )
    confirmedInputs: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("confirmedInputs", "confirmed_inputs"),
        serialization_alias="confirmedInputs",
    )
    performanceTargets: PerformanceTargets = Field(
        validation_alias=AliasChoices("performanceTargets", "performance_targets"),
        serialization_alias="performanceTargets",
    )
    domain: str | None = None
    complexityTier: str | None = None
    submittedAt: str | None = None
    updatedAt: str | None = None


class PlanSignal(ContractModel):
    name: str = Field(min_length=1)
    type: SignalType
    address: str | None = None
    source: str | None = None
    description: str = Field(min_length=1)

    @field_validator("name", "description")
    @classmethod
    def signal_text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Signal name and description must not be empty.")
        return value


class InternalVar(ContractModel):
    name: str
    type: Literal["BOOL", "INT", "REAL", "TIME"] = "BOOL"
    description: str = ""


class PlanScope(ContractModel):
    standard: Literal["IEC 61131-3"]
    edition: str
    language: Literal["Structured Text"]
    runtime: str


class PlanObject(ContractModel):
    projectId: str
    domain: str = Field(min_length=1)
    agent: str
    generatedAt: str
    inputs: list[PlanSignal] = Field(min_length=1)
    outputs: list[PlanSignal]
    internalVars: list[InternalVar] = Field(default_factory=list)
    logicRules: list[str]
    safetyConstraints: list[str]
    scope: PlanScope
    llmProvider: str | None = None
    llmModel: str | None = None
    tokensUsed: int | None = None


class AgentMessage(ContractModel):
    id: str
    projectId: str
    agent: str
    role: Literal["input", "output", "system"]
    content: str
    createdAt: str


class WorkflowEvent(ContractModel):
    id: str
    projectId: str
    agent: str
    status: AgentStatus
    iteration: int
    inputSummary: str
    outputSummary: str
    durationMs: int
    createdAt: str


class CodeMetrics(ContractModel):
    loc: int
    cyclomaticComplexity: int
    maintainabilityIndex: int


class RAGSource(ContractModel):
    id: str
    name: str
    similarity: float | None = None
    domain: str | None = None
    patternType: str | None = None


class CodeMetadata(ContractModel):
    generator: str
    iecStandard: Literal["IEC 61131-3"]
    sourcePlanId: str
    createdAt: str
    iteration: int
    ragSources: list[RAGSource] = Field(default_factory=list)
    llmProvider: str | None = None
    llmModel: str | None = None
    generationMode: str | None = None
    tokensUsed: int | None = None
    generationTimeMs: int | None = None


class CodeArtifact(ContractModel):
    projectId: str
    artifactId: str
    language: Literal["structured-text"]
    filename: str
    source: str
    iteration: int
    generatedAt: str
    metrics: CodeMetrics
    metadata: CodeMetadata


class ValidationProperty(ContractModel):
    id: str
    description: str
    status: Literal["passed", "failed"]


class ValidationSafetyResult(ContractModel):
    id: str
    description: str
    status: Literal["passed", "failed"]
    details: str | None = None


class ValidationReport(ContractModel):
    projectId: str
    artifactId: str
    iteration: int
    status: ValidationStatus
    syntaxPassed: bool
    formalPassed: bool
    solver: str
    validator: str
    # Reports stored before D-033 have no level. They read as L0 because their compile may predate D-005.
    evidenceLevel: EvidenceLevel = "GENERATED"
    checkedAt: str
    summary: str
    syntaxErrors: list[str] = Field(default_factory=list)
    formalErrors: list[str] = Field(default_factory=list)
    safetyResults: list[ValidationSafetyResult] = Field(default_factory=list)
    properties: list[ValidationProperty]
    errors: list[str]
    counterexample: list[dict[str, bool | int | float | str]] | None = None
    counterexamples: list[dict[str, bool | int | float | str]] = Field(default_factory=list)


class DebuggingReport(ContractModel):
    projectId: str
    sourceArtifactId: str
    status: DebuggingStatus
    sourceValidationStatus: ValidationStatus
    errorType: str
    rootCause: str
    rootCauseSummary: str
    affectedCodeRegion: str
    patchAdvice: list[str]
    suggestedRegenerationPrompt: str
    counterexampleSummary: str | None = None
    createdAt: str
    debugger: str
    regeneratedArtifactId: str | None = None
    llmProvider: str | None = None
    llmModel: str | None = None
    tokensUsed: int | None = None


class OptimizationPass(ContractModel):
    name: str
    status: Literal["applied", "rolled_back"]
    locBefore: int
    locAfter: int
    ccBefore: int
    ccAfter: int


class StructuredTextMetrics(ContractModel):
    loc: int
    cyclomaticComplexity: int
    maintainabilityIndex: int
    estimatedScanTimeMs: float


class StructuredTextMetricsDelta(ContractModel):
    loc: int
    cyclomaticComplexity: int
    maintainabilityIndex: int
    estimatedScanTimeMs: float
    locReductionPercent: float
    cyclomaticReductionPercent: float
    maintainabilityGainPercent: float
    scanTimeReductionPercent: float


class MetricsReportDelta(ContractModel):
    locDelta: int
    cyclomaticComplexityDelta: int
    maintainabilityIndexDelta: int
    estimatedScanTimeDelta: float
    locReductionPercent: float
    complexityReductionPercent: float
    maintainabilityImprovementPercent: float
    scanTimeReductionPercent: float


class MetricsSource(ContractModel):
    selected: Literal["generated_code", "repaired_code", "optimized_code"]
    generatedCode: str | None = None
    repairedCode: str | None = None
    optimizedCode: str | None = None


class MetricsHistoryEntry(ContractModel):
    label: str
    source: Literal["generated_code", "repaired_code", "optimized_code"]
    artifactId: str
    metrics: StructuredTextMetrics
    createdAt: str


class OptimizationPassResult(ContractModel):
    name: str
    status: OptimizationPassStatus
    summary: str
    accepted: bool
    revalidationStatus: ValidationStatus
    beforeMetrics: StructuredTextMetrics
    afterMetrics: StructuredTextMetrics


class OptimizationRollbackEvent(ContractModel):
    passName: str
    reason: str
    revalidationStatus: ValidationStatus


class OptimizationReport(ContractModel):
    projectId: str
    sourceArtifactId: str
    optimizedArtifactId: str
    status: OptimizationStatus
    optimizer: str
    originalCode: CodeArtifact
    optimizedCode: CodeArtifact
    passes: list[OptimizationPassResult]
    beforeMetrics: StructuredTextMetrics
    afterMetrics: StructuredTextMetrics
    metricsDelta: StructuredTextMetricsDelta
    revalidationStatus: ValidationStatus
    rollbackEvents: list[OptimizationRollbackEvent]
    createdAt: str
    summary: str
    revalidated: bool


class MetricsReport(ContractModel):
    projectId: str
    source: MetricsSource
    beforeMetrics: StructuredTextMetrics
    afterMetrics: StructuredTextMetrics
    metricsDelta: MetricsReportDelta
    history: list[MetricsHistoryEntry]
    latestValidationStatus: ValidationStatus | None = None
    latestOptimizationStatus: OptimizationStatus | None = None
    createdAt: str
    summary: str


class BenchmarkCase(ContractModel):
    id: str
    name: str
    domain: str
    complexity: Literal["simple", "medium", "complex"]
    status: Literal["passed", "warning", "failed", "pending"]
    runtimeMs: float | None = None
    optimizationGainPercent: float | None = None


BenchmarkMode = Literal["rule_based", "llm", "llm_rag"]


class BenchmarkExpectedProperty(ContractModel):
    id: str
    description: str


class BenchmarkCaseCatalogItem(ContractModel):
    id: str = Field(validation_alias=AliasChoices("id", "caseId", "case_id"), serialization_alias="id")
    name: str = Field(validation_alias=AliasChoices("name", "caseName", "title"), serialization_alias="name")
    domain: str
    complexity: Literal["simple", "medium", "complex"] = Field(
        validation_alias=AliasChoices("complexity", "complexity_tier"),
        serialization_alias="complexity",
    )


class BenchmarkCaseDefinition(ContractModel):
    id: str = Field(validation_alias=AliasChoices("id", "case_id"), serialization_alias="id")
    name: str
    domain: str
    complexity: Literal["simple", "medium", "complex"] = Field(
        validation_alias=AliasChoices("complexity", "complexity_tier"),
        serialization_alias="complexity",
    )
    requirement: str
    expectedInputs: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("expectedInputs", "expected_inputs"),
        serialization_alias="expectedInputs",
    )
    expectedOutputs: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("expectedOutputs", "expected_outputs"),
        serialization_alias="expectedOutputs",
    )
    safetyConstraints: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("safetyConstraints", "safety_constraints"),
        serialization_alias="safetyConstraints",
    )
    expectedProperties: list[BenchmarkExpectedProperty] = Field(
        default_factory=list,
        validation_alias=AliasChoices("expectedProperties", "expected_properties"),
        serialization_alias="expectedProperties",
    )


class BenchmarkCaseResult(ContractModel):
    caseId: str
    mode: BenchmarkMode
    domain: str
    verified: bool
    validationStatus: ValidationStatus | None = None
    repairIterations: int
    generationTimeMs: int
    metrics: StructuredTextMetrics
    ragSourcesUsed: list[str] = Field(default_factory=list)
    llmProvider: str | None = None
    llmModel: str | None = None
    generatedCode: str
    error: str | None = None


class BenchmarkRunRequest(ContractModel):
    caseId: str
    mode: BenchmarkMode = "llm"


class BenchmarkCompareRequest(ContractModel):
    caseId: str


class BenchmarkComparisonDelta(ContractModel):
    locDelta: float
    ccDelta: float
    miDelta: float
    scanDelta: float
    repairIterations: int
    verified: bool | None = None


class BenchmarkComparison(ContractModel):
    llmVsBaseline: BenchmarkComparisonDelta
    ragVsLlm: BenchmarkComparisonDelta
    ragVsBaseline: BenchmarkComparisonDelta


class BenchmarkComparisonResult(ContractModel):
    caseId: str
    results: dict[BenchmarkMode, BenchmarkCaseResult | dict[str, str]]
    comparison: BenchmarkComparison


class BenchmarkSummaryModeStats(ContractModel):
    avgLoc: float
    avgCC: float
    verificationRate: float
    avgRepairIterations: float


class BenchmarkSummaryCaseResult(ContractModel):
    id: str
    name: str
    results: dict[str, BenchmarkCaseResult | dict[str, str]]


class BenchmarkSummaryResponse(ContractModel):
    totalRuns: int
    byMode: dict[BenchmarkMode, BenchmarkSummaryModeStats]
    bestMode: BenchmarkMode | Literal["none"]
    cases: list[BenchmarkSummaryCaseResult]


class FinalReport(ContractModel):
    projectId: str
    reportId: str
    generatedAt: str
    summary: str
    validation: ValidationReport | None = None
    optimization: OptimizationReport | None = None
    metrics: MetricsReport | None = None
    project: Project
    requirement: RequirementInput | None = None
    planObject: PlanObject | None = None
    codeArtifact: CodeArtifact | None = None
    debugging: DebuggingReport | None = None
    repairLoop: RepairLoopReport | None = None
    validationSummary: str
    debuggingSummary: str
    repairLoopSummary: str
    optimizationSummary: str
    metricsSummary: str
    finalStatusSummary: str
    recommendations: list[str] = Field(default_factory=list)
    limitationsDisclaimer: str


class RepairLoopReport(ContractModel):
    projectId: str
    finalStatus: RepairLoopFinalStatus
    iterations: int
    finalCodeArtifact: CodeArtifact
    finalValidationReport: ValidationReport
    debuggingReports: list[DebuggingReport]
    codeVersions: list[CodeArtifact]
    validationReports: list[ValidationReport]
    summary: str
