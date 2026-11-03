# Neon setup

MigrateCRM uses [Neon](https://neon.com) serverless PostgreSQL.

## 1. Create the project

1. In the Neon console create a project in **AWS Asia Pacific (Sydney) – `aws-ap-southeast-2`**.
   The region cannot be changed later; Sydney keeps client data in Australia.
2. Postgres version: 16 or later.
3. Create branches:
   - `main` – production (set compute to **always on**, i.e. disable scale-to-zero, to avoid cold starts).
   - `staging` – branched from `main`.
   - Developers can create personal `dev/<name>` branches (scale-to-zero is fine there).

## 2. Connection strings

Each branch has two endpoints. Copy both from **Connect** in the console:

| Variable | Endpoint | Used by |
|---|---|---|
| `DATABASE_URL` | **Pooled** (host contains `-pooler`) | API and Celery workers |
| `DATABASE_URL_DIRECT` | **Direct** | Alembic migrations, admin scripts |

Keep `?sslmode=require` (and `channel_binding=require` if Neon includes it) on both URLs.
The app converts `postgresql://` to the psycopg 3 driver automatically.

Pooled connections go through PgBouncer in transaction mode, so the app:
- disables psycopg prepared statements automatically when the host contains `-pooler`
  (override with `DATABASE_DISABLE_PREPARED_STATEMENTS=true|false`);
- uses `pool_pre_ping` and a 300 s `pool_recycle`, because Neon can close idle connections;
- never relies on session state (`LISTEN/NOTIFY`, session advisory locks, `SET` without `LOCAL`).

## 3. Run migrations

```bash
cd backend
DATABASE_URL_DIRECT="postgresql://...direct-host.../neondb?sslmode=require" uv run alembic upgrade head
```

## 4. CI preview branches

`.github/workflows/neon-preview.yml` creates a branch `preview/pr-<number>` for every pull request,
runs migrations (direct endpoint) and the backend tests (pooled endpoint), and deletes the branch when
the PR closes. Configure in GitHub → Settings → Secrets and variables → Actions:

| Kind | Name | Value |
|---|---|---|
| Secret | `NEON_API_KEY` | Neon API key |
| Variable | `NEON_PROJECT_ID` | Neon project id |
| Variable | `NEON_DB_USER` | Database role, e.g. `neondb_owner` |
| Variable | `NEON_DB_NAME` | Database name (optional, default `neondb`) |

The workflow is skipped until `NEON_PROJECT_ID` is set, and for pull requests from forks.

## 5. Backups

Neon point-in-time restore covers short-term recovery. For long-term retention (7-year record keeping),
schedule a nightly `pg_dump` of the direct endpoint to encrypted S3 storage in Sydney (added in phase 7).
