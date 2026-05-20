import type { CreateProjectRequest, Project, RequirementInput, WorkflowEvent } from "@/lib/api-contracts";
import { API_ENDPOINTS, projectEndpoint } from "@/lib/api-contracts";
import {
  currentProject,
  dashboardKpis,
  domainYield,
  planObject,
  projects,
  requirement,
  serviceStatus,
  settingsGroups,
  trendData
} from "@/lib/mock-data";

import { isMockApiEnabled } from "./config";
import { apiRequest } from "./fetch-transport";
import { cloneMock, mockResolve } from "./mock-transport";

export const ACTIVE_PROJECT_ID = currentProject.id;

export type ProjectRouteSegment =
  | "requirements"
  | "plan"
  | "workflow"
  | "code"
  | "validation"
  | "debugging"
  | "optimization"
  | "metrics"
  | "report";

export function projectPath(projectId: string, segment?: ProjectRouteSegment) {
  return segment ? `/projects/${projectId}/${segment}` : `/projects/${projectId}`;
}

export type DashboardPageData = {
  dashboardKpis: typeof dashboardKpis;
  trendData: typeof trendData;
  serviceStatus: typeof serviceStatus;
  projects: typeof projects;
  domainYield: typeof domainYield;
};

export type RequirementPageData = {
  requirement: typeof requirement;
  derivedPlan: typeof planObject;
};

export type SettingsPageData = {
  settingsGroups: typeof settingsGroups;
};

export type HealthResponse = {
  status: string;
  service: string;
  version: string;
  timestamp: string;
};

export async function createProject(request: CreateProjectRequest): Promise<Project> {
  if (!isMockApiEnabled()) {
    return apiRequest<Project, CreateProjectRequest>(API_ENDPOINTS.createProject, {
      method: "POST",
      body: request
    });
  }

  return mockResolve({
    id: ACTIVE_PROJECT_ID,
    name: request.name,
    description: request.description,
    domain: request.domain,
    standard: "IEC 61131-3",
    targetLanguage: "Structured Text",
    status: "draft",
    createdAt: currentProject.updated,
    updatedAt: currentProject.updated
  });
}

export async function getProjects(): Promise<Project[]> {
  if (!isMockApiEnabled()) {
    return apiRequest<Project[]>(API_ENDPOINTS.listProjects);
  }

  return mockResolve(
    projects.map((project) => ({
      id: project.id,
      name: project.name,
      description: `${project.domain} PLC optimization session`,
      domain: project.domain,
      standard: "IEC 61131-3",
      targetLanguage: "Structured Text",
      status: project.status === "failed" ? "failed" : project.status === "verified" ? "validated" : "optimized",
      createdAt: project.updated,
      updatedAt: project.updated
    }))
  );
}

export const listProjects = getProjects;

export async function getProject(projectId: string): Promise<Project> {
  if (!isMockApiEnabled()) {
    return apiRequest<Project>(projectEndpoint(API_ENDPOINTS.getProject, projectId));
  }

  const project = projects.find((item) => item.id === projectId) ?? projects[0];
  return mockResolve({
    id: projectId,
    name: project.name,
    description: `${project.domain} PLC optimization session`,
    domain: project.domain,
    standard: "IEC 61131-3",
    targetLanguage: "Structured Text",
    status: project.status === "failed" ? "failed" : project.status === "verified" ? "validated" : "optimized",
    createdAt: project.updated,
    updatedAt: project.updated
  });
}

export async function getDashboardData(): Promise<DashboardPageData> {
  if (!isMockApiEnabled()) {
    const apiProjects = await getProjects();
    return mockResolve({
      dashboardKpis,
      trendData,
      serviceStatus,
      projects: apiProjects.map(toProjectRow),
      domainYield
    });
  }

  return mockResolve({
    dashboardKpis,
    trendData,
    serviceStatus,
    projects,
    domainYield
  });
}

export async function getRequirementInput(projectId: string): Promise<RequirementInput> {
  return mockResolve({
    projectId,
    text: requirement.text,
    safetyConstraints: [...requirement.constraints],
    performanceTargets: {
      maxScanTimeMs: requirement.performanceTargets.scanTimeMs,
      maxCyclomaticComplexity: requirement.performanceTargets.cyclomaticComplexity,
      minMaintainabilityIndex: requirement.performanceTargets.maintainability,
      maxIterations: requirement.performanceTargets.maxIterations
    }
  });
}

export async function getRequirementPageData(projectId: string): Promise<RequirementPageData> {
  const derivedPlan = cloneMock(planObject);
  derivedPlan.projectId = projectId;
  return mockResolve({
    requirement,
    derivedPlan
  });
}

export async function submitRequirements(request: RequirementInput): Promise<WorkflowEvent> {
  if (!isMockApiEnabled()) {
    return apiRequest<WorkflowEvent, RequirementInput>(
      projectEndpoint(API_ENDPOINTS.submitRequirements, request.projectId),
      {
        method: "POST",
        body: request
      }
    );
  }

  return mockResolve({
    id: `${request.projectId}-wf-planning-1`,
    projectId: request.projectId,
    agent: "Planning Agent",
    status: "completed",
    iteration: 1,
    inputSummary: "Natural-language requirement accepted",
    outputSummary: "Requirement envelope stored; ready for Plan Object generation",
    durationMs: 4200,
    createdAt: "2026-05-17T09:42:18Z"
  });
}

export async function getProjectHistoryData() {
  if (!isMockApiEnabled()) {
    const apiProjects = await getProjects();
    return mockResolve({
      projects: apiProjects.map(toProjectRow)
    });
  }

  return mockResolve({
    projects
  });
}

export async function getSettingsData(): Promise<SettingsPageData> {
  return mockResolve({
    settingsGroups
  });
}

export async function getHealth(): Promise<HealthResponse> {
  if (!isMockApiEnabled()) {
    return apiRequest<HealthResponse>("/api/health");
  }

  return mockResolve({
    status: "mock",
    service: "frontend-mock-api",
    version: "local",
    timestamp: new Date("2026-05-17T09:42:18Z").toISOString()
  });
}

function toProjectRow(project: Project) {
  return {
    name: project.name,
    id: project.id,
    domain: project.domain,
    updated: project.updatedAt.slice(0, 10),
    iterations: project.status === "draft" ? 0 : 1,
    delta: project.status === "optimized" ? "-41.7%" : "-",
    status: project.status === "failed" ? "failed" : project.status === "optimized" ? "optimized" : "verified"
  };
}
