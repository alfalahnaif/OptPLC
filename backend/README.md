# OptPLC Backend

FastAPI backend for OptPLC. It exposes project workflow and benchmark APIs, persists pipeline state with async SQLAlchemy, runs LLM-assisted planning, code generation, debugging and optimization, checks ST syntax with MATIEC plus heuristic domain rules, and produces metrics and final reports.

API base URL: `http://localhost:8000/api`

Plan, status and known issues: [`../docs/plan/`](../docs/plan/README.md). This file describes the code as it is.

## Runtime Startup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

On startup `app.main` runs `Base.metadata.create_all()` and seeds the RAG store from `knowledge_base/patterns/`. Check readiness with `GET /api/health`.

The reference runtime for reported results is the Docker image (see [Docker](#docker)); the local virtual environment can drift from it (for example `openai`).

## Configuration

Settings module: `app/config.py`, read from `backend/.env`. Variables are listed in the root `.env.example`.

| Group | Key variables |
| --- | --- |
| LLM routing | `LLM_PROVIDER` (`anthropic`, `openai`, `gemini`, `groq`, `ollama`; default `openai`) |
| Provider keys/models | `ANTHROPIC_*`, `OPENAI_*`, `GEMINI_*`, `GROQ_*`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| LLM tuning | `LLM_MAX_TOKENS`, `LLM_TEMPERATURE` |
| Validation | `MATIEC_BIN`, `PLCVERIF_BIN`, `VERIFICATION_TIMEOUT_S` |
| Persistence | `DATABASE_URL` (default `sqlite+aiosqlite:///./plcforge.db`) |
| Pipeline | `MAX_ITER` |

Startup fails if the key for the selected provider is missing (Anthropic, OpenAI, Gemini). Groq and Ollama are not checked at startup.

## Database and Migrations

| Component | Path |
| --- | --- |
| ORM models | `app/database/models.py` |
| Engine / session | `app/database/database.py` |
| Repository (CRUD) | `app/database/repository.py` |
| Migrations | `alembic.ini`, `alembic/versions/` |

```bash
cd backend
alembic upgrade head
```

The local development database was created by `create_all()`, not by Alembic (it has no `alembic_version` table). Back it up before any migration:

```powershell
backend\.venv\Scripts\python scripts\backup_runtime_data.py
```

Schema: `projects` (metadata) and `sessions` (one per project; all pipeline state as JSON columns).

## Agents and Runtime Modes

Modes are hard-coded in `app/services/project_service.py`.

| Step | Agent | Mode | Fallback / caveat |
| --- | --- | --- | --- |
| Plan | `PlanningAgent` | `llm` | Rule-based plan if the reply is not JSON after one retry |
| Generate | `CodeGenerationAgent` | `llm` | Template if the reply has no `PROGRAM` or misses a plan output; RAG off on `/generate` |
| Validate | `ValidationAgent` | `static` | See [Validation](#validation) |
| Debug | `DebuggingAgent` | `llm` | Rule-based advice on any LLM error |
| Optimize | `OptimizationAgent` | `llm` | Per-pass static revalidation and rollback; no behavioural-equivalence check |

Known template defects: the motor template never starts the motor (C-10), the batch template never sets `Batch_Complete` (C-11), and the `"Safety Interlock"` domain falls back to the generic template with undeclared variables (C-13). They are fixed in P1-22.

`app/agents/llm_client.py` provides one async `llm_complete()` for all providers. Agents must not call provider SDKs directly.

## RAG

`app/services/rag_service.py`: ChromaDB with the `all-MiniLM-L6-v2` embedding model (English only), 12 JSON patterns in `knowledge_base/patterns/`.

- Storage and pattern paths are hard-coded to `/app/rag_db` and `/app/knowledge_base/patterns`. On Windows this resolves to the current drive (for example `E:\app\...`), where no patterns exist, so retrieval returns nothing without an error. Fixed in P1-20.
- Used in planning (LLM mode) and in benchmark `llm_rag` mode; not used on `/generate`.
- Retrieval quality and its effect on results have not been measured yet.

## Validation

### Active path (`ValidationAgent(mode="static")`)

1. **Syntax.** If `MATIEC_BIN` exists, `iec2c -f -I <MATIEC_LIB_DIR> -T <temp dir>` compiles the source **exactly as written**, in a private temporary directory per request (P1-02, D-005, D-030). The old normalization step was removed because it hid real errors. Async callers use `ValidationAgent.validate_in_thread`, so a compile never blocks the server. If MATIEC is missing, the parser check `parser.v1` runs (`app/services/st_syntax_check.py`, P1-01): structural checks, a Lark parse of a documented ST subset, then undeclared variables and unknown calls. Passing it is not evidence level L1.
2. **Domain rules.** The first matching domain validator (batch, motor, traffic, process, interlock, generic) applies regex rules. These are text heuristics: an unsafe program can pass them.

The status `VERIFIED` means these static checks passed. It is not a proof.

### Not wired in (`mode="formal"`)

`transpiler_service.py` (ST→SMV) and `PLCVerifValidator` exist, but the transpiler drops `IF` blocks and produces no real LTL, and PLCverif output parsing fails open. Replaced in phase 3.

## Artifact Contracts

Contracts live in `app/schemas/contracts.py` and are mirrored in `src/lib/api-contracts/types.ts` (camelCase, `ContractModel` with `extra="forbid"`).

| Contract | Key fields |
| --- | --- |
| `RequirementInput` | `projectId`, `text`, `safetyConstraints`, `performanceTargets`, `confirmedOutputs`, `confirmedInputs` |
| `PlanObject` | `inputs`, `outputs`, `internalVars`, `logicRules`, `safetyConstraints`, `scope` |
| `CodeArtifact` | `artifactId`, `source`, `iteration`, `metrics`, `metadata` |
| `ValidationReport` | `status`, `syntaxErrors`, `formalErrors`, `safetyResults`, `counterexamples` |
| `DebuggingReport` | `patchAdvice`, `suggestedRegenerationPrompt`, `rootCauseSummary` |
| `OptimizationReport` | `passes`, `beforeMetrics`, `afterMetrics`, `rollbackEvents`, `revalidationStatus` |
| `MetricsReport` | before/after metrics and history (`estimatedScanTimeMs` is a static proxy, not milliseconds) |
| `FinalReport` | aggregated summaries of every step |

## API Routes

Routers are mounted under `/api`. There is no authentication or rate limiting yet (S-01).

### Health

- `GET /api/health` returns `status: "ok"`, MATIEC availability and path, the LLM provider, and a timestamp.

### Projects

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/projects` | Create project |
| `GET` | `/api/projects` | List projects |
| `GET` | `/api/projects/{project_id}` | Get project |
| `POST` | `/api/projects/{project_id}/requirements` | Submit requirements |
| `GET` | `/api/projects/{project_id}/requirements` | Get requirements (404 until submitted) |
| `POST` | `/api/projects/{project_id}/analyze-requirement` | LLM analysis of requirement text |
| `POST` | `/api/projects/{project_id}/plan` | Generate plan |
| `GET` | `/api/projects/{project_id}/plan` | Get plan |
| `POST` | `/api/projects/{project_id}/generate` | Generate code |
| `GET` | `/api/projects/{project_id}/code` | Get latest code artifact |
| `POST` | `/api/projects/{project_id}/validate` | Validate code |
| `GET` | `/api/projects/{project_id}/validation` | Get validation report |
| `POST` | `/api/projects/{project_id}/debug` | Debug the failed validation |
| `GET` | `/api/projects/{project_id}/debug` | Get debugging report |
| `POST` | `/api/projects/{project_id}/repair-loop` | Run the repair loop (up to 90 s in one request) |
| `POST` | `/api/projects/{project_id}/optimize` | Optimize verified code |
| `GET` | `/api/projects/{project_id}/optimization` | Get optimization report |
| `GET` | `/api/projects/{project_id}/metrics` | Compute and get the metrics report |
| `GET` | `/api/projects/{project_id}/report` | Get the final report |
| `GET` | `/api/projects/{project_id}/report/export/json` | Export report as JSON |
| `GET` | `/api/projects/{project_id}/report/export/markdown` | Export report as Markdown |

### Benchmarks

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/benchmarks/cases` | List benchmark cases |
| `POST` | `/api/benchmarks/run` | Run one case in one mode |
| `POST` | `/api/benchmarks/compare` | Run one case in all modes |
| `POST` | `/api/benchmarks/run-suite` | Run all cases (synchronously, in one request) |
| `GET` | `/api/benchmarks/results` | List stored results |
| `GET` | `/api/benchmarks/summary` | Aggregated summary |

## Benchmarks

Runner: `app/services/benchmark_runner.py`. Modes: `rule_based`, `llm`, `llm_rag`.

- Five cases, B001–B005, in `benchmark/cases/` (15 more are to be authored).
- Each case's `expected_properties` are not evaluated yet; "verified" in a result means the static checks passed.
- Results are written to `benchmark/results/` (git-ignored). No valid LLM results are stored yet.

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider
```

The suite is hermetic: `app/tests/conftest.py` binds settings to a temporary SQLite database before importing the app (and refuses to run otherwise), installs a fake LLM provider and a fake RAG service, sends benchmark results to a temporary directory, and blocks non-loopback network connections. `app/tests/known_failures.txt` lists the documented failing tests; run `scripts\check.ps1` from the repository root, which fails only on new failures. The current baseline is in [`../docs/plan/TEST_BASELINE.md`](../docs/plan/TEST_BASELINE.md).

## Docker

Reference image: `docker/app.Dockerfile`.

```bash
docker build -f docker/app.Dockerfile -t optplc-backend:p0-05 .
```

- Builds MATIEC (`iec2c`) from a pinned commit in a builder stage.
- Installs Python dependencies from the hashed lock `requirements-docker.lock` (compiled from `requirements-docker.in` with `uv pip compile --generate-hashes`; CPU-only PyTorch).
- Runs as the unprivileged user `optplc` (uid 10001) with a health check on `/api/health`.
- No PLCverif binary is installed.

Compile one ST file with the pinned MATIEC, without normalization:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\st-compile.ps1 -Path path\to\program.st
```

`docker-compose.yml` builds this image as `optplc-backend:local` (container `optplc-app`) with the database, the Chroma store, and the benchmark results mounted from the host. `docker compose up` replaces the older `plcforge-app` container (P0-13).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Startup error about an API key | Set the key for the selected `LLM_PROVIDER` in `backend/.env` |
| `matiec: unavailable` in `/api/health` | `MATIEC_BIN` must point to an executable `iec2c`; use the Docker image |
| A valid program fails with `Parser check (parser.v1) failed at line …` | MATIEC is missing and the program uses a construct outside the parser check's ST subset (P1-01); run in the Docker image with MATIEC |
| RAG returns nothing locally | Paths are hard-coded to `/app/...` (P1-20) |
| `Project not found` on workflow routes | Complete earlier steps first (requirements → plan → generate → validate …) |

## Security Notes

- Never commit `backend/.env` or API keys.
- Keep `plcforge.db`, `rag_db/`, and benchmark result JSON out of version control.
- The API has no authentication; do not expose it on an open network.
- Rotate any credential immediately if it is ever committed.
