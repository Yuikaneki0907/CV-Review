# CV-Review

Hệ thống full-stack hỗ trợ ứng viên **viết CV** và **đánh giá CV** theo Job
Description (JD) bằng AI. Toàn bộ logic chấm điểm chạy theo **schema 5 chiều**
có thể tái lập (deterministic) cho 3/5 chiều, và 2/5 chiều dùng LLM-as-judge —
tránh tình trạng "đánh giá theo cảm tính".

> Stack ngắn gọn: **FastAPI + Celery + SQLAlchemy async + PostgreSQL + Redis +
> MinIO** ở backend, **React + Vite + TipTap** ở frontend, AI provider có thể
> đổi giữa **OpenAI** / **Gemini** / **OpenAI-OAuth** qua biến môi trường.

---

## Hai pipeline AI song song

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│   ┌────────────────────┐          ┌──────────────────────────────┐   │
│   │  Generate pipeline │          │  Analyze pipeline            │   │
│   │  (Phase 2 + 3)     │          │  (Phase 1)                   │   │
│   ├────────────────────┤          ├──────────────────────────────┤   │
│   │ chat / improve →   │          │ extract_jd  →  extract_cv    │   │
│   │ generate →         │  ───→    │      ↓             ↓         │   │
│   │ analyze →          │          │   score_cv (5 chiều)         │   │
│   │ revise → analyze   │          │      ↓                       │   │
│   │ (quality_gate)     │          │   verdict + suggestions      │   │
│   └────────────────────┘          └──────────────────────────────┘   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Pipeline Generate

| Endpoint                                          | Use case                       | Mô tả                                                                |
| ------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------- |
| `POST /api/v1/generated-cvs/chat/stream`          | `ChatCVUseCase`                | Chat tự nhiên với AI; khi đủ thông tin AI xuất `<FINAL_CV>...</FINAL_CV>`. |
| `POST /api/v1/generated-cvs/{id}/edit/stream`     | `EditGeneratedCVUseCase`       | Sửa CV đã có thành phiên bản mới (versioning, immutable rows).      |
| `POST /api/v1/generated-cvs/improve`              | `GenerateAndImproveCVUseCase`  | Loop `generate → analyze → revise` tối đa 3 vòng.                    |
| `POST /api/v1/generated-cvs/import`               | `ImportGeneratedCVUseCase`     | Parse PDF/DOCX → markdown lossy.                                     |
| `POST /api/v1/generated-cvs/{id}/normalize`       | `NormalizeGeneratedCVUseCase`  | LLM strict-rewrite: chỉ tổ chức lại, không thay đổi nội dung (≥85% token gốc). |

**Quality gate** (`application/services/generation/quality_gate.py`) chạy sau
mọi lần emit CV: extract JD → extract CV → `score_cv` → revise nếu
`overall_score < 80` (mặc định `DEFAULT_MAX_REVISIONS=2`). Trả về CV tốt nhất
giữa các vòng.

### Pipeline Analyze

| Endpoint                                          | Use case             | Mô tả                                                              |
| ------------------------------------------------- | -------------------- | ------------------------------------------------------------------ |
| `POST /api/v1/analysis/`                          | `AnalyzeCVUseCase`   | Upload file → MinIO → Celery task → SSE progress qua Redis pub/sub. |
| `POST /api/v1/analysis/chat-analyze/stream`       | `AnalyzeCVUseCase`   | Inline SSE — không cần tạo row trước.                              |
| `POST /api/v1/analysis/generated/{cv_id}`         | `AnalyzeCVUseCase`   | Chấm lại 1 CV đã sinh ra (cross-pipeline check).                   |

### Schema chấm điểm 5 chiều

| Dimension              | Trọng số | Loại                | Lý do                                              |
| ---------------------- | -------: | ------------------- | -------------------------------------------------- |
| `relevance`            |     30 % | LLM-judge           | CV có làm đúng nhóm việc JD yêu cầu không?         |
| `keyword_coverage`     |     25 % | Deterministic       | Bao nhiêu % must-have keyword JD xuất hiện trong CV. |
| `achievement_quality`  |     20 % | Deterministic       | Bullet có action verb + chỉ số định lượng + 8-40 từ. |
| `structure`            |     15 % | Deterministic       | Đủ 4 section, ít placeholder, có dữ kiện thật.     |
| `summary_alignment`    |     10 % | LLM-judge           | Summary có nói thẳng về JD không.                  |

**Verdict:** `PASS ≥ 70`, `BORDERLINE 50–69`, `FAIL < 50`. Quality gate ngưỡng
mặc định `DEFAULT_PASS_THRESHOLD=80` cho CV do AI sinh, đảm bảo CV-Gen luôn
clear pipeline Analyze.

Output đầy đủ ở [`AnalysisResultSchema`](backend/app/domain/schemas/analysis_schema.py):
`overall_score`, `verdict`, `dimension_scores` (5 chiều + reason), `gap_analysis`
(`critical_missing`/`improvable`), `keyword_report` (`found`/`missing`/`density_ok`),
`suggestions[]` (rewrite proposals dạng `current` vs `suggested`).

---

## Kiến trúc Clean Architecture (backend)

```
backend/app/
├── presentation/      # FastAPI routes — handler thin, gọi use case
│   ├── analysis_routes.py
│   ├── auth_routes.py
│   ├── cv_file_routes.py
│   └── generated_cv_routes.py
│
├── application/       # Logic nghiệp vụ; KHÔNG được import từ infrastructure
│   ├── use_cases/     # ChatCVUseCase, AnalyzeCVUseCase, ...
│   ├── services/
│   │   ├── scoring/        # 5-dimension scorers + aggregator
│   │   ├── generation/     # cv_generator, cv_reviser, improvement_loop, quality_gate, normalize_import
│   │   └── shared/         # cv_extractor, jd_extractor, skill_normalisation
│   ├── interfaces/    # IAIService, IAnalysisRepository, IGeneratedCVRepository, ...
│   ├── prompts/       # *.txt — TẤT CẢ prompt LLM nằm ở đây, load qua render_prompt()
│   └── dto/           # Request/Response Pydantic
│
├── domain/            # Entities + Pydantic schemas + value objects (pure, no I/O)
│   ├── entities/      # AnalysisResult, GeneratedCV, User, ...
│   ├── schemas/       # AnalysisResultSchema, CVSchema, JDSchema, IterationRecord
│   └── value_objects/ # MatchScore, Skill, ...
│
└── infrastructure/    # Adapter cụ thể
    ├── ai/            # openai_service, gemini_service (factory chọn theo AI_PROVIDER)
    ├── database/      # SQLAlchemy models + repos
    ├── celery/        # Celery app + tasks
    ├── file_parsers/  # PyMuPDF / python-docx / mammoth / pdf2docx
    ├── storage/       # MinIO client
    └── notifications/ # SMTP
```

**Dependency rule:** `presentation` / `infrastructure` chỉ được import inward
vào `application` / `domain`. Không bao giờ ngược lại.

---

## Frontend

`frontend/src/`:

- `pages/` — `WorkspacePage`, `GenerateCVPage`, `AnalysisPage`, `HistoryPage`,
  `CVManagementPage`, ...
- `components/` — `SideNav`, `CvWysiwygEditor` (TipTap-based markdown WYSIWYG)
- `api.js` — fetch/axios client; SSE helpers; auth token đọc từ `localStorage`
- `AuthContext.jsx` — auth state + login/logout
- `utils/` — `workspaceDraft`, `templateSkeletons`, `analysisInsights` (legacy)

Vite dev server proxy `/api/*` → `VITE_PROXY_TARGET` (mặc định `http://localhost:8020`).
ESLint config cho phép unused vars match `^[A-Z_]`.

---

## Chạy local

### Cách 1 — Conda + scripts (host-side dev)

```bash
# Một lần duy nhất:
conda env create -f environment.yml      # tạo env "cv-review" (Python 3.11 + Node 20)
cp .env.example .env                     # nhớ sửa OPENAI_API_KEY hoặc GEMINI_API_KEY

# Mỗi phiên dev:
./scripts/run_all.sh
# → DB + Redis + MinIO (Docker)
# → alembic upgrade head
# → FastAPI :8020 + Celery worker + Vite :5120
```

Hoặc chạy từng phần độc lập:

```bash
./scripts/run_infra.sh      # chỉ DB + Redis + MinIO (+ optional Mailpit)
./scripts/run_backend.sh    # FastAPI
./scripts/run_worker.sh     # Celery worker
./scripts/run_frontend.sh   # Vite
```

### Cách 2 — Pure Docker Compose

```bash
cp .env.example .env
docker compose up
# → backend trên 0.0.0.0:8020 (alembic upgrade head trước khi uvicorn)
# → frontend trên 0.0.0.0:3020
```

### Service ports (compose bind `127.0.0.1`)

| Service       | Port (host) |
| ------------- | ----------- |
| FastAPI       | `8020`      |
| Vite (host)   | `5120`      |
| Vite (Docker) | `3020`      |
| PostgreSQL    | `5420`      |
| Redis         | `6320`      |
| MinIO API     | `9020`      |
| MinIO console | `9021`      |
| Mailpit UI    | `8025`      |

---

## Cấu hình

`backend/app/config.py:Settings` là single source of truth (đọc qua
`pydantic-settings`). Quan trọng:

| Biến                    | Mặc định                                            | Ghi chú                                                |
| ----------------------- | --------------------------------------------------- | ------------------------------------------------------ |
| `AI_PROVIDER`           | `openai`                                            | `openai` / `gemini` / `openai_oauth`                   |
| `OPENAI_API_KEY`        | —                                                   | Bắt buộc khi dùng `openai`                             |
| `OPENAI_MODEL`          | `gpt-4o-mini`                                       |                                                        |
| `OPENAI_API_BASE_OAUTH` | `http://127.0.0.1:8317/v1`                          | Khi dùng `openai_oauth` (proxy token-less)             |
| `GEMINI_API_KEY`        | —                                                   | Bắt buộc khi dùng `gemini`                             |
| `DATABASE_URL`          | `postgresql+asyncpg://cvreview:cvreview_pass@db:5432/cvreview` |                                            |
| `REDIS_URL`             | `redis://redis:6379/0`                              |                                                        |
| `CELERY_BROKER_URL`     | giống `REDIS_URL`                                   |                                                        |
| `MINIO_ENDPOINT`        | `minio:9000`                                        |                                                        |
| `SECRET_KEY`            | —                                                   | Production refuse boot khi vẫn để default              |
| `CORS_ORIGINS`          | `["http://localhost:3020","http://localhost:5120"]` | Production refuse boot khi chứa `*`                    |

`validate_runtime_safety` chạy ở startup: nếu `ENVIRONMENT=prod` mà `SECRET_KEY`
/ MinIO creds vẫn default, hoặc `DEBUG=true`, hoặc `CORS_ORIGINS` chứa `*` →
raise. **Sửa env, đừng làm yếu check.**

---

## Migrations

```bash
cd backend
alembic upgrade head                      # apply migrations
alembic revision -m "add foo" --autogenerate
```

`alembic.ini` để `sqlalchemy.url` rỗng — URL lấy từ `Settings.DATABASE_URL` qua
`alembic/env.py`.

---

## Testing

```bash
cd backend
pytest                                    # tất cả test
pytest tests/integration/test_cross_pipeline.py -v   # cross-pipeline guarantee
pytest tests/unit/scoring/test_aggregator.py -xvs    # 1 file, verbose, no capture
```

### Cấu trúc test

```
backend/tests/
├── conftest.py                          # prepend backend/ vào sys.path
├── fixtures/fake_ai.py                  # FakeIAIService — dùng thay cho mock SDK
├── unit/
│   ├── schemas/                         # CVSchema, JDSchema validation
│   ├── scoring/                         # aggregator, keyword_coverage, achievement_quality, structure
│   ├── services/                        # cv_generator, cv_reviser, improvement_loop, quality_gate, *_extractor
│   └── use_cases/                       # chat_cv_quality_gate (JD persistence), generate_and_improve_cv_stream
└── integration/
    ├── test_analyze_cv_pipeline.py      # AnalyzeCVUseCase end-to-end
    └── test_cross_pipeline.py           # Goal: gen-CV qua quality_gate luôn PASS analyze (>=80)
```

**Quy ước:** dùng `tests/fixtures/fake_ai.py` thay vì mock từng method của
SDK. `backend/test_llm.py` ở root là smoke script ad-hoc — không thuộc pytest.

Frontend:

```bash
cd frontend
npm run lint    # ESLint
npm run build   # Vite production build
npm run dev     # Vite dev server
```

---

## House style

- **Vietnamese** cho mọi user-facing string (errors, chat reply, UI labels).
- Logger: `app.logger.get_logger("app.<module>")` — không dùng
  `logging.getLogger` trực tiếp.
- Prompts ở `application/prompts/*.txt`, load qua `render_prompt(name, **vars)`
  (`string.Template` — dùng `$var`, không phải `{var}`).
- Repositories rollback + re-raise; use case quyết định retry.
- Celery task tự rollback + `mark_failed` trước khi retry.
- Conventional Commits: `feat(scope): summary` / `fix(scope): summary` / `test:`
  / `refactor(scope):` / `docs:` ...
- Generated CV rows **immutable** — mỗi edit là 1 row mới cùng `conversation_id`,
  trỏ về parent qua `parent_version_id`. "Latest CV" query dùng `MAX(version)`
  group theo `conversation_id`.

---

## License

Internal project — chưa release.
