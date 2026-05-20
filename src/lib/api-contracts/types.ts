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
}

export interface PlanSignal {
  name: string;
  type: SignalType;
  address?: string;
  source?: string;
  description: string;
}

export interface PlanObject {
  projectId: string;
  agent: string;
  generatedAt: string;
  inputs: PlanSignal[];
  outputs: PlanSignal[];
  logicRules: string[];
  safetyConstraints: string[];
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
  metadata: {
    generator: string;
    iecStandard: "IEC 61131-3";
    sourcePlanId: string;
    createdAt: string;
    iteration: number;
  };
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

export interface FinalReport {
  projectId: string;
  reportId: string;
  generatedAt: string;
  summary: string;
  validation: ValidationReport;
  optimization: OptimizationReport;
  metrics: MetricsReport;
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
