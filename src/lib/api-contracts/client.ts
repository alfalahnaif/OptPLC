import type {
  BenchmarkCase,
  CodeArtifact,
  CreateProjectRequest,
  DebuggingReport,
  FinalReport,
  MetricsReport,
  OptimizationReport,
  PlanObject,
  Project,
  RepairLoopReport,
  RequirementInput,
  ValidationReport,
  WorkflowEvent
} from "./types";

function notImplemented<T>(operation: string): Promise<T> {
  return Promise.reject(new Error(`${operation} is an API contract placeholder and is not wired to a backend yet.`));
}

export const apiClient = {
  createProject(_request: CreateProjectRequest): Promise<Project> {
    void _request;
    return notImplemented("createProject");
  },
  listProjects(): Promise<Project[]> {
    return notImplemented("listProjects");
  },
  getProject(_projectId: string): Promise<Project> {
    void _projectId;
    return notImplemented("getProject");
  },
  submitRequirements(_request: RequirementInput): Promise<WorkflowEvent> {
    void _request;
    return notImplemented("submitRequirements");
  },
  createPlan(_projectId: string): Promise<PlanObject> {
    void _projectId;
    return notImplemented("createPlan");
  },
  generateCode(_projectId: string): Promise<CodeArtifact> {
    void _projectId;
    return notImplemented("generateCode");
  },
  validateCode(_projectId: string): Promise<ValidationReport> {
    void _projectId;
    return notImplemented("validateCode");
  },
  debugCode(_projectId: string): Promise<DebuggingReport> {
    void _projectId;
    return notImplemented("debugCode");
  },
  runRepairLoop(_projectId: string): Promise<RepairLoopReport> {
    void _projectId;
    return notImplemented("runRepairLoop");
  },
  optimizeCode(_projectId: string): Promise<OptimizationReport> {
    void _projectId;
    return notImplemented("optimizeCode");
  },
  getMetrics(_projectId: string): Promise<MetricsReport> {
    void _projectId;
    return notImplemented("getMetrics");
  },
  getReport(_projectId: string): Promise<FinalReport> {
    void _projectId;
    return notImplemented("getReport");
  },
  runBenchmarks(): Promise<BenchmarkCase[]> {
    return notImplemented("runBenchmarks");
  }
};
