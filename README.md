# MigrateCRM

Enterprise CRM for Australian registered migration agents (MARA / OMARA regulated).
Plan: [`docs/Implementation_Plan_v2.pdf`](docs/Implementation_Plan_v2.pdf).

| Layer | Stack |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, Celery + Redis |
| Frontend | React 18, TypeScript, Vite, React Router, TanStack Query, Tailwind CSS |
| Database | Neon serverless PostgreSQL (AWS Sydney) – see [`docs/neon-setup.md`](docs/neon-setup.md) |

**Status:** Phase 0 (foundations) complete – project structure, configuration, logging, error format,
database layer, migrations, health checks, background worker, tests, Docker and CI.

## Repository layout

```
backend/    FastAPI app (app/), Alembic migrations, tests
frontend/   React SPA, nginx config for production
docs/       Implementation plan, Neon setup
.github/    CI and Neon preview-branch workflows
```

## Quick start (Docker)

```bash
docker compose up --build
```

- App: http://localhost:5173 (the Vite dev server proxies `/api` to the API)
- API docs: http://localhost:8000/api/v1/docs
- Uses a local Postgres by default. To use a Neon branch, export `DATABASE_URL` (pooled) and
  `DATABASE_URL_DIRECT` (direct) before running compose.

## Local development without Docker

Requirements: [uv](https://docs.astral.sh/uv/), Node.js 22, PostgreSQL 16 (or a Neon branch), Redis 7.

Backend:

```bash
cd backend
cp .env.example .env   # then edit DATABASE_URL / REDIS_URL
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Worker (separate terminal):

```bash
cd backend && uv run celery -A app.worker.celery_app worker --loglevel=INFO
```

Frontend (separate terminal):

```bash
cd frontend && npm install && npm run dev
```

## Checks

Backend (tests need a Postgres database and Redis; defaults: `postgresql://crm:crm@localhost:5432/crm_test`,
`redis://localhost:6379/15`, override with `TEST_DATABASE_URL` / `TEST_REDIS_URL`):

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests alembic && uv run pytest
```

Frontend:

```bash
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

Optional git hooks: `pre-commit install` (see `.pre-commit-config.yaml`).

## API conventions

- All endpoints under `/api/v1`. Health: `GET /api/v1/health/live`, `GET /api/v1/health/ready` (503 when a dependency is down).
- Errors: `{"error": {"code", "message", "fields", "request_id"}}`; every response carries `X-Request-ID`.
- OpenAPI docs are disabled when `APP_ENV=production`.

## Configuration

See [`backend/.env.example`](backend/.env.example). In staging/production `SECRET_KEY` (≥ 32 chars) is required.
