# OptPLC Backend

FastAPI backend for OptPLC. It exposes project workflow and benchmark APIs, persists pipeline state with async SQLAlchemy, runs LLM-assisted planning, code generation, debugging, and optimization, performs compiler-backed syntax checks with domain-aware structural safety validation, and produces metrics and final reports.

API base URL: `http://localhost:8000/api`

## Runtime Startup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

On startup, `app.main` creates database tables (local convenience) and seeds the RAG knowledge base from `knowledge_base/patterns/`. Verify readiness via `GET /api/health`.

## Configuration

Primary settings module: `app/config.py`. Environment variables are documented in the root `.env.example`.

| Group | Key variables |
| --- | --- |
| LLM routing | `LLM_PROVIDER` (`anthropic`, `openai`, `gemini`, `groq`, `ollama`) |
| Provider keys/models | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| LLM tuning | `LLM_MAX_TOKENS`, `LLM_TEMPERATURE` |
| Validation | `MATIEC_BIN`, `PLCVERIF_BIN`, `VERIFICATION_TIMEOUT_S` |
| Persistence | `DATABASE_URL` (default: `sqlite+aiosqlite:///./plcforge.db`) |
| Pipeline | `MAX_ITER` |

## Database and Migrations

| Component | Path |
| --- | --- |
| ORM models | `app/database/models.py` |
| Engine / session | `app/database/database.py` |
| Repository (CRUD) | `app/database/repository.py` |
| Migration config | `alembic.ini`, `alembic/versions/` |

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

`app.main` also runs `Base.metadata.create_all()` at startup for local convenience. Alembic remains the schema source of truth for controlled environments.

### Schema overview

- **`projects`** — project metadata (`id`, `name`, `domain`, `status`, `complexity_tier`, timestamps).
- **`sessions`** — one session per project; all pipeline state stored as JSON columns (`requirement_input`, `plan_object`, `code_artifact`, `validation_report`, `debugging_report`, `optimization_report`, `metrics_report`, `workflow_events`, etc.).

## Agent and Service Architecture

### Runtime modes in `ProjectService`

| Step | Agent | Mode |
| --- | --- | --- |
| Plan | `PlanningAgent` | `llm` |
| Generate | `CodeGenerationAgent` | `llm` |
| Validate | `ValidationAgent` | `static` |
| Debug | `DebuggingAgent` | `llm` |
| Optimize | `OptimizationAgent` | `llm` |

Mode selection is hardcoded in `app/services/project_service.py`. Each agent also supports deterministic fallback paths when LLM calls fail.

### Agent responsibilities

- **`PlanningAgent`** — requirement text → `PlanObject` (inputs, outputs, `internalVars`, logic rules, safety constraints). LLM path retrieves RAG context from domain patterns.
- **`CodeGenerationAgent`** — `PlanObject` (+ optional patch advice) → `CodeArtifact` (ST source, iteration, metadata). `rag_enabled` defaults to `false`; benchmark `llm_rag` mode sets it to `true`.
- **`ValidationAgent`** — `CodeArtifact` + `PlanObject` → `ValidationReport`.
- **`DebuggingAgent`** — failed validation context → `DebuggingReport` (patch advice, regeneration prompt).
- **`OptimizationAgent`** — verified/repaired artifact → `OptimizationReport` with pass outcomes, metrics deltas, and rollback events.

### LLM client

`app/agents/llm_client.py` provides unified async completion for Anthropic, OpenAI, Gemini (OpenAI-compatible endpoint), Groq (OpenAI-compatible endpoint), and Ollama.

### Orchestration services

| Service | Role |
| --- | --- |
| `project_service.py` | Main pipeline orchestrator (973 lines) |
| `repair_service.py` | Iterative repair loop coordination |
| `metrics_service.py` | LOC, cyclomatic complexity, maintainability index, estimated scan time |
| `validation_service.py` | MATIEC subprocess wrapper, PLCverif executor |
| `transpiler_service.py` | ST → SMV transpilation (scaffold for formal path) |
| `rag_service.py` | ChromaDB retrieval over knowledge-base patterns |
| `benchmark_runner.py` | Deterministic / LLM / RAG benchmark execution |

## RAG

Service: `app/services/rag_service.py`

| Aspect | Detail |
| --- | --- |
| Storage | ChromaDB persistent store at `/app/rag_db` (container path; local dev uses `./rag_db`) |
| Seed source | `knowledge_base/patterns/` (JSON pattern files) |
| Startup | `app.main` lifespan calls `get_rag_service().seed()` |
| Active in planning | `PlanningAgent` LLM path retrieves domain patterns as prompt context |
| Active in benchmarks | `llm_rag` mode sets `CodeGenerationAgent.rag_enabled = true` |
| Not active by default | Main `/generate` path does not enable `rag_enabled` on `CodeGenerationAgent` |

## Validation Stages

### Active runtime path (`ValidationAgent(mode="static")`)

1. **MATIEC syntax validation** — invoked when `MATIEC_BIN` points to an available `iec2c` binary; falls back to regex-based checks otherwise.
2. **Static structure checks** — Lark-based ST parser (`st_parser.py`) for supplemental analysis.
3. **Domain-aware safety rules** — structural checks for motor, traffic, tank, interlock, and batch domains.

### Implemented but not active in default pipeline (`mode="formal"`)

- ST → SMV transpilation via `transpiler_service.py`
- PLCverif execution via `validation_service.py` (`PLCVerifValidator`)
- nuXmv model checking (depends on real PLCverif / nuXmv binary provisioning)

`ProjectService` selects `mode="static"` for all `/validate` calls. The formal path exists in source for future integration.

## Artifact Contracts

Contracts are defined in `app/schemas/contracts.py` and mirrored in `src/lib/api-contracts/types.ts`. All fields use camelCase.

| Contract | Key fields |
| --- | --- |
| `RequirementInput` | `projectId`, `text`, `safetyConstraints`, `performanceTargets`, optional `confirmedOutputs` / `confirmedInputs` |
| `PlanObject` | `inputs`, `outputs`, `internalVars`, `logicRules`, `safetyConstraints`, `scope` |
| `CodeArtifact` | `artifactId`, `source` (ST code), `iteration`, `language`, `metadata` |
| `CodeMetadata` | `ragSources`, `llmProvider`, `llmModel`, `generationMode`, `tokensUsed`, `generationTimeMs` |
| `ValidationReport` | `status` (`VERIFIED` / `SYNTAX_ERROR` / `FORMAL_VIOLATION` / `TIMEOUT`), `syntaxErrors`, `formalErrors`, `safetyResults` |
| `DebuggingReport` | `patchAdvice`, `suggestedRegenerationPrompt`, root-cause summary |
| `OptimizationReport` | `passes`, metrics deltas, rollback events, revalidation status |
| `MetricsReport` | before/after metrics, historical timeline |
| `FinalReport` | aggregated project, requirements, plan, code, validation, debug, optimization, and metrics summaries |

## API Routes

Routers are mounted in `app.main` under `/api`.

### Health

- `GET /api/health`

### Projects

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/projects` | Create project |
| `GET` | `/api/projects` | List projects |
| `GET` | `/api/projects/{project_id}` | Get project with session state |
| `POST` | `/api/projects/{project_id}/requirements` | Submit requirements |
| `GET` | `/api/projects/{project_id}/requirements` | Get requirements |
| `POST` | `/api/projects/{project_id}/analyze-requirement` | Analyze requirement text |
| `POST` | `/api/projects/{project_id}/plan` | Generate plan |
| `GET` | `/api/projects/{project_id}/plan` | Get plan |
| `POST` | `/api/projects/{project_id}/generate` | Generate code |
| `GET` | `/api/projects/{project_id}/code` | Get latest code artifact |
| `POST` | `/api/projects/{project_id}/validate` | Validate code |
| `GET` | `/api/projects/{project_id}/validation` | Get validation report |
| `POST` | `/api/projects/{project_id}/debug` | Debug failed validation |
| `GET` | `/api/projects/{project_id}/debug` | Get debugging report |
| `POST` | `/api/projects/{project_id}/repair-loop` | Run repair loop |
| `POST` | `/api/projects/{project_id}/optimize` | Optimize code |
| `GET` | `/api/projects/{project_id}/optimization` | Get optimization report |
| `GET` | `/api/projects/{project_id}/metrics` | Get metrics report |
| `GET` | `/api/projects/{project_id}/report` | Get final report |
| `GET` | `/api/projects/{project_id}/report/export/json` | Export report as JSON |
| `GET` | `/api/projects/{project_id}/report/export/markdown` | Export report as Markdown |

### Benchmarks

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/benchmarks/cases` | List benchmark cases |
| `POST` | `/api/benchmarks/run` | Run single case |
| `POST` | `/api/benchmarks/compare` | Compare modes for a case |
| `POST` | `/api/benchmarks/run-suite` | Run full suite |
| `GET` | `/api/benchmarks/results` | List persisted results |
| `GET` | `/api/benchmarks/summary` | Aggregated summary |

## Benchmarks

Runner: `app/services/benchmark_runner.py`

| Mode | Description |
| --- | --- |
| `rule_based` | Deterministic agents (planning, codegen, debug, optimize) |
| `llm` | LLM agents without RAG on code generation |
| `llm_rag` | LLM agents with RAG enabled on code generation |

Cases are loaded from `benchmark/cases/` (B001–B005). Results are persisted as JSON under `benchmark/results/` (local, git-ignored).

```bash
curl -X POST http://localhost:8000/api/benchmarks/run-suite
```

## Tests and Quality Checks

```bash
cd backend
pytest
python -m compileall app
```

Test modules live in `app/tests/` and cover agents, API endpoints, database schema, benchmarks, and metrics.

## Docker

Compose file: `docker-compose.yml` (backend service only, container name `plcforge-app`).

```bash
docker compose up --build
```

Image build: `docker/app.Dockerfile`

- Builds MATIEC (`iec2c`) in a builder stage.
- Installs Python dependencies and runs `uvicorn`.
- Mounts `./rag_db` for ChromaDB persistence and `./backend/plcforge.db` for SQLite.
- PLCverif binary path is a placeholder; formal runtime availability depends on real binary provisioning.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| LLM provider key errors | Ensure the key for the selected `LLM_PROVIDER` is set in `backend/.env` |
| `MATIEC unavailable` in `/api/health` | Verify `MATIEC_BIN` path and executable permissions |
| `No RAG patterns loaded` in startup logs | Ensure `knowledge_base/patterns/` files are present and readable |
| `Project not found` on workflow routes | Complete prior pipeline steps in order (requirements → plan → generate → validate → …) |
| Formal validation not running | Default runtime uses `ValidationAgent(mode="static")`; formal flow is implemented but not wired into `ProjectService` |

## Security Notes

- Never commit `backend/.env` or API keys.
- Keep local database files (`plcforge.db`), vector-store artifacts (`rag_db/`), and benchmark result JSON out of version control.
- Rotate any credential immediately if accidentally committed.
