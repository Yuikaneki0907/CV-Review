# Repository Guidelines

## Project Structure & Module Organization

This is a full-stack CV review application. Backend code lives in `backend/app` and follows a clean-architecture layout: `presentation/` for FastAPI routes, `application/` for use cases, services, DTOs, interfaces, and prompts, `domain/` for pure entities/value objects, and `infrastructure/` for database, Celery, AI, parsers, storage, and email adapters. Backend tests are under `backend/tests`.

Frontend code lives in `frontend/src`, with pages in `pages/`, shared UI in `components/`, API/auth entry points in `api.js` and `AuthContext.jsx`, and assets in `frontend/public` or `frontend/src/assets`. Sample CV/JD files are in `publics/`; exported mockups are in `stitch-export/`.

## Build, Test, and Development Commands

- `conda env create -f environment.yml`: create the expected `cv-review` Python/Node environment.
- `./scripts/run_all.sh`: start infrastructure, migrations, FastAPI on `8020`, Celery, and Vite on `5120`.
- `docker compose up`: run the stack in containers; frontend is exposed on `3020`.
- `cd backend && pytest`: run backend tests.
- `cd backend && alembic upgrade head`: apply database migrations.
- `cd frontend && npm run dev`: start Vite locally.
- `cd frontend && npm run build && npm run lint`: build and lint the React app.

## Coding Style & Naming Conventions

Keep backend dependencies pointed inward: `application` and `domain` must not import infrastructure adapters. FastAPI handlers should stay thin and call use cases. Use `app.logger.get_logger("app.<module>")` for logging. Keep LLM prompt text in `backend/app/application/prompts/*.txt`.

Python uses 4-space indentation, snake_case modules/functions, and PascalCase classes. React components use PascalCase `.jsx` files; hooks/utilities use camelCase. ESLint is configured in `frontend/eslint.config.js`; unused vars are only acceptable when matching `^[A-Z_]`.

## Testing Guidelines

Use pytest for backend coverage. Name tests `test_*.py` and place focused unit tests beside their domain area, for example `backend/tests/unit/services/test_cv_generator.py`. Prefer `backend/tests/fixtures/fake_ai.py` over direct SDK calls. For targeted runs, use `cd backend && pytest tests/unit/scoring/test_aggregator.py -xvs`.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commits, for example `feat: wire quality gate into chat-gen flow` and `refactor(ai): implement sliding window...`. Follow `type(scope): summary` when useful; keep summaries imperative and specific.

Pull requests should include the user-facing change, backend/frontend impact, migration notes, test commands run, and screenshots or recordings for UI changes. Link related issues and call out required `.env` changes.

## Security & Configuration Tips

Copy `.env.example` to `.env` for local work and never commit secrets. Production safety checks in `backend/app/config.py` reject default secrets, wildcard CORS, and debug mode; fix configuration rather than weakening those checks.
