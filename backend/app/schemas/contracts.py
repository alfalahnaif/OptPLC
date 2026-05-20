from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectStatus = Literal["draft", "planned", "generated", "validated", "optimized", "failed"]
AgentStatus = Literal["pending", "running", "completed", "failed"]
SignalType = Literal["BOOL", "INT", "REAL", "TIME", "STRING"]
ValidationStatus = Literal["VERIFIED", "SYNTAX_ERROR", "FORMAL_VIOLATION", "TIMEOUT"]
DebuggingStatus = Literal["NOT_REQUIRED", "PATCH_ADVICE_GENERATED", "CANNOT_DEBUG"]
RepairLoopFinalStatus = Literal["VERIFIED", "FAILED", "ITERATION_LIMIT_REACHED"]
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


class CreateProjectRequest(ContractModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    targetLanguage: Literal["Structured Text"]
    complexityTier: Literal["simple", "medium", "complex"]


class PerformanceTargets(ContractModel):
    maxScanTimeMs: float
    maxCyclomaticComplexity: int
    minMaintainabilityIndex: int
    maxIterations: int


class RequirementInput(ContractModel):
    projectId: str
    text: str = Field(min_length=1)
    safetyConstraints: list[str]
    performanceTargets: PerformanceTargets

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Requirement text must not be empty.")
        return value


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


class PlanScope(ContractModel):
    standard: Literal["IEC 61131-3"]
    edition: str
    language: Literal["Structured Text"]
    runtime: str


class PlanObject(ContractModel):
    projectId: str
    agent: str
    generatedAt: str
    inputs: list[PlanSignal] = Field(min_length=1)
    outputs: list[PlanSignal] = Field(min_length=1)
    logicRules: list[str]
    safetyConstraints: list[str]
    scope: PlanScope


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


class CodeMetadata(ContractModel):
    generator: str
    iecStandard: Literal["IEC 61131-3"]
    sourcePlanId: str
    createdAt: str
    iteration: int


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


class FinalReport(ContractModel):
    projectId: str
    reportId: str
    generatedAt: str
    summary: str
    validation: ValidationReport
    optimization: OptimizationReport
    metrics: MetricsReport


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
