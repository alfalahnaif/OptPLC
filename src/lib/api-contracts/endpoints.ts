export const API_ENDPOINTS = {
  createProject: "/api/projects",
  listProjects: "/api/projects",
  getProject: "/api/projects/:id",
  getRequirements: "/api/projects/:id/requirements",
  submitRequirements: "/api/projects/:id/requirements",
  analyzeRequirement: "/api/projects/:id/analyze-requirement",
  createPlan: "/api/projects/:id/plan",
  getPlan: "/api/projects/:id/plan",
  generateCode: "/api/projects/:id/generate",
  getCode: "/api/projects/:id/code",
  validateCode: "/api/projects/:id/validate",
  getValidation: "/api/projects/:id/validation",
  debugCode: "/api/projects/:id/debug",
  getDebug: "/api/projects/:id/debug",
  repairLoop: "/api/projects/:id/repair-loop",
  optimizeCode: "/api/projects/:id/optimize",
  getOptimization: "/api/projects/:id/optimization",
  getMetrics: "/api/projects/:id/metrics",
  getReport: "/api/projects/:id/report",
  exportReportJson: "/api/projects/:id/report/export/json",
  exportReportMarkdown: "/api/projects/:id/report/export/markdown",
  getBenchmarkCases: "/api/benchmarks/cases",
  runBenchmarks: "/api/benchmarks/run",
  compareBenchmarks: "/api/benchmarks/compare",
  runBenchmarkSuite: "/api/benchmarks/run-suite",
  getBenchmarkResults: "/api/benchmarks/results",
  getBenchmarkSummary: "/api/benchmarks/summary"
} as const;

export type ApiEndpointKey = keyof typeof API_ENDPOINTS;

export function projectEndpoint(template: string, projectId: string) {
  return template.replace(":id", encodeURIComponent(projectId));
}
