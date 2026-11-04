# Meridian CRM

Configurable, multi-industry CRM (Salesforce-style) with a **Migration Agency (Australia)** industry pack.
Plan: [`docs/Implementation_Plan_v3.pdf`](docs/Implementation_Plan_v3.pdf) (v3 supersedes v2). "Meridian CRM" is a
working name; the brand name and colour are settings (Setup → Company & Branding).

| Layer | Stack |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, Celery + Redis |
| Frontend | React 18, TypeScript, Vite, React Router, TanStack Query, Tailwind CSS |
| Database | Neon serverless PostgreSQL (AWS Sydney) – see [`docs/neon-setup.md`](docs/neon-setup.md) |

**Status** (plan v3 phases)

| Phase | Scope | State |
|---|---|---|
| 0–1 | Foundations; identity (sessions, CSRF, MFA, password reset, invitations), audit log, user admin | Done |
| 2 | Security model: profiles (system / object / field permissions), role hierarchy, sharing defaults, sharing rules, groups, queues | Done |
| 3 | Metadata & record engine: custom objects and fields, validation, sharing, history, recycle bin, list views, search | Done |
| 4 | Lightning-style UI: app rail, apps & tabs, list views (columns, filters, saved views, inline edit, Kanban), record pages, Setup (Object Manager, App Manager, profiles, roles, sharing, packs, settings) | Done |
| 5–9 | Sales, Billing, Service (incl. customer portal), Marketing, Analytics (reports & dashboards), CSV import/export | Done |
| 10 | Industry pack framework + Migration Agency pack | Done |
| 11 | Hardening: load and security testing, accessibility audit, backups/retention jobs, UAT | Planned |

Roles and permissions: plan v3 sections 9–10. Defaults are seeded by
[`backend/app/security/seed_v1.py`](backend/app/security/seed_v1.py) and checked against the plan's tables by
`backend/tests/test_permissions.py`; admins change them in Setup → Profiles / Roles / Sharing Settings.

## Domain CRMs

At sign-up a firm picks Law firm, Migration agency, Accounting practice or Loan broking and gets a CRM
shaped for that profession. See [docs/domains.md](docs/domains.md).

## Documentation

| Document | For |
|---|---|
| [User guide](docs/user-guide.md) | Everyone: signing up, lists, records, portal, import/export, reports, troubleshooting |
| [How each profession's workspace works](docs/domain-workflows.md) | Step-by-step flow, stage checks, automation and reminders for law, migration, accounting and lending |
| [Roles and permissions](docs/roles-and-permissions.md) | Profiles, roles, sharing, field security and each profession's default profiles |
| [Operations runbook](docs/operations.md) | Deploying, upgrading the database, sign-up checklist, backups, performance |
| [`backend/.env.production.example`](backend/.env.production.example) | Example production settings, including Zoho Mail SMTP |

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

Development only – one demo account per default staff profile, password `Demo-Password-2026!`:
`admin@` (System Administrator), `salesmanager@`, `sales@`, `service@`, `marketing@`, `finance@`, `auditor@`
(Read Only) — all `@demo.example.com`. Install the Migration Agency pack in Setup → Industry Packs.

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

End-to-end smoke test (needs the API, worker and Vite running, demo users seeded and
`MFA_REQUIRED_FOR_STAFF=false`; uses Playwright's Chromium). `WORKER_LOG` is the worker's log file, from which
the test reads the console-backend invitation e-mail:

```bash
cd frontend && BASE_URL=http://localhost:5173 WORKER_LOG=/path/to/worker.log node e2e/smoke.mjs
```

It covers: sign-in, creating records, Object Manager (custom object + picklist field), App Manager, settings,
installing the Migration Agency pack, reports/dashboards, global search, inviting a portal user, accepting the
invitation, raising and discussing a case in the portal (phone width), and read-only auditor restrictions.

After deploying schema changes that add indexed fields, run `uv run python -m app.cli sync-indexes`.

Optional git hooks: `pre-commit install` (see `.pre-commit-config.yaml`).

## API conventions

- All endpoints under `/api/v1`. Health: `GET /api/v1/health/live`, `GET /api/v1/health/ready` (503 when a dependency is down).
- Errors: `{"error": {"code", "message", "fields", "request_id"}}`; every response carries `X-Request-ID`.
- OpenAPI docs are disabled when `APP_ENV=production`.

## Security model

- Sessions: opaque 256-bit token in an `HttpOnly`, `SameSite=Lax` (`Secure` outside dev) cookie; only its
  SHA-256 hash is stored. 12 h absolute / 60 min idle expiry; revoked on logout, password change/reset,
  profile/role change and deactivation.
- CSRF: per-session token (cookie `crm_csrf`, sent back as `X-CSRF-Token`) on every unsafe request, plus an
  Origin check against `PUBLIC_APP_URL`.
- Passwords: Argon2id; ≥ 12 characters, common/simple passwords and ones containing the user's e-mail or name
  are refused. Lockout after 5 failed attempts (password or MFA) for 15 minutes; Redis rate limits on sign-in,
  MFA, password reset and invitation endpoints.
- MFA: TOTP (authenticator app) with ±30 s drift and replay protection, 10 single-use recovery codes; mandatory
  for staff. Secrets are encrypted with a key derived from `SECRET_KEY`.
- Authorisation: deny-by-default on the server for every request, list, report, search and export — profile
  system and object permissions, field-level security (hidden fields are stripped from responses), and record
  sharing (org-wide defaults, ownership, role hierarchy, queues, sharing rules, manual shares, portal scoping).
- Audit: every sign-in, failure, lockout, MFA event, password event, user, permission, sharing and metadata change
  is written to `audit_logs`, which a database trigger makes append-only.

## Configuration

See [`backend/.env.example`](backend/.env.example). In staging/production `SECRET_KEY` (≥ 32 chars) is required.
