# OptPLC Backend

FastAPI backend for OptPLC. It exposes project workflow and benchmark APIs, persists state with async SQLAlchemy, runs LLM-assisted planning/code/debug/optimization, performs compiler-backed syntax checks plus domain-aware structural safety checks, and produces metrics/final reports.

## Runtime Startup

PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Shell:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

API base URL: `http://localhost:8000/api`

## Configuration

Primary settings module: `backend/app/config.py`.

- LLM provider routing: `LLM_PROVIDER` (`anthropic`, `openai`, `gemini`, `groq`, `ollama`)
- Provider keys/models:
  - `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`
  - `OPENAI_API_KEY`, `OPENAI_MODEL`
  - `GEMINI_API_KEY`, `GEMINI_MODEL`
  - `GROQ_API_KEY`, `GROQ_MODEL`
  - `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- Validation:
  - `MATIEC_BIN`
  - `PLCVERIF_BIN`
  - `VERIFICATION_TIMEOUT_S`
- Persistence:
  - `DATABASE_URL`
- Pipeline controls:
  - `MAX_ITER`
  - `LLM_MAX_TOKENS`
  - `LLM_TEMPERATURE`

## Database and Migrations

- ORM models: `backend/app/database/models.py`
- Engine/session: `backend/app/database/database.py`
- Repository abstraction: `backend/app/database/repository.py`
- Migration tooling: `backend/alembic.ini` + `backend/alembic/versions/`

Commands:

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

Runtime note:

- `app.main` also runs `Base.metadata.create_all()` at startup for local convenience.
- Alembic remains the schema source of truth for controlled environments.

## Agent and Service Architecture

### Runtime agent modes in `ProjectService`

- Planning: `PlanningAgent(mode="llm")`
- Code generation: `CodeGenerationAgent(mode="llm")`
- Validation: `ValidationAgent(mode="static")`
- Debugging: `DebuggingAgent(mode="llm")`
- Optimization: `OptimizationAgent(mode="llm")`

### Agent responsibilities

- `PlanningAgent`: requirement -> `PlanObject` (with `internalVars` support).
- `CodeGenerationAgent`: plan (+ optional patch advice) -> `CodeArtifact`.
- `ValidationAgent`: code + plan -> `ValidationReport`.
- `DebuggingAgent`: failed validation context -> `DebuggingReport`.
- `OptimizationAgent`: verified/repaired artifact -> `OptimizationReport` + rollback metadata.

### LLM provider abstraction

`backend/app/agents/llm_client.py` provides unified async completion for:

- Anthropic
- OpenAI
- Gemini (OpenAI-compatible endpoint)
- Groq (OpenAI-compatible endpoint)
- Ollama

## RAG Initialization and Persistence

RAG service: `backend/app/services/rag_service.py`

- Storage: ChromaDB persistent store at `/app/rag_db` (container path).
- Seed source: `/app/knowledge_base/patterns`.
- Startup behavior: `app.main` lifespan calls `get_rag_service().seed()`.
- Active usage:
  - Planning LLM path (retrieval context included).
  - Benchmark mode `llm_rag` (code generation RAG enabled).
- Not active by default:
  - Main `/generate` path does not explicitly enable `CodeGenerationAgent.rag_enabled`.

## Validation Stages

### Active runtime path (`ValidationAgent(mode="static")`)

1. Optional MATIEC syntax validation (if binary is available).
2. Static syntax/structure checks (fallback or supplemental checks).
3. Domain-aware structural safety checks (motor, traffic, tank, interlock, batch).

This corresponds to compiler-backed syntax validation and domain-aware structural safety validation.

### Implemented but not active in default pipeline (`mode="formal"`)

- ST -> SMV transpilation (`transpiler_service.py`)
- PLCverif execution (`validation_service.py`, `PLCVerifValidator`)

The formal path exists in source but is not selected by `ProjectService` for normal `/validate`.

## API Routes

Routers are mounted in `app.main` under `/api`:

- Health:
  - `GET /api/health`
- Projects:
  - `POST /api/projects`
  - `GET /api/projects`
  - `GET /api/projects/{project_id}`
  - `POST /api/projects/{project_id}/requirements`
  - `GET /api/projects/{project_id}/requirements`
  - `POST /api/projects/{project_id}/analyze-requirement`
  - `POST /api/projects/{project_id}/plan`
  - `GET /api/projects/{project_id}/plan`
  - `POST /api/projects/{project_id}/generate`
  - `GET /api/projects/{project_id}/code`
  - `POST /api/projects/{project_id}/validate`
  - `GET /api/projects/{project_id}/validation`
  - `POST /api/projects/{project_id}/debug`
  - `GET /api/projects/{project_id}/debug`
  - `POST /api/projects/{project_id}/repair-loop`
  - `POST /api/projects/{project_id}/optimize`
  - `GET /api/projects/{project_id}/optimization`
  - `GET /api/projects/{project_id}/metrics`
  - `GET /api/projects/{project_id}/report`
  - `GET /api/projects/{project_id}/report/export/json`
  - `GET /api/projects/{project_id}/report/export/markdown`
- Benchmarks:
  - `GET /api/benchmarks/cases`
  - `POST /api/benchmarks/run`
  - `POST /api/benchmarks/compare`
  - `POST /api/benchmarks/run-suite`
  - `GET /api/benchmarks/results`
  - `GET /api/benchmarks/summary`

## Benchmarks

Benchmark runner: `backend/app/services/benchmark_runner.py`

- Supported modes: `rule_based`, `llm`, `llm_rag`
- Cases loaded from `backend/benchmark/cases/` (B001..B005)
- Output persisted as JSON under `backend/benchmark/results/`

Example:

```bash
curl -X POST http://localhost:8000/api/benchmarks/run-suite
```

## Tests and Quality Checks

Run backend checks:

```bash
cd backend
pytest
python -m compileall app
```

## Docker

Compose file: `docker-compose.yml` (backend service only)

```bash
docker compose up --build
```

Image build file: `docker/app.Dockerfile`

- Builds MATIEC (`iec2c`) in a builder stage.
- Installs Python dependencies and runs `uvicorn`.
- Includes a PLCverif placeholder executable path; formal runtime availability depends on real binary provisioning.

## Troubleshooting

- `LLM provider key errors`: ensure the key for selected `LLM_PROVIDER` is set.
- `MATIEC unavailable` in `/api/health`: verify `MATIEC_BIN` path and executable permissions.
- `No RAG patterns loaded`: ensure knowledge-base files are mounted/copied where the service expects them.
- `Project not found` / `artifact missing` on workflow routes: complete prior pipeline steps in order (`requirements -> plan -> generate -> validate ...`).
- `Formal validation expectations`: default runtime uses `ValidationAgent(mode="static")`; formal flow is implemented but not wired into main project orchestration.
