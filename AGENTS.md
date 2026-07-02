# AGENTS.md — OptPLC Project Context
## Multi-Agent AI System for IEC 61131-3 Structured Text

> **Read this file at the start of every prompt.**
> Every decision in this project must align with what is documented here.

---

## 1. Project Identity

| Field | Value |
|-------|-------|
| **Name** | OptPLC |
| **Full name** | OptPLC — AI Agent Optimizer for PLC Programs |
| **Purpose** | Multi-agent AI system that generates, validates, debugs, and optimizes IEC 61131-3 Structured Text (ST) code from natural language requirements |
| **Target users** | Industrial control engineers and system integrators |
| **Academic context** | Master's thesis — Peter the Great St. Petersburg Polytechnic University |
| **Target standard** | IEC 61131-3 Structured Text (ST) — CODESYS / TwinCAT compatible |

---

## 2. Architecture — Three Layers

```
┌──────────────────────────────────────────────────────────┐
│  Frontend  (Next.js 15 + TypeScript)                     │
│  9-step Pipeline UI — project-scoped routes              │
│  /projects/[id]/requirements → plan → code → ...        │
└──────────────────┬───────────────────────────────────────┘
                   │ REST API  (NEXT_PUBLIC_USE_MOCK_API=false)
┌──────────────────▼───────────────────────────────────────┐
│  Backend   (FastAPI + Python)                            │
│  ProjectService (973 lines) — orchestrates pipeline      │
│  5 Agents — each with rule_based (done) + llm (TODO)     │
│  Repository (231 lines) — async SQLAlchemy CRUD          │
└──────────────────┬───────────────────────────────────────┘
                   │ SQLAlchemy async
┌──────────────────▼───────────────────────────────────────┐
│  Database  (SQLite dev / PostgreSQL prod)                │
│  2 tables: projects + sessions                           │
│  All pipeline state stored as JSON in sessions table     │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack — Confirmed Versions

### Backend (`backend/requirements.txt`)
```
fastapi==0.136.1
uvicorn[standard]==0.47.0
anthropic==0.103.1          ← installed, NOT yet called
chromadb==0.6.3             ← installed, NOT yet used
sentence-transformers==3.4.1 ← installed, NOT yet used
lark-parser==0.12.0         ← used by st_parser.py
sqlalchemy[asyncio]==2.0.49
alembic==1.18.4
aiosqlite==0.22.1
pydantic-settings==2.14.1
httpx==0.28.1
slowapi==0.1.9
```

### Frontend (`package.json`)
```
Next.js 15.5.18
React 19
TypeScript 5
Tailwind CSS 3
shadcn/ui components
recharts (charts)
lucide-react (icons)
Monaco Editor (ST syntax highlighting)
Vitest (testing)
```

### Environment (`.env` / `.env.local`)
```bash
# Backend backend/.env
ANTHROPIC_API_KEY=          ← must be set for LLM mode
MATIEC_BIN=/usr/local/bin/iec2c
PLCVERIF_BIN=/usr/local/bin/plcverif
DATABASE_URL=sqlite+aiosqlite:///./plcforge.db
LLM_PROVIDER=anthropic
MAX_ITER=5

# Frontend .env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCK_API=false   ← real API mode (DO NOT change to true)
```

---

## 4. The 9-Step Pipeline

The entire product is organized as a sequential pipeline. Each step has a dedicated route, page component, and backend endpoint.

| Step | Route Segment | Page Component | Backend Endpoint |
|------|--------------|----------------|-----------------|
| 01 | `/requirements` | `requirements-page.tsx` | `POST /api/projects/:id/requirements` |
| 02 | `/plan` | `plan-page.tsx` | `POST /api/projects/:id/plan` |
| 03 | `/workflow` | `workflow-page.tsx` | `GET /api/projects/:id` |
| 04 | `/code` | `code-page.tsx` | `POST /api/projects/:id/generate` |
| 05 | `/validation` | `validation-page.tsx` | `POST /api/projects/:id/validate` |
| 06 | `/debugging` | `debugging-page.tsx` | `POST /api/projects/:id/debug` + `POST /api/projects/:id/repair-loop` |
| 07 | `/optimization` | `optimization-page.tsx` | `POST /api/projects/:id/optimize` |
| 08 | `/metrics` | `metrics-page.tsx` | `GET /api/projects/:id/metrics` |
| 09 | `/report` | `report-page.tsx` | `GET /api/projects/:id/report` |

**Navigation pattern:** All project pages use `/projects/[id]/[step]`
**Navigation between steps:** Each page has a CTA button that pushes to the next step using:
```typescript
router.push(projectPath(projectId, "plan"))  // after requirements
router.push(projectPath(projectId, "code"))  // after plan
// etc.
```

---

## 5. Database Schema

### Table: `projects`
| Column | Type | Notes |
|--------|------|-------|
| id | String(64) PK | Format: `PRJ-0001`, `PRJ-0002` (auto-incremented) |
| name | String(255) | Project display name |
| domain | String(120) | e.g. "Sequential Batch", "Motor Control" |
| description | Text | |
| standard | String(50) | Always "IEC 61131-3" |
| target_language | String(50) | Always "Structured Text" |
| complexity_tier | String(50) | "simple" / "medium" / "complex" |
| status | String(50) | "draft" → "planned" → ... → "optimized" |
| created_at / updated_at | DateTime(timezone=True) | |

### Table: `sessions`
One session per project. All pipeline state as JSON columns.

| Column | JSON Content |
|--------|-------------|
| `requirement_input` | Full `RequirementInput` contract |
| `plan_object` | Full `PlanObject` contract |
| `code_artifact` | Latest `CodeArtifact` |
| `code_artifact_history` | List of all `CodeArtifact` versions |
| `validation_report` | Latest `ValidationReport` |
| `validation_report_history` | All validation attempts |
| `debugging_report` | Latest `DebuggingReport` |
| `repair_loop_report` | Full `RepairLoopReport` |
| `optimization_report` | Latest `OptimizationReport` |
| `metrics_report` | `MetricsReport` |
| `metrics_before` / `metrics_after` | `StructuredTextMetrics` delta |
| `workflow_events` | List of `WorkflowEvent` for timeline |
| `messages_log` | Agent message history |

---

## 6. Agent System — The Core

### Current State vs Target State

| Agent | Current Mode | Current Status | Target Mode | What to Build |
|-------|-------------|----------------|-------------|---------------|
| PlanningAgent | `rule_based` | ✅ Works | `llm` | Replace `NotImplementedError` with Anthropic call |
| CodeGenerationAgent | `template_based` | ✅ Works | `llm` | Replace `NotImplementedError` with Anthropic call |
| ValidationAgent | `static` | ⚠️ Regex only | `formal` | Build MATIEC + PLCverif integration |
| DebuggingAgent | `rule_based` | ✅ Works | `llm` | Replace `NotImplementedError` with Anthropic call |
| OptimizationAgent | `static` | ✅ Works | `llm` | Replace `NotImplementedError` with Anthropic call |

### Exact Method Signatures (DO NOT CHANGE — project_service.py depends on these)

```python
# PlanningAgent
def generate_plan(self, *, project_id: str, requirement_text: str,
    safety_constraints: list[str] | None = None,
    performance_targets: PerformanceTargets | dict | None = None,
    confirmed_outputs: list[str] | None = None,
    domain: str = "", complexity_tier: str = "medium") -> PlanObject

# CodeGenerationAgent
def generate_code(self, *, project_id: str, plan: PlanObject,
    patch_advice: list[str] | None = None,
    suggested_regeneration_prompt: str | None = None,
    iteration: int = 1) -> CodeArtifact

# ValidationAgent
def validate(self, *, project_id: str, artifact: CodeArtifact,
    plan: PlanObject) -> ValidationReport

# DebuggingAgent
def debug(self, *, project_id: str, plan: PlanObject,
    artifact: CodeArtifact, validation: ValidationReport) -> DebuggingReport

# OptimizationAgent
def optimize(self, *, project_id: str, artifact: CodeArtifact,
    plan: PlanObject, validation: ValidationReport,
    repair_loop_report: RepairLoopReport | None = None) -> OptimizationReport
```

### How to Activate LLM Mode
Each agent has this pattern:
```python
class PlanningAgent:
    def __init__(self, mode: str = "rule_based") -> None:
        self.mode = mode

    def generate_plan(self, ...) -> PlanObject:
        if self.mode == "llm":
            raise NotImplementedError("...reserved for future integration...")
        # rule_based implementation below
```

**To activate LLM:** Replace `raise NotImplementedError(...)` with real Anthropic API call.
**To switch mode globally:** Change `project_service.py` calls from `mode="rule_based"` to `mode="llm"`.

---

## 7. Data Contracts — Critical Conventions

### Rule 1: camelCase in ALL Pydantic models
```python
# ✅ Correct
class Project(ContractModel):
    projectId: str
    createdAt: str
    planObject: PlanObject | None = None

# ❌ Wrong
class Project(ContractModel):
    project_id: str   # snake_case not allowed
```

### Rule 2: All contracts inherit from ContractModel
```python
class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")  # no unknown fields
```

### Rule 3: Literal types instead of Enum
```python
# ✅ Correct
ProjectStatus = Literal["draft", "planned", "generated", "validated", "optimized", "failed"]
AgentStatus = Literal["pending", "running", "completed", "failed"]
ValidationStatus = Literal["VERIFIED", "SYNTAX_ERROR", "FORMAL_VIOLATION", "TIMEOUT"]
```

### Key Contract Types
```python
PlanObject      → 7 inputs, 4 outputs, safety constraints, logic rules
CodeArtifact    → artifactId, source (ST code), iteration, language, metadata
ValidationReport → status: ValidationStatus, safetyResults, syntaxErrors
DebuggingReport  → patchAdvice: list[str], suggestedRegenerationPrompt: str
OptimizationReport → passes: list[OptimizationPass], metrics delta
MetricsReport   → loc, cyclomaticComplexity, maintainabilityIndex, estimatedScanTimeMs
```

---

## 8. Key Files Map

### Backend
```
backend/
├── app/
│   ├── config.py                    ← Pydantic Settings — reads .env
│   ├── main.py                      ← FastAPI app, CORS, router registration
│   ├── schemas/contracts.py         ← 433 lines — ALL data contracts
│   ├── database/
│   │   ├── database.py              ← engine, AsyncSessionLocal, get_db
│   │   ├── models.py                ← ProjectModel, SessionModel (ORM)
│   │   └── repository.py            ← 231 lines — async CRUD operations
│   ├── services/
│   │   ├── project_service.py       ← 973 lines — MAIN orchestrator
│   │   ├── repair_service.py        ← ⚠️ 95 lines — uses MemoryStore (needs migration to Repository)
│   │   ├── metrics_service.py       ← 160 lines — LOC, CC, MI, EST calculation
│   │   ├── st_parser.py             ← 305 lines — Lark-based AST parser for ST
│   │   ├── validation_service.py    ← 171 lines — MATIEC wrapper (subprocess)
│   │   └── benchmark_runner.py      ← 304 lines — benchmark execution
│   ├── agents/
│   │   ├── planning_agent.py        ← 421 lines — rule_based ✅ | llm TODO
│   │   ├── code_generation_agent.py ← 433 lines — template_based ✅ | llm TODO
│   │   ├── validation_agent.py      ← 444 lines — static ✅ | formal TODO
│   │   ├── debugging_agent.py       ← 316 lines — rule_based ✅ | llm TODO
│   │   └── optimization_agent.py    ← 339 lines — static ✅ | llm TODO
│   └── api/
│       ├── projects.py              ← 20+ endpoints for the full pipeline
│       ├── benchmarks.py            ← benchmark endpoints
│       └── health.py                ← GET /api/health
├── benchmark/cases/                 ← 4 JSON cases (B002-B005), B001 missing
└── alembic/                         ← migrations
    └── versions/20260520_0001_initial_schema.py
```

### Frontend
```
src/
├── app/
│   ├── projects/[id]/               ← project-scoped routes (USE THESE)
│   │   ├── requirements/page.tsx
│   │   ├── plan/page.tsx
│   │   ├── workflow/page.tsx
│   │   ├── code/page.tsx
│   │   ├── validation/page.tsx      ← currently empty (0 bytes)
│   │   ├── debugging/page.tsx
│   │   ├── optimization/page.tsx
│   │   ├── metrics/page.tsx
│   │   └── report/page.tsx
│   └── page.tsx                     ← root redirect
├── components/
│   ├── pages/                       ← 15 page components (main logic here)
│   ├── common/                      ← shared components
│   ├── layout/                      ← PageHeader, PipelineStrip
│   └── ui/                          ← shadcn components (card, table, tabs, etc.)
└── lib/
    ├── api-client/                  ← API functions (mock/real toggle)
    │   ├── config.ts                ← isMockApiEnabled()
    │   ├── project-client.ts        ← main API calls
    │   └── mock-transport.ts        ← mockResolve() for mock mode
    ├── api-contracts/
    │   ├── types.ts                 ← 358 lines TypeScript types
    │   └── endpoints.ts             ← 24 API endpoint constants
    └── mock-data.ts                 ← mock data (only used when MOCK=true)
```

---

## 9. What Is Working vs What Needs Building

### ✅ Working (Do NOT rewrite)
- Full 9-step pipeline UI with real data
- Database persistence (projects + sessions tables)
- All 20+ API endpoints in `api/projects.py`
- Repository CRUD operations
- All 5 agents in `rule_based/template_based/static` mode
- LLM Planning Agent (`PlanningAgent/llm.v1`)
- LLM Code Generation Agent (`CodeGenerationAgent/llm.v1`)
- LLM Optimization Agent (`OptimizationAgent/llm.v1`)
- Metrics Service (AST-based, real values)
- LLM Client with 4 providers (Anthropic/OpenAI/Gemini/Groq)
- Mock/Real API toggle system
- Benchmark runner structure (4 cases)
- `contracts.py` (433 lines, comprehensive)
- `st_parser.py` (Lark-based AST, 305 lines)
- Frontend-backend full connection

### 🔴 Needs Building (The AI Layer)
1. **Debugging Agent LLM** — still `rule_based.v1` (LLM mode not implemented yet)
2. **MATIEC subprocess** — `validation_service.py` exists but is not wired into full validation flow
3. **ST→SMV Transpiler** — `transpiler_service.py` is scaffolded only
4. **PLCverif formal verification** — not yet integrated
5. **RAG System** — ChromaDB is installed, but `rag_service.py` is not built
6. **repair_service.py migration** — move `MemoryStore` usage to `Repository` (SQLAlchemy)

---

## 10. Critical Rules — Always Follow

### Backend Rules

**RULE 1: Never change method signatures of agents**
`project_service.py` depends on exact signatures. Any change breaks the pipeline.

**RULE 2: All new code uses async/await**
All DB operations go through `AsyncSession`. No synchronous DB calls.

**RULE 3: Contracts use camelCase fields**
Every Pydantic model field is camelCase. `project_id` → `projectId`. No exceptions.

**RULE 4: Inherit from ContractModel**
Every new Pydantic model must inherit from `ContractModel(BaseModel)`.

**RULE 5: Read existing file before ANY modification**
Before editing any agent or service, read the full file first. Do not overwrite working code.

**RULE 6: LLM mode pattern**
When implementing LLM mode, follow this pattern exactly:
```python
if self.mode == "llm":
    return self._generate_with_llm(...)  # replace NotImplementedError with this
if self.mode != "rule_based":
    raise ValueError(f"Unsupported mode: {self.mode}")
# existing rule_based code remains untouched as fallback
```

**RULE 7: Anthropic API usage**
```python
from anthropic import AsyncAnthropic
from app.config import settings

client = AsyncAnthropic(api_key=settings.anthropic_api_key)
response = await client.messages.create(
    model="claude-sonnet-4-20250514",  # always this model
    max_tokens=2048,
    temperature=0.2,
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": user_content}]
)
```

### Frontend Rules

**RULE 8: Never remove mock mode**
`isMockApiEnabled()` must always work. Mock mode is essential for demos and testing without backend.

**RULE 9: Project-scoped routes only**
Always use `/projects/[id]/step` routes. The standalone routes (`/requirements`, `/validation`) are legacy.

**RULE 10: Table component names are short**
```typescript
// ✅ Correct — these are the ONLY exports from table.tsx
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table"
// ❌ Wrong — shadcn standard names are NOT used
import { TableHeader, TableRow, TableCell } from "@/components/ui/table"
```

**RULE 11: API prefix**
All backend endpoints are under `/api/`. Frontend calls `http://localhost:8000/api/projects/...`

---

## 11. ID Patterns
```
Projects:  PRJ-0001, PRJ-0002 ... (auto-incremented, zero-padded 4 digits)
Sessions:  one session per project (get_or_create pattern)
Artifacts: PRJ-0001-code-iter1, PRJ-0001-code-iter2 ...
Events:    PRJ-0001-wf-requirements-1, PRJ-0001-wf-plan-1 ...
```

---

## 12. How to Run

```bash
# Start Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Start Frontend  
npm run dev   # at project root

# Database migrations
cd backend && alembic upgrade head

# Run tests
cd backend && pytest
cd .. && npm run test
```

---

## 13. Next Steps — AI Layer Roadmap

Build in this exact order (each depends on the previous):

```
Step 1: Fix repair_service.py          → migrate MemoryStore to Repository
Step 2: Config-driven agent mode       → read llm_mode from settings
Step 3: LLM Client wrapper             → new file agents/llm_client.py
Step 4: LLM Planning Agent             → planning_agent.py mode="llm"
Step 5: LLM Code Generation Agent      → code_generation_agent.py mode="llm"
Step 6: MATIEC subprocess              → validation_service.py (real syntax check)
Step 7: ST-to-SMV Transpiler           → new file services/transpiler_service.py
Step 8: PLCverif integration           → validation_agent.py mode="formal"
Step 9: LLM Debugging Agent            → debugging_agent.py mode="llm"
Step 10: LLM Optimization Agent        → optimization_agent.py mode="llm"
Step 11: RAG Service                   → new file services/rag_service.py
Step 12: Knowledge Base content        → knowledge_base/ directory
```

---

*Last updated: May 2026 — based on full codebase audit of OptPLC v03*