export type ProjectStatus = "draft" | "planned" | "generated" | "validated" | "optimized" | "failed";
export type AgentStatus = "pending" | "running" | "completed" | "failed";
export type SignalType = "BOOL" | "INT" | "REAL" | "TIME" | "STRING";

export interface Project {
  id: string;
  name: string;
  domain: string;
  description: string;
  standard: "IEC 61131-3";
  targetLanguage: "Structured Text";
  status: ProjectStatus;
  createdAt: string;
  updatedAt: string;
}

export interface CreateProjectRequest {
  name: string;
  description: string;
  domain: string;
  targetLanguage: "Structured Text";
  complexityTier: "simple" | "medium" | "complex";
}

export interface RequirementInput {
  projectId: string;
  text: string;
  safetyConstraints: string[];
  performanceTargets: {
    maxScanTimeMs: number;
    maxCyclomaticComplexity: number;
    minMaintainabilityIndex: number;
    maxIterations: number;
  };
  confirmedOutputs?: string[];
  confirmedInputs?: string[];
  domain?: string;
  complexityTier?: string;
}

export interface RequirementPayload {
  projectId: string;
  text: string;
  safetyConstraints: string[];
  confirmedOutputs?: string[];
  confirmedInputs?: string[];
  performanceTargets: {
    maxScanTimeMs: number;
    maxCyclomaticComplexity: number;
    minMaintainabilityIndex: number;
    maxIterations: number;
  };
  domain?: string | null;
  complexityTier?: string | null;
  submittedAt?: string | null;
  updatedAt?: string | null;
}

export interface AnalysisSignal {
  name: string;
  type: "BOOL" | "INT" | "REAL" | "TIME";
  source?: "Operator" | "Safety" | "Sensor" | "Timer";
  description?: string;
  confirmed?: boolean;
}

export interface AnalysisResult {
  domain: string;
  confidence: number;
  inferred_inputs: AnalysisSignal[];
  suggested_outputs: AnalysisSignal[];
  suggested_internals: AnalysisSignal[];
  safety_constraints: string[];
  suggested_constraints: string[];
  projectId?: string;
  analyzedAt?: string;
  source?: "llm" | "heuristic" | "empty";
}

export interface PlanSignal {
  name: string;
  type: SignalType;
  address?: string;
  source?: string;
  description: string;
}

export interface RAGSource {
  id: string;
  name: string;
  similarity?: number;
  domain?: string;
  patternType?: string;
}

export interface CodeMetadata {
  generator: string;
  iecStandard: "IEC 61131-3";
  sourcePlanId: string;
  createdAt: string;
  iteration: number;
  ragSources?: RAGSource[];
  llmProvider?: string;
  llmModel?: string;
  generationMode?: string;
  tokensUsed?: number;
  generationTimeMs?: number;
}

export interface PlanObject {
  projectId: string;
  agent: string;
  generatedAt: string;
  inputs: PlanSignal[];
  outputs: PlanSignal[];
  internalVars?: Array<{
    name: string;
    type: string;
    description: string;
  }>;
  logicRules: string[];
  safetyConstraints: string[];
  llmProvider?: string;
  llmModel?: string;
  tokensUsed?: number;
  scope: {
    standard: "IEC 61131-3";
    edition: string;
    language: "Structured Text";
    runtime: string;
  };
}

export interface AgentMessage {
  id: string;
  projectId: string;
  agent: string;
  role: "input" | "output" | "system";
  content: string;
  createdAt: string;
}

export interface WorkflowEvent {
  id: string;
  projectId: string;
  agent: string;
  status: AgentStatus;
  iteration: number;
  inputSummary: string;
  outputSummary: string;
  durationMs: number;
  createdAt: string;
}

export interface CodeArtifact {
  projectId: string;
  artifactId: string;
  language: "structured-text";
  filename: string;
  source: string;
  iteration: number;
  generatedAt: string;
  metrics: {
    loc: number;
    cyclomaticComplexity: number;
    maintainabilityIndex: number;
  };
  metadata: CodeMetadata;
}

export type ValidationStatus = "VERIFIED" | "SYNTAX_ERROR" | "FORMAL_VIOLATION" | "TIMEOUT";

export interface ValidationSafetyResult {
  id: string;
  description: string;
  status: "passed" | "failed";
  details?: string | null;
}

export interface ValidationReport {
  projectId: string;
  artifactId: string;
  iteration: number;
  status: ValidationStatus;
  syntaxPassed: boolean;
  formalPassed: boolean;
  solver: string;
  validator: string;
  checkedAt: string;
  summary: string;
  syntaxErrors: string[];
  formalErrors: string[];
  safetyResults: ValidationSafetyResult[];
  properties: ValidationSafetyResult[];
  errors: string[];
  counterexample?: Array<Record<string, boolean | number | string>>;
  counterexamples: Array<Record<string, boolean | number | string>>;
}

export interface DebuggingReport {
  projectId: string;
  sourceArtifactId: string;
  status: "NOT_REQUIRED" | "PATCH_ADVICE_GENERATED" | "CANNOT_DEBUG";
  sourceValidationStatus: ValidationStatus;
  errorType: string;
  rootCause: string;
  rootCauseSummary: string;
  affectedCodeRegion: string;
  patchAdvice: string[];
  suggestedRegenerationPrompt: string;
  counterexampleSummary?: string | null;
  createdAt: string;
  debugger: string;
  regeneratedArtifactId?: string;
  llmProvider?: string;
  llmModel?: string;
  tokensUsed?: number;
}

export type OptimizationStatus = "OPTIMIZED" | "NO_CHANGES" | "ROLLED_BACK" | "CANNOT_OPTIMIZE";
export type OptimizationPassStatus = "applied" | "rolled_back" | "no_changes";

export interface StructuredTextMetrics {
  loc: number;
  cyclomaticComplexity: number;
  maintainabilityIndex: number;
  estimatedScanTimeMs: number;
}

export interface StructuredTextMetricsDelta {
  loc: number;
  cyclomaticComplexity: number;
  maintainabilityIndex: number;
  estimatedScanTimeMs: number;
  locReductionPercent: number;
  cyclomaticReductionPercent: number;
  maintainabilityGainPercent: number;
  scanTimeReductionPercent: number;
}

export interface OptimizationPassResult {
  name: string;
  status: OptimizationPassStatus;
  summary: string;
  accepted: boolean;
  revalidationStatus: ValidationStatus;
  beforeMetrics: StructuredTextMetrics;
  afterMetrics: StructuredTextMetrics;
}

export interface OptimizationRollbackEvent {
  passName: string;
  reason: string;
  revalidationStatus: ValidationStatus;
}

export interface OptimizationReport {
  projectId: string;
  sourceArtifactId: string;
  optimizedArtifactId: string;
  status: OptimizationStatus;
  optimizer: string;
  originalCode: CodeArtifact;
  optimizedCode: CodeArtifact;
  passes: OptimizationPassResult[];
  beforeMetrics: StructuredTextMetrics;
  afterMetrics: StructuredTextMetrics;
  metricsDelta: StructuredTextMetricsDelta;
  revalidationStatus: ValidationStatus;
  rollbackEvents: OptimizationRollbackEvent[];
  createdAt: string;
  summary: string;
  revalidated: boolean;
}

export interface MetricsReport {
  projectId: string;
  source: {
    selected: "generated_code" | "repaired_code" | "optimized_code";
    generatedCode?: string | null;
    repairedCode?: string | null;
    optimizedCode?: string | null;
  };
  beforeMetrics: StructuredTextMetrics;
  afterMetrics: StructuredTextMetrics;
  metricsDelta: {
    locDelta: number;
    cyclomaticComplexityDelta: number;
    maintainabilityIndexDelta: number;
    estimatedScanTimeDelta: number;
    locReductionPercent: number;
    complexityReductionPercent: number;
    maintainabilityImprovementPercent: number;
    scanTimeReductionPercent: number;
  };
  history: Array<{
    label: string;
    source: "generated_code" | "repaired_code" | "optimized_code";
    artifactId: string;
    metrics: StructuredTextMetrics;
    createdAt: string;
  }>;
  latestValidationStatus?: ValidationStatus | null;
  latestOptimizationStatus?: OptimizationStatus | null;
  createdAt: string;
  summary: string;
}

export interface BenchmarkCase {
  id: string;
  name: string;
  domain: string;
  complexity: "simple" | "medium" | "complex";
  status: "passed" | "warning" | "failed" | "pending";
  runtimeMs?: number;
  optimizationGainPercent?: number;
}

export interface BenchmarkCaseDefinition {
  id: string;
  name: string;
  domain: string;
  complexity: "simple" | "medium" | "complex";
  requirement: string;
  safetyConstraints: string[];
  expectedInputs: string[];
  expectedOutputs: string[];
  expectedProperties: Array<{
    id: string;
    description: string;
  }>;
}

export interface BenchmarkCaseCatalogItem {
  id: string;
  name: string;
  domain: string;
  complexity: "simple" | "medium" | "complex";
  caseId?: string;
  case_id?: string;
  caseName?: string;
  title?: string;
}

export type BenchmarkMode = "rule_based" | "llm" | "llm_rag";

export interface BenchmarkCaseResult {
  caseId: string;
  mode: BenchmarkMode;
  domain: string;
  verified: boolean;
  validationStatus?: ValidationStatus | null;
  repairIterations: number;
  generationTimeMs: number;
  metrics: StructuredTextMetrics;
  ragSourcesUsed: string[];
  llmProvider?: string | null;
  llmModel?: string | null;
  generatedCode: string;
  error?: string | null;
}

export interface BenchmarkComparisonDelta {
  locDelta: number;
  ccDelta: number;
  miDelta: number;
  scanDelta: number;
  repairIterations: number;
  verified?: boolean | null;
}

export interface BenchmarkComparisonResult {
  caseId: string;
  results: Record<string, BenchmarkCaseResult | { error: string; mode?: string }>;
  comparison: {
    llmVsBaseline: BenchmarkComparisonDelta;
    ragVsLlm: BenchmarkComparisonDelta;
    ragVsBaseline: BenchmarkComparisonDelta;
  };
}

export interface BenchmarkSummaryResponse {
  totalRuns: number;
  byMode: Record<BenchmarkMode, {
    avgLoc: number;
    avgCC: number;
    verificationRate: number;
    avgRepairIterations: number;
  }>;
  bestMode: BenchmarkMode | "none";
  cases: Array<{
    id: string;
    name: string;
    results: Record<string, BenchmarkCaseResult | { error: string; mode?: string }>;
  }>;
}

export interface BenchmarkSuiteRunResponse {
  runId: string;
  completedAt: string;
  totalCases: number;
  totalRuns: number;
  cases: BenchmarkComparisonResult[];
  summary: BenchmarkSummaryResponse;
}

export interface FinalReport {
  projectId: string;
  reportId: string;
  generatedAt: string;
  summary: string;
  validation?: ValidationReport | null;
  optimization?: OptimizationReport | null;
  metrics?: MetricsReport | null;
  project: Project;
  requirement?: RequirementInput | null;
  planObject?: PlanObject | null;
  codeArtifact?: CodeArtifact | null;
  debugging?: DebuggingReport | null;
  repairLoop?: RepairLoopReport | null;
  validationSummary: string;
  debuggingSummary: string;
  repairLoopSummary: string;
  optimizationSummary: string;
  metricsSummary: string;
  finalStatusSummary: string;
  recommendations: string[];
  limitationsDisclaimer: string;
}

export interface RepairLoopReport {
  projectId: string;
  finalStatus: "VERIFIED" | "FAILED" | "ITERATION_LIMIT_REACHED";
  iterations: number;
  finalCodeArtifact: CodeArtifact;
  finalValidationReport: ValidationReport;
  debuggingReports: DebuggingReport[];
  codeVersions: CodeArtifact[];
  validationReports: ValidationReport[];
  summary: string;
}
