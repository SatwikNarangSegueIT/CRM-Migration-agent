# MigrateCRM

Enterprise CRM for Australian registered migration agents (MARA / OMARA regulated).
Plan: [`docs/Implementation_Plan_v2.pdf`](docs/Implementation_Plan_v2.pdf).

| Layer | Stack |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, Celery + Redis |
| Frontend | React 18, TypeScript, Vite, React Router, TanStack Query, Tailwind CSS |
| Database | Neon serverless PostgreSQL (AWS Sydney) – see [`docs/neon-setup.md`](docs/neon-setup.md) |

**Status**

| Phase | Scope | State |
|---|---|---|
| 0 | Foundations: config, logging, errors, DB layer, migrations, health checks, worker, CI, Docker | Done |
| 1 | Auth (sessions, CSRF, MFA, password reset, invitations), roles & permissions, audit log, user admin, UI kit | Backend done; UI in progress |
| 2–7 | Core CRM, matters, billing, client portal, reports, hardening | Planned |

Roles and the permission matrix: section 7 of the plan, implemented in
[`backend/app/permissions/matrix.py`](backend/app/permissions/matrix.py) and verified against the plan by
`backend/tests/test_permissions.py`.

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

First user:

```bash
uv run python -m app.cli create-admin --email you@agency.com.au --name "Your Name"   # prompts for password
```

Development only – one demo account per staff role (`admin@demo.example.com`, `manager@…`, `agent@…`,
`officer@…`, `intake@…`, `accounts@…`, `auditor@…`; password `Demo-Password-2026!`):

```bash
uv run python -m app.cli seed-demo
```

`backend/.env.example` sets `MFA_REQUIRED_FOR_STAFF=false` for local development. It must stay `true` in
production (enforced at start-up), where staff enrol an authenticator app at first sign-in.

Worker (separate terminal; sends e-mails such as invitations and password resets):

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

## Security model (phase 1)

- Sessions: opaque 256-bit token in an `HttpOnly`, `SameSite=Lax` (`Secure` outside dev) cookie; only its
  SHA-256 hash is stored. 12 h absolute / 60 min idle expiry; revoked on logout, password change/reset,
  role change and deactivation.
- CSRF: per-session token (cookie `crm_csrf`, sent back as `X-CSRF-Token`) on every unsafe request, plus an
  Origin check against `PUBLIC_APP_URL`.
- Passwords: Argon2id; ≥ 12 characters, common/simple passwords and ones containing the user's e-mail or name
  are refused. Lockout after 5 failed attempts (password or MFA) for 15 minutes; Redis rate limits on sign-in,
  MFA, password reset and invitation endpoints.
- MFA: TOTP (authenticator app) with ±30 s drift and replay protection, 10 single-use recovery codes; mandatory
  for staff. Secrets are encrypted with a key derived from `SECRET_KEY`.
- Audit: every sign-in, failure, lockout, MFA event, password event and user change is written to
  `audit_logs`, which a database trigger makes append-only.

## Configuration

See [`backend/.env.example`](backend/.env.example). In staging/production `SECRET_KEY` (≥ 32 chars) is required.
