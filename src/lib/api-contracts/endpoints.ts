export const API_ENDPOINTS = {
  createProject: "/api/projects",
  listProjects: "/api/projects",
  getProject: "/api/projects/:id",
  submitRequirements: "/api/projects/:id/requirements",
  createPlan: "/api/projects/:id/plan",
  generateCode: "/api/projects/:id/generate",
  validateCode: "/api/projects/:id/validate",
  debugCode: "/api/projects/:id/debug",
  repairLoop: "/api/projects/:id/repair-loop",
  optimizeCode: "/api/projects/:id/optimize",
  getMetrics: "/api/projects/:id/metrics",
  getReport: "/api/projects/:id/report",
  runBenchmarks: "/api/benchmarks/run"
} as const;

export type ApiEndpointKey = keyof typeof API_ENDPOINTS;

export function projectEndpoint(template: string, projectId: string) {
  return template.replace(":id", encodeURIComponent(projectId));
}
