# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the stack

Two equivalent ways to bring everything up — pick one and stay with it.

**Conda + scripts (host-side dev):** the scripts assume a `cv-review` conda env (`conda env create -f environment.yml`) and a running Docker daemon for the infra containers.

- `./scripts/run_all.sh` — DB + Redis + MinIO via `docker compose`, then alembic upgrade, FastAPI (port 8020), Celery worker, Vite dev server (port 5120).
- `./scripts/run_infra.sh` / `run_backend.sh` / `run_worker.sh` / `run_frontend.sh` — same pieces individually.

**Pure Docker Compose:** `docker compose up` brings up the same services but the backend lives on `0.0.0.0:8020` and the frontend on `0.0.0.0:3020`. The `backend` service runs `alembic upgrade head` before starting uvicorn.

Service ports (compose binds to `127.0.0.1`): Postgres `5420`, Redis `6320`, MinIO API `9020`, MinIO console `9021`, Mailpit UI `8025`.

## Backend dev commands

Run from `backend/` inside the conda env (or `docker compose exec backend …`).

- Tests: `pytest` (root config relies solely on `tests/conftest.py`, which prepends `backend/` to `sys.path`). Single test: `pytest tests/unit/scoring/test_aggregator.py::test_name -xvs`. Tests use `unittest.TestCase` + `pytest`; fake AI services live in `tests/fixtures/fake_ai.py` — prefer these over mocking individual methods.
- Migrations: `alembic upgrade head`, `alembic revision -m "msg" --autogenerate`. `alembic.ini` has `sqlalchemy.url` blank — the URL comes from `app.config.Settings.DATABASE_URL` via `alembic/env.py`.
- The repo ships `backend/test_llm.py` and a root-level `test_llm.py` as ad-hoc smoke scripts for the AI provider — they are NOT part of the pytest suite.

## Frontend dev commands

From `frontend/`: `npm run dev` (Vite on `0.0.0.0:5120`), `npm run build`, `npm run lint`. ESLint rule of note: unused vars starting with capital/`_` are allowed (`varsIgnorePattern: '^[A-Z_]'`). Vite proxies `/api/*` to `VITE_PROXY_TARGET` (defaults `http://localhost:8020`).

## Architecture

### Clean-architecture layout (backend/app)

- `presentation/` — FastAPI routers (`analysis_routes`, `auth_routes`, `cv_file_routes`, `generated_cv_routes`). Handlers MUST stay thin: validate, call a use case, map to a response DTO. Scoring/extraction/AI logic does not belong here (see the docstring at the top of `analysis_routes.py`).
- `application/` — use cases (`use_cases/`), services (`services/`), DTOs (`dto/`), interfaces (`interfaces/`), prompt templates (`prompts/*.txt` loaded via `prompts/loader.py`), exception types. Code here depends only on `domain/` + `application/interfaces/`.
- `domain/` — pure entities (`entities/`), pydantic schemas for AI I/O (`schemas/`), and value objects (`value_objects/`). No I/O, no FastAPI, no SQLAlchemy.
- `infrastructure/` — concrete adapters: SQLAlchemy models + repos (`database/`), Celery app + tasks (`celery/`), AI providers (`ai/`), file parsers (`file_parsers/`), MinIO (`storage/`), SMTP (`notifications/`).

The dependency rule: presentation/infrastructure depend inwards on application/domain. Don't import infrastructure from application/domain code.

### Two parallel pipelines

**Analyze pipeline (Phase 1 — score a CV against a JD).** Entry: `POST /api/v1/analysis/` (file upload → MinIO → Celery) or `POST /api/v1/analysis/chat-analyze/stream` (inline SSE). The Celery task in `infrastructure/celery/tasks.py` invokes `AnalyzeCVUseCase`, which is a thin chain: `extract_jd → extract_cv → score_cv → persist`. The scorer (`application/services/scoring/aggregator.py:score_cv`) computes five weighted dimensions (relevance / keyword_coverage / achievement_quality / structure / summary_alignment — weights in `domain/schemas/analysis_schema.py:DIMENSION_WEIGHTS`), derives a verdict (PASS ≥70, BORDERLINE 50–69, FAIL <50), and emits an `AnalysisResultSchema`. Pre-flight short-circuits handle unusable JDs and template-only CVs without burning LLM calls. Progress is streamed to clients via Redis pub/sub on channel `analysis:{id}` — the SSE route in `analysis_routes.py:stream_analysis` subscribes and forwards.

**Generate/chat pipeline (Phases 2–3 — produce a CV).** Entry: `POST /api/v1/generated-cvs/chat/stream` and friends in `generated_cv_routes.py`. `ChatCVUseCase` (new CV) and `EditGeneratedCVUseCase` (revise) own the conversational flow. The improvement loop in `application/services/generation/improvement_loop.py` runs `generate → analyze → revise → analyze → …` up to `DEFAULT_MAX_ITERATIONS=3`, stopping on `passed_threshold` / `no_improvement` / `extractor_failed` / `max_iterations`. After any CV emission the **quality gate** (`application/services/generation/quality_gate.py:ensure_quality`, default threshold 80) re-scores and may run bounded revisions before returning. Both the streaming use case and the loop emit typed SSE events (`status`, `chat_chunk`, `cv_chunk`, `cv_id`, `iteration`, `done`, `error`).

### Generated CV versioning

`GeneratedCVModel` rows are immutable — every edit creates a new row sharing a `conversation_id`, pointing back via `parent_version_id` (see `create_versioned` in `generated_cv_repository`). `ChatSessionModel` stores the chat transcript for that conversation. The "latest CV" query joins on `MAX(version)` grouped by `conversation_id` — see `_get_latest_cv_map` in `generated_cv_routes.py`. Soft-deletes via `deleted_at` are honoured by every list query.

### Import-normalize pass

`POST /api/v1/generated-cvs/import` runs a deterministic PDF/DOCX parser (`infrastructure/file_parsers/import_pipeline`) and stores the result with `source_type="uploaded_cv"`. The parser is lossy on multi-column / iconified PDFs, so an opt-in cleanup endpoint `POST /api/v1/generated-cvs/{cv_id}/normalize` runs `application/services/generation/normalize_import.py:normalize_imported_cv` — a strict-rewrite LLM pass that re-groups/re-indents the markdown but is forbidden from changing content. The service rejects any output that drops more than `CONTENT_LOSS_TOLERANCE=0.15` of the original alphanumeric tokens and returns the original markdown with a warning instead. On success a new immutable version is created and `source_type` is promoted to `uploaded_cv_normalized`; the use case (`NormalizeGeneratedCVUseCase`) refuses to run on anything else. The response always includes `normalize_changed` and `normalize_warnings` so the FE can show the right toast.

### AI provider abstraction

`infrastructure/ai/__init__.py:ai_service_factory()` picks an `IAIService` (`application/interfaces/ai_service.py`) based on `settings.AI_PROVIDER` ∈ `{openai, gemini, openai_oauth}`. The OAuth variant points at a local `OPENAI_API_BASE_OAUTH` (default `http://127.0.0.1:8317/v1`) — useful when you want to swap the underlying model without touching code. Add new providers by implementing `IAIService` and wiring the factory; never call SDKs directly from use cases.

### Prompts

All LLM prompts are externalised as `.txt` files in `application/prompts/` and loaded via `prompts/loader.py` (use `render_prompt(name, **vars)`). When changing analyzer or generator behaviour, edit the prompt file rather than inlining strings in the service. Filenames map to phases: `jd_extraction`, `cv_extraction` (shared/Phase 1), `scoring_*` (aggregator), `cv_generation`, `cv_revision` (Phase 2/3), `cv_normalize` (import cleanup — see Import-normalize pass).

### Crash recovery

`app.main:create_app` registers a startup hook (`recover_stuck_analyses`) that finds analyses left in PENDING/PROCESSING after a crash and re-queues them via `run_analysis_task.delay`. Don't bypass it by editing the status enum directly.

### Frontend routing

Single-page React app (`frontend/src/App.jsx`). All authenticated routes go through `PrivateRoute`; `/upload` is a permanent redirect to `/generate-cv`. Backend API calls live in `frontend/src/api.js`; auth context is in `AuthContext.jsx`.

## Configuration

`backend/app/config.py:Settings` is the single source of truth. Production safety (`validate_runtime_safety`) refuses to boot when `ENVIRONMENT` is `prod`/`production` AND the SECRET_KEY/MinIO creds are still defaults, DEBUG is on, or CORS contains `*`. Don't silently relax these — fix the env.

## House style

- Most user-facing strings (errors, chat messages) are in Vietnamese; keep that consistent when adding new ones.
- Use `app.logger.get_logger("app.<module-path>")` for logging; never `logging.getLogger` directly.
- Repositories always rollback on exception and re-raise; callers (use cases) decide whether to retry. The Celery task in `tasks.py` does its own rollback + `mark_failed` before retry — mirror this pattern when adding new background work.
