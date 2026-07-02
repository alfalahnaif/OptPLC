# OptPLC

OptPLC is a research prototype for generating, validating, repairing, optimizing, and evaluating IEC 61131-3 Structured Text (ST) programs from natural-language industrial control requirements. The repository includes a Next.js frontend, a FastAPI backend, SQLAlchemy persistence, LLM-assisted pipeline agents, compiler-backed syntax validation plus domain-aware structural safety validation, and a benchmark runner for deterministic/LLM/RAG comparisons.

## Naming Consistency Note

The canonical product name in runtime UI/backend metadata is `OptPLC`. The repository still contains legacy identifiers such as `plc-agent-optimizer` (package name) and `plcforge` (DB file names, report export filenames, and container name). This README keeps `OptPLC` as the project name and calls out legacy names where needed.

## Current Implementation Status


| Component                         | Status      | Description                                                                                                                                                |
| --------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Project creation and persistence  | Implemented | `POST /api/projects` + SQLAlchemy `projects`/`sessions` persistence.                                                                                       |
| Requirement analysis              | Implemented | `POST /api/projects/{id}/analyze-requirement` is available and used by frontend requirements preview.                                                      |
| PlanObject generation             | Implemented | `PlanningAgent(mode="llm")` is used in runtime for `/plan`.                                                                                                |
| `PlanObject.internalVars` support | Implemented | Field exists in backend/TS contracts and is produced by planning logic.                                                                                    |
| Code generation                   | Implemented | `CodeGenerationAgent(mode="llm")` is used in runtime for `/generate`.                                                                                      |
| LLM provider abstraction          | Implemented | Unified LLM client supports Anthropic, OpenAI, Gemini, Groq, Ollama via `LLM_PROVIDER`.                                                                    |
| RAG retrieval                     | Partial     | RAG service is implemented and seeded at app startup; active in planning and benchmark `llm_rag`, but not enabled in default runtime code generation path. |
| MATIEC validation                 | Implemented | Static validation path runs optional MATIEC syntax checking when `MATIEC_BIN` is available.                                                                |
| Domain-aware safety validation    | Implemented | Static validators enforce domain safety checks and return structured safety results.                                                                       |
| Debugging / repair loop           | Implemented | LLM debugging + iterative regeneration/revalidation loop is active via `/debug` and `/repair-loop`.                                                        |
| Optimization passes               | Implemented | LLM optimization flow runs passes and revalidates outcomes.                                                                                                |
| Rollback and revalidation         | Implemented | Optimization performs post-pass validation and rollback event tracking.                                                                                    |
| Metrics                           | Implemented | Metrics endpoint computes LOC/CC/MI/estimated scan-time deltas and history.                                                                                |
| Benchmark runner                  | Implemented | `/api/benchmarks/*` supports case run, mode compare, full suite, persisted result summaries.                                                               |
| Final report                      | Implemented | `GET /api/projects/{id}/report` and JSON/Markdown export endpoints are active.                                                                             |
| nuXmv / PLCverif integration      | Partial     | PLCverif path exists in `ValidationAgent(mode="formal")`, but formal mode is not wired into the main project runtime pipeline.                             |




## Architecture

```mermaid
flowchart TD
    A[Natural-language requirement] --> B[Requirement analysis + persistence]
    B --> C[Planning Agent -> PlanObject]
    C --> D[Optional RAG retrieval context]
    D --> E[Code Generation Agent -> CodeArtifact]
    E --> F[Validation Agent]
    F -->|VERIFIED| G[Optimization Agent]
    F -->|Not verified| H[Debugging Agent]
    H --> I[Repair loop regeneration]
    I --> F
    G --> J[Revalidation + rollback checks]
    J --> K[Metrics report]
    K --> L[Final report + exports]
```





## Agent Responsibilities


| Agent                 | Input                                                   | Output               | Execution mode                  | Type                                                             |
| --------------------- | ------------------------------------------------------- | -------------------- | ------------------------------- | ---------------------------------------------------------------- |
| Planning Agent        | `projectId`, requirement text, constraints/targets      | `PlanObject`         | Runtime: `llm` (`/plan`)        | Hybrid (LLM + deterministic fallback)                            |
| Code Generation Agent | `PlanObject`, optional patch advice                     | `CodeArtifact`       | Runtime: `llm` (`/generate`)    | Hybrid (LLM + structured templates/fallback)                     |
| Validation Agent      | `CodeArtifact` + `PlanObject`                           | `ValidationReport`   | Runtime: `static` (`/validate`) | Deterministic (compiler-backed syntax + structural safety rules) |
| Debugging Agent       | `PlanObject`, `CodeArtifact`, `ValidationReport`        | `DebuggingReport`    | Runtime: `llm` (`/debug`)       | Hybrid                                                           |
| Optimization Agent    | artifact + plan + validation (+ optional repair report) | `OptimizationReport` | Runtime: `llm` (`/optimize`)    | Hybrid with revalidation guards                                  |




## Artifact Contracts

Implemented contracts are defined in `backend/app/schemas/contracts.py` and mirrored in `src/lib/api-contracts/types.ts`.

- `RequirementInput`: `projectId`, `text`, `safetyConstraints`, `performanceTargets`, optional `confirmedOutputs`/`confirmedInputs`.
- `PlanObject`: `inputs`, `outputs`, `internalVars`, `logicRules`, `safetyConstraints`, `scope`.
- `PlanObject.internalVars`: typed internal declarations (`BOOL`/`INT`/`REAL`/`TIME`) used for generated ST structure.
- `CodeArtifact`: source ST, iteration, metrics, and metadata.
- `CodeMetadata`: includes implemented metadata fields `ragSources`, `llmProvider`, `llmModel`, `generationMode`, `tokensUsed`, `generationTimeMs`.
- `RAGSource`: retrieval provenance (`id`, `name`, optional `similarity`, `domain`, `patternType`).
- `ValidationReport`: status (`VERIFIED`/`SYNTAX_ERROR`/`FORMAL_VIOLATION`/`TIMEOUT`), syntax/formal errors, safety results, counterexamples.
- `DebuggingReport`: root-cause summary, patch advice, regeneration prompt, optional LLM usage metadata.
- `OptimizationReport`: optimization pass outcomes, metrics deltas, rollback events, revalidation status.
- `MetricsReport`: before/after metrics and historical metric timeline.
- `FinalReport`: aggregated project, requirements, plan, code, validation/debug/optimization/metrics summaries and recommendations.



## Technology Stack

- Python: `3.11` (Docker image), local environment configurable.
- FastAPI: `0.136.1`
- SQLAlchemy (async): `2.0.49`
- Pydantic settings: `2.14.1`
- LLM providers: Anthropic/OpenAI/Gemini/Groq/Ollama via provider abstraction.
- Next.js: `^15.0.0`
- TypeScript: `^5.7.2`
- ChromaDB: `0.6.3`
- sentence-transformers: `3.4.1`
- MATIEC: `iec2c` invoked from configured binary path.
- Docker: `docker/app.Dockerfile` + `docker-compose.yml` (backend service).



## Repository Structure

```text
backend/
  app/
    api/                # FastAPI routers: health, projects, benchmarks
    agents/             # Planning/codegen/validation/debug/optimization + llm client
    services/           # Orchestration, metrics, validation backends, RAG, benchmark runner
    schemas/            # Pydantic contracts
    database/           # SQLAlchemy engine/models/repository
  benchmark/cases/      # Benchmark case definitions (B001..B005)
  benchmark/results/    # Persisted benchmark run outputs
src/
  app/                  # Next.js routes (project-scoped workflow pages)
  components/pages/     # Workflow and system pages
  lib/api-client/       # Real/mock transport and API clients
  lib/api-contracts/    # Frontend contract types and endpoint constants
docker/
  app.Dockerfile
docker-compose.yml
```



## Local Development



### Backend

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



### Frontend

PowerShell:

```powershell
npm install
npm run dev
```

Shell:

```bash
npm install
npm run dev
```



### Docker Compose (backend service)

```bash
docker compose up --build
```



## Repository Structure

```text

OptPLC/

├── [README.md](http://README.md)

├── [AGENTS.md](http://AGENTS.md)

├── .env.example

├── docker-compose.yml

├── docker/

│   └── app.Dockerfile

│

├── backend/

│   ├── [README.md](http://README.md)

│   ├── alembic.ini

│   ├── alembic/

│   │   ├── [env.py](http://env.py)

│   │   └── versions/

│   │

│   ├── app/

│   │   ├── agents/

│   │   │   ├── planning_[agent.py](http://agent.py)

│   │   │   ├── code_generation_[agent.py](http://agent.py)

│   │   │   ├── validation_[agent.py](http://agent.py)

│   │   │   ├── debugging_[agent.py](http://agent.py)

│   │   │   ├── optimization_[agent.py](http://agent.py)

│   │   │   └── llm_[client.py](http://client.py)

│   │   │

│   │   ├── api/

│   │   │   ├── [projects.py](http://projects.py)

│   │   │   ├── [benchmarks.py](http://benchmarks.py)

│   │   │   └── [health.py](http://health.py)

│   │   │

│   │   ├── database/

│   │   ├── schemas/

│   │   │   └── [contracts.py](http://contracts.py)

│   │   │

│   │   ├── services/

│   │   │   ├── project_[service.py](http://service.py)

│   │   │   ├── rag_[service.py](http://service.py)

│   │   │   ├── validation_[service.py](http://service.py)

│   │   │   ├── repair_[service.py](http://service.py)

│   │   │   ├── metrics_[service.py](http://service.py)

│   │   │   ├── benchmark_[runner.py](http://runner.py)

│   │   │   └── transpiler_[service.py](http://service.py)

│   │   │

│   │   ├── storage/

│   │   └── [main.py](http://main.py)

│   │

│   ├── benchmark/

│   │   ├── cases/

│   │   └── results/          # Generated locally and ignored by Git

│   │

│   ├── knowledge_base/

│   │   └── patterns/

│   │

│   ├── tests/

│   └── requirements.txt

│

├── src/

│   ├── components/

│   │   ├── common/

│   │   ├── layout/

│   │   ├── pages/

│   │   └── ui/

│   │

│   ├── lib/

│   │   ├── api-client/

│   │   └── api-contracts/

│   │

│   └── test/

│

├── package.json

├── package-lock.json

└── tsconfig.json



## Environment Variables

Variables are documented in `.env.example`. Do not commit real secrets.

- Application:
  - `MAX_ITER`
- Database:
  - `DATABASE_URL`
- LLM:
  - `LLM_PROVIDER`
  - `LLM_MAX_TOKENS`
  - `LLM_TEMPERATURE`
  - `OPENAI_API_KEY`, `OPENAI_MODEL`
  - `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`
  - `GEMINI_API_KEY`, `GEMINI_MODEL`
  - `GROQ_API_KEY`, `GROQ_MODEL`
  - `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- RAG:
  - No configurable env vars in current backend settings (paths are currently defined in service code).
- Validation:
  - `MATIEC_BIN`
  - `PLCVERIF_BIN`
  - `VERIFICATION_TIMEOUT_S`
- CORS/frontend:
  - `NEXT_PUBLIC_API_BASE_URL`
  - `NEXT_PUBLIC_USE_MOCK_API`
  - `NEXT_PUBLIC_PLANNING_MODE`



## Running the Application

- Backend server: `uvicorn app.main:app --reload --port 8000` (from `backend/`).
- Frontend server: `npm run dev` (from repository root).
- Docker Compose: `docker compose up --build`.
- Knowledge-base seeding: runs automatically during backend startup lifespan; verify via backend logs and `GET /api/health`.
- Benchmark runner (API): `POST /api/benchmarks/run`, `POST /api/benchmarks/compare`, or `POST /api/benchmarks/run-suite`.

Example suite run:

```bash
curl -X POST http://localhost:8000/api/benchmarks/run-suite
```



## Testing and Quality Checks

Backend:

```bash
cd backend
pytest
python -m compileall app
```

Frontend:

```bash
npm run typecheck
npm run lint
npm run test
npm run build
```



## API Overview

Routers are registered under `/api`:

- Health:
  - `GET /api/health`
- Project workflow:
  - `/api/projects` for create/list/get and full workflow (`requirements`, `plan`, `generate`, `validate`, `debug`, `repair-loop`, `optimize`, `metrics`, `report`, exports).
- Benchmarks:
  - `/api/benchmarks/cases`
  - `/api/benchmarks/run`
  - `/api/benchmarks/compare`
  - `/api/benchmarks/run-suite`
  - `/api/benchmarks/results`
  - `/api/benchmarks/summary`



## Evaluation Modes

Supported execution/evaluation modes:

- Deterministic/rule-based: used by benchmark mode `rule_based`.
- LLM-only: used by benchmark mode `llm`.
- LLM + RAG: used by benchmark mode `llm_rag`.

Configuration:

- LLM provider/model is selected through backend environment variables (`LLM_PROVIDER` and provider-specific model vars).
- Main runtime agent mode selection is currently hardcoded in `ProjectService` (plan/code/debug/optimize use `llm`; validation uses `static`).



## Known Limitations

- Current validation in the active runtime is compiler-backed syntax validation plus domain-aware structural safety validation; it is not full temporal-logic model checking in the default pipeline.
- `ValidationAgent(mode="formal")` exists, but formal mode is not wired into the main project workflow endpoints.
- Generated PLC code still requires industrial engineer review before deployment.
- Estimated scan time is a static proxy metric unless validated on real PLC hardware/digital twin.
- LLM outputs can vary by provider/model and prompt context.
- Default SQLite storage is suitable for local/demo use; production persistence requires managed DB deployment.
- Frontend includes some remaining mock-only UI data paths (for dashboard/settings/workflow monitor views).



## Roadmap (Planned)

- Wire formal validation mode into the default workflow and complete nuXmv/PLCverif operational integration.
- Expand benchmark corpus and benchmarking analytics.
- Conduct broader industrial engineer evaluation studies.
- Add vendor-specific codegen targets and conformance profiles.
- Validate generated logic on real PLC hardware or digital-twin environments.



## Security Notes

- Never commit `.env` files or API keys.
- Keep local DB/vector-store artifacts out of version control.
- Rotate any credential immediately if it is accidentally committed.



## Research Disclaimer

OptPLC is a research prototype for academic and engineering evaluation. It is not a certified safety system and does not provide SIL or production safety guarantees.

## Additional Docs

- Backend technical documentation: `[backend/README.md](backend/README.md)`

