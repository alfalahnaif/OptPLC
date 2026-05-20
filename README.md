# PLC Agent Optimizer

Production-readiness MVP for **OptPLC - PLC Agent Optimizer**. The app presents an industrial AI workflow that turns natural-language PLC control requirements into planned, generated, validated, debugged, optimized, and reported IEC 61131-3 Structured Text.

The frontend runs in mock mode by default, with an optional real API mode for the FastAPI endpoints that already exist. A FastAPI backend skeleton is available under `backend/` with in-memory storage for project creation, project lookup, requirement submission, a deterministic Planning Agent, a template-based Code Generation Agent, a static Validation Agent, a rule-based Debugging Agent, a deterministic repair loop, and a static Optimization Agent. Real LLM calls, external formal verification, metrics, benchmark, and final report generation are not implemented yet.

## Tech Stack

- Next.js App Router
- TypeScript
- TailwindCSS
- shadcn/ui conventions with Radix primitives
- lucide-react
- Recharts
- Monaco Editor with custom `structured-text` language registration
- Vitest + React Testing Library
- FastAPI backend skeleton with Pydantic schemas and pytest tests

## Implemented Pages

- Dashboard
- New Project
- Project Overview
- Requirement Input
- Plan Object Preview
- Agent Workflow Monitor
- Generated Structured Text Code
- Validation Results
- Debugging Feedback
- Optimization Results
- Metrics Comparison
- Final Report
- Benchmark Suite
- Project History
- Settings

## Routing

Global routes:

- `/` - dashboard
- `/new-project` - create a PLC project envelope
- `/history` - project history
- `/benchmark` - benchmark suite
- `/settings` - local frontend configuration

Project-scoped routes:

- `/projects/[id]`
- `/projects/[id]/requirements`
- `/projects/[id]/plan`
- `/projects/[id]/workflow`
- `/projects/[id]/code`
- `/projects/[id]/validation`
- `/projects/[id]/debugging`
- `/projects/[id]/optimization`
- `/projects/[id]/metrics`
- `/projects/[id]/report`

Legacy pipeline routes such as `/requirements`, `/plan`, `/workflow`, `/code`, `/validation`, `/debugging`, `/optimization`, `/metrics`, and `/report` are preserved as redirects to the active mock project route.

## API Client Layer

The frontend is prepared for backend integration through typed service modules:

- `src/lib/api-client/project-client.ts`
- `src/lib/api-client/workflow-client.ts`
- `src/lib/api-client/validation-client.ts`
- `src/lib/api-client/optimization-client.ts`
- `src/lib/api-client/report-client.ts`

These clients expose async functions whose signatures match the API contracts. They use mock data by default and switch to typed fetch calls when `NEXT_PUBLIC_USE_MOCK_API=false`.

## Run Locally

Frontend:

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

Backend:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/api/health`.

## API Mode

The frontend supports two API modes:

- Mock mode, the default: all frontend clients use centralized local mock data.
- Real API mode: implemented project endpoints call the FastAPI backend at `NEXT_PUBLIC_API_BASE_URL`.

Create `.env.local` from [.env.example](/E:/Projects/PLC_AI/.env.example):

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCK_API=true
```

To call the FastAPI backend for implemented endpoints:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCK_API=false
```

When real API mode is enabled, these frontend client functions call FastAPI:

- `getHealth()` -> `GET /api/health`
- `getProjects()` / `listProjects()` -> `GET /api/projects`
- `getProject(id)` -> `GET /api/projects/{id}`
- `createProject(request)` -> `POST /api/projects`
- `submitRequirements(request)` -> `POST /api/projects/{id}/requirements`
- `generatePlan(id)` / `createPlan(id)` -> `POST /api/projects/{id}/plan`
- `generateCode(id)` -> `POST /api/projects/{id}/generate`
- `validateCode(id)` -> `POST /api/projects/{id}/validate`
- `debugCode(id)` -> `POST /api/projects/{id}/debug`
- `runRepairLoop(id)` -> `POST /api/projects/{id}/repair-loop`
- `optimizeCode(id)` -> `POST /api/projects/{id}/optimize`

All other workflow clients remain mocked until backend endpoints are implemented.

## Real Planning Agent Flow

To test the real Planning Agent end to end:

1. Start the FastAPI backend:

```bash
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

2. Create `.env.local` in the project root:

```bash
NEXT_PUBLIC_USE_MOCK_API=false
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

3. Start the frontend:

```bash
npm run dev
```

4. Open `http://localhost:3000/new-project`, create a project, continue to Requirements, submit the requirement, and the app navigates to `/projects/{id}/plan`.

In real mode:

- New Project calls `POST /api/projects`.
- Requirement Input calls `POST /api/projects/{id}/requirements`.
- Plan Object Preview calls `POST /api/projects/{id}/plan`.
- The Plan page displays the `PlanObject` generated by the backend `PlanningAgent/rule_based.v1`.
- Requirement and Plan pages show `Real Backend Planning Agent`; mock mode shows `Mock Planning Mode`.

The Code page continues the flow:

- Click `Generate Code` on the Plan page to open `/projects/{id}/code`.
- In real mode, the Code page calls `POST /api/projects/{id}/generate`.
- The Code page displays backend-generated IEC 61131-3 Structured Text from `CodeGenerationAgent/template_based.v1`.
- The Code page shows `Real Template Code Generator`; mock mode shows `Mock Code Generator`.

The Validation page now continues the live backend path:

- Click `Run validation` on the Code page to open `/projects/{id}/validation`.
- In real mode, the Validation page calls `POST /api/projects/{id}/validate`.
- The backend `ValidationAgent/static.v1` checks Structured Text structure, declarations, assignments, block closure, unsupported language syntax, and domain-specific safety rules.
- The page displays `VERIFIED`, `SYNTAX_ERROR`, `FORMAL_VIOLATION`, or `TIMEOUT`, plus syntax errors, safety result rows, and counterexamples when present.
- The Validation page shows `Real Static Validator`; mock mode shows `Mock Validator`.
- If validation passes, the Validation page shows `Continue to Optimization`.
- If validation fails, the Validation page shows `Open Debugging Advice` and routes to `/projects/{id}/debugging`.

The Debugging page consumes the latest validation report:

- In real mode, the Debugging page calls `POST /api/projects/{id}/debug`.
- The backend `DebuggingAgent/rule_based.v1` returns `NOT_REQUIRED`, `PATCH_ADVICE_GENERATED`, or `CANNOT_DEBUG`.
- The page displays root cause summary, affected code region, patch advice, suggested regeneration prompt, and counterexample summary when present.
- The Debugging page shows `Real Rule-Based Debugger`; mock mode shows `Mock Debugger`.

The Repair Loop completes the first real repair cycle:

- Click `Run Repair Loop` on `/projects/{id}/debugging`.
- In real mode, the frontend calls `POST /api/projects/{id}/repair-loop`.
- The backend validates the current `CodeArtifact`, asks `DebuggingAgent/rule_based.v1` for patch advice when validation fails, regenerates ST through `CodeGenerationAgent/template_based.repair.v1`, and revalidates.
- The loop stops when validation returns `VERIFIED`, when no actionable debugging advice exists, or when `MAX_ITER=5` is reached.
- `RepairLoopPanel` displays final status, validation attempts, code versions, debugging advice used, and the final validation result.
- Code, Validation, and Workflow pages can display the latest repair-loop report while the frontend session keeps it cached.

The Optimization page now connects to the backend optimizer:

- In real mode, `/projects/{id}/optimization` calls `POST /api/projects/{id}/optimize`.
- Optimization only runs when a `PlanObject`, `CodeArtifact`, and latest `ValidationReport` exist and the validation status is `VERIFIED`.
- The backend `OptimizationAgent/static.v1` applies three deterministic passes: Structural Simplification, Logic Compaction, and Maintainability Enhancement.
- Each candidate pass is revalidated with `ValidationAgent/static.v1`; failed candidates are rolled back and recorded as rollback events.
- The page displays `OPTIMIZED`, `NO_CHANGES`, `ROLLED_BACK`, or `CANNOT_OPTIMIZE`, plus before/after metrics, pass results, rollback events, and optimized Structured Text.
- The Optimization page shows `Real Static Optimizer`; mock mode shows `Mock Optimizer`.

## Quality Commands

Frontend:

```bash
npm run typecheck
npm run lint
npm run test
npm run test:watch
npm run build
```

Backend:

```bash
cd backend
pytest
python -m compileall app
```

## Project Structure

```text
backend/                         FastAPI backend skeleton
backend/app/api/                 Health and project routers
backend/app/schemas/             Pydantic API contract schemas
backend/app/services/            Project service layer and repair loop orchestration
backend/app/agents/              Rule-based Planning, template Code Generation, static Validation, Debugging, and Optimization agents
backend/app/storage/             In-memory storage
backend/app/tests/               Pytest endpoint tests
src/app/                         Next.js routes, redirects, and global layout
src/app/projects/[id]/           Project-scoped workflow routes
src/components/ui/               shadcn-style reusable primitives
src/components/common/           Product-level reusable components and states
src/components/layout/           App shell, page header, pipeline strip
src/components/pages/            Page-level UI composition
src/lib/mock-data.ts             Centralized PLC and agent mock data
src/lib/api-client/              Mock/real API client layer with typed fetch transport
src/lib/api-contracts/           Future backend TypeScript contracts
src/lib/monaco-structured-text.ts Monaco IEC ST language support
src/test/                        Vitest setup and browser API shims
```

## Frontend-Only Status

Current behavior is intentionally local and deterministic:

- Frontend API client functions return mock data by default.
- Real API mode connects health, projects, requirements submission, Plan Object creation, code generation, static validation, debugging advice, repair loop, and optimization.
- Backend project endpoints use in-memory storage; `/plan` uses the rule-based Planning Agent, `/generate` uses the template Code Generation Agent, `/validate` uses the static Validation Agent, `/debug` uses the rule-based Debugging Agent, `/repair-loop` orchestrates validation, debugging, regeneration, and revalidation, and `/optimize` runs the static Optimization Agent with rollback-on-regression.
- Dynamic routes pass `projectId` into page components, but mock responses resolve to the active sample project.
- Buttons such as export, run, copy, and retry are UI placeholders.
- Loading, empty, and error states are simulated through local component state and mock client behavior.
- The Monaco editor is client-only to avoid SSR issues.

## Test Coverage

The Vitest suite covers the app shell, major workflow pages, dynamic project routes, project ID propagation, and mock API client responses.

## Known Limitations

- No persistence, authentication, authorization, or real project workspace data.
- No LLM, RAG, external formal solver, metrics, benchmark, or report-generation service calls.
- Metrics, report, and benchmark frontend clients remain mocked.
- Backend storage is process-local and resets on restart.
- Repair-loop results are persisted only in process memory on the backend and cached only for the current frontend session.
- Monaco highlighting is a focused IEC Structured Text tokenizer, not a full language server.
- Export/download/copy actions are not wired to browser file APIs yet.
- `npm audit` previously reported moderate dependency-tree vulnerabilities; review dependency upgrades before using forced audit fixes.

## Backend Integration Plan

1. Add persistent storage and project authorization to the backend.
2. Persist project, requirement, plan, code, validation, debugging, and repair-loop records beyond process memory.
3. Implement metrics, report, and benchmark endpoints.
4. Replace remaining mocked workflow clients with real API calls endpoint by endpoint.
5. Add contract tests against the FastAPI OpenAPI schema and integration tests for the full project flow.
6. Replace `ValidationAgent(mode="static")` with external MATIEC/nuXmv/PLCverif adapters behind the reserved formal mode when those tools are available.
7. Add future LLM/RAG implementations behind the existing placeholder agent modes.
