# AGENTS.md — OptPLC Project Context
## Multi-Agent AI System for IEC 61131-3 Structured Text

> **Read this file first in every session, then `docs/plan/STATUS.md`.**
> `docs/plan/` is the single source of truth for the plan, the status, and every decision (D-001).
> Last updated: 2026-09-14 (plan item P0-08). Earlier versions of this file contained statements that no
> longer matched the code; they are listed in `docs/plan/AUDIT_2026-09.md` §2.

---

## 1. Project Identity

| Field | Value |
|-------|-------|
| **Name** | OptPLC |
| **Purpose** | Generate, check, repair, and optimize IEC 61131-3 Structured Text (ST) from natural-language requirements |
| **Target users** | Industrial control engineers and system integrators |
| **Academic context** | Master's thesis, Peter the Great St. Petersburg Polytechnic University (defense June 2027) |
| **Target standard** | IEC 61131-3 Structured Text, CODESYS / TwinCAT compatible |

---

## 2. Architecture (as implemented)

```
Frontend  Next.js 15 + React 19 + TypeScript — 9-step pipeline UI at /projects/[id]/<step>
   │  REST (/api/...)
Backend   FastAPI — ProjectService runs one pipeline step per HTTP request
   │        5 agents; LLM access only through app/agents/llm_client.py
   │        RAG: app/services/rag_service.py (ChromaDB + all-MiniLM-L6-v2)
   │  SQLAlchemy async
Database  SQLite (dev) — tables `projects` and `sessions`; pipeline state stored as JSON columns
```

- There is **no orchestrator yet**. It is planned as a deterministic state machine (decision D-013, items P1-21, P2-11).
- The **reference runtime** for results is the Docker image built from `docker/app.Dockerfile`: MATIEC pinned to a commit, non-root user, dependencies installed from the hashed lock `backend/requirements-docker.lock`.

### Runtime modes (hard-coded in `ProjectService` until P2-11)

| Step | Agent | Mode | What actually happens |
|------|-------|------|-----------------------|
| Plan | PlanningAgent | `llm` | Falls back to `rule_based` if the reply is not valid JSON twice |
| Generate | CodeGenerationAgent | `llm` | Falls back to `template_based` if the reply has no `PROGRAM` or misses a plan output; RAG is off on `/generate` |
| Validate | ValidationAgent | `static` | MATIEC when available (the code is normalized first, see §8), otherwise a regex fallback (bug C-01); then regex domain rules |
| Debug | DebuggingAgent | `llm` | Falls back to `rule_based` on any LLM error |
| Optimize | OptimizationAgent | `llm` | Three passes with static revalidation and rollback; **no behavioural-equivalence check** (C-03) |

---

## 3. Evidence Ladder and Wording Rule (D-003)

| Level | Meaning | Unlocked in phase |
|-------|---------|-------------------|
| L0 GENERATED | Code produced, unchecked | now |
| L1 COMPILES | MATIEC compiles the **unmodified** source | 1 |
| L2 STATIC_RULES_PASSED | Documented heuristic rules pass (proves nothing) | 1 |
| L3 SIMULATION_TESTED | Properties hold on test vectors in a scan-cycle simulator | 2 |
| L4 PROPERTIES_PROVEN | Safety properties proven by nuXmv | 3 |
| L5 HIL_PASSED | Scenarios pass on a (virtual or real) PLC with measured cycle time | 5 |
| L6 ENGINEER_APPROVED | A named engineer signed off | 8 |

**Never describe output as "verified" below L4.** The current code reaches at most L2, even though its status
enum is called `VERIFIED`; the enum is renamed in P1-04.

---

## 4. Data Contracts — Conventions

- All Pydantic contracts live in `backend/app/schemas/contracts.py` and are mirrored in `src/lib/api-contracts/types.ts`.
- Field names are camelCase (`projectId`, not `project_id`).
- Every contract inherits `ContractModel` (`extra="forbid"`).
- Use `Literal[...]` types instead of `Enum`.

---

## 5. Key Files

```
backend/app/
  config.py                    Pydantic settings (.env); LLM_PROVIDER selects the provider
  main.py                      FastAPI app, CORS, startup (create_all + RAG seed)
  schemas/contracts.py         All data contracts
  database/                    engine, ORM models, Repository
  services/project_service.py  Pipeline steps, reports (to be split in P2-11)
  services/validation_service.py  MATIEC wrapper (+ PLCverif executor, unused)
  services/transpiler_service.py  ST→SMV scaffold — not usable for proofs (replaced in P3-02)
  services/metrics_service.py  LOC, CC, MI variant, static cost proxy (not milliseconds, M-03)
  services/rag_service.py      Chroma retrieval; paths hard-coded to /app (fixed in P1-20)
  services/benchmark_runner.py rule_based / llm / llm_rag runs over benchmark/cases/
  agents/                      the five agents + llm_client.py
  tests/                       hermetic pytest suite (conftest.py, fakes.py, known_failures.txt)
backend/benchmark/cases/       B001–B005 (15 more cases to author, D-016)
backend/knowledge_base/patterns/  12 RAG patterns
docker/app.Dockerfile          reference image
scripts/check.ps1              local pre-merge checks (replaces CI, D-015)
scripts/backup_runtime_data.py verified backup of plcforge.db and benchmark results (D-018)
scripts/st-compile.ps1         compile one ST file with the pinned MATIEC in the image
src/components/pages/          page components; src/lib/api-client/ API client (mock/real toggle)
docs/plan/                     plan, status, backlog, decisions, changelog, audit, test baseline
```

---

## 6. ID Patterns

```
Projects:  PRJ-0001, PRJ-0002 ... (max existing suffix + 1)
Sessions:  one session per project, id <project>-session-1
Artifacts: PRJ-0001-code-iter-1, PRJ-0001-code-iter-2 ...
Events:    PRJ-0001-wf-requirements-1, PRJ-0001-wf-plan-2 ...
```

---

## 7. Rules — Always Follow

### Backend
1. **Signatures change only inside a documented backlog item**, updating every caller and every test in the same commit (D-004; this replaces the old "never change agent signatures" rule).
2. All database access is async (`AsyncSession`).
3. Contracts use camelCase fields.
4. New Pydantic contracts inherit `ContractModel`.
5. Read a file completely before modifying it.
6. LLM mode pattern: `if self.mode == "llm": return await self._..._with_llm(...)`. Keep the deterministic fallback, and make its use visible in the output (P1-07).
7. Call LLMs only through `llm_complete()` in `app/agents/llm_client.py`. Provider and model come from settings (`.env`). Never hard-code a model id in an agent.

### Frontend
8. Never remove mock mode, but mock data must never be shown as real results (A-06).
9. Use project-scoped routes only (`/projects/[id]/<step>`); the standalone routes are legacy.
10. Table components use the short names: `Table, THead, TBody, TR, TH, TD`.
11. All backend endpoints are under `/api/`.

### Process
12. **Scientific honesty:** record measured results as they are, including failures; never claim more than the evidence level reached.
13. **Tests:** backend tests are safe only on `staging` and branches taken from it (hermetic `conftest.py`: temp DB, fake LLM/RAG, network blocked). Never point them at `backend/plcforge.db`. Run `scripts/check.ps1` before every merge.
14. **Git (D-017, D-023):** one branch per backlog item from `staging`; merge into `staging` with `--no-ff` after the check passes; **never merge into `main` without the user's explicit approval**; the agent does not push, the user does.
15. **Documentation:** after every change update `docs/plan/BACKLOG.md`, `CHANGELOG.md`, and `STATUS.md`; ask the user before starting each backlog item.

---

## 8. Known Gaps (details in `docs/plan/AUDIT_2026-09.md` and `docs/plan/TEST_BASELINE.md`)

- **C-01:** the regex syntax fallback rejects every valid program with `VAR_INPUT`/`VAR_OUTPUT` (P1-01).
- **MATIEC normalization:** timer calls are removed, `X.Q` becomes `FALSE`, and `T#` literals become `0` before compiling, so the checked code is not the delivered code (P1-02, D-005).
- **C-02:** the repair loop shows the LLM the template code instead of the failed code (P1-06).
- **C-10 / C-11:** the motor template can never start the motor, and the batch template never sets `Batch_Complete` (P1-22).
- **Static domain rules** are text patterns; an unsafe motor program can pass them.
- **Formal path:** the transpiler deletes `IF` blocks and emits no real LTL, and its result parsing fails open (P3).
- **No authentication or rate limiting** on any endpoint (S-01; minimal protection in P1-14).
- **Dependency advisories:** `npm audit` is clean after P0-12 (Next.js 15.5.25 with a `postcss` override, D-027; the Next.js 16 upgrade is P8-14). `pip-audit` on `backend/requirements-docker.lock` reports 12 known vulnerabilities in `chromadb`, `transformers`, and `pydantic-settings`, not yet addressed; `torch 2.5.1+cpu` cannot be audited because that build is not on PyPI.

---

## 9. How to Run

```powershell
# Backend (local dev)
cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Frontend
npm install; npm run dev

# Checks before merging (typecheck, lint, vitest, hermetic pytest, audit)
powershell -ExecutionPolicy Bypass -File scripts\check.ps1

# Reference image and one-file compile with the pinned MATIEC
docker build -f docker/app.Dockerfile -t optplc-backend:p0-05 .
powershell -ExecutionPolicy Bypass -File scripts\st-compile.ps1 -Path path\to\program.st

# Backup before any database migration
backend\.venv\Scripts\python scripts\backup_runtime_data.py
```

---

## 10. Roadmap

See `docs/plan/MASTER_PLAN.md`: phases 0–8, with Orchestrator and RAG cross-cutting tracks, on a compressed schedule
ending 2027-05-30. The current phase and next items are in `docs/plan/STATUS.md`.
