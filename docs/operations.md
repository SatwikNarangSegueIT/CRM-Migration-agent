# Operations runbook

## Components

| Component | Image / command | Notes |
|---|---|---|
| API | `api` image, `uvicorn app.main:app` | Stateless; scale horizontally behind the load balancer. |
| Worker | `api` image, `celery -A app.worker.celery_app worker` | E-mail, marketing sends, imports, index DDL. |
| Scheduler | `api` image, `celery -A app.worker.celery_app beat` | Run exactly **one** instance. |
| Web | `web` image (nginx) | Serves the SPA, proxies `/api` to the API, sets security headers. |
| Database | Neon PostgreSQL (AWS Sydney) | Pooled endpoint for the app, direct endpoint for migrations. |
| Redis | Managed Redis (e.g. ElastiCache) | Celery broker and rate limiting. Not a system of record. |

Uploaded files are stored **in the database** (`stored_files`, up to 25 MB each), so they are covered by the
same backups and point-in-time restore as the records they belong to.

## Deploying

The `Deploy` workflow builds both images, then for **staging** and (after approval) **production**:

1. `alembic upgrade head` against the environment's direct Neon endpoint;
2. `python -m app.cli sync-indexes` (creates field indexes concurrently; safe to re-run);
3. triggers the platform's deploy hook with the new image tags;
4. waits for `GET /api/v1/health/ready`.

Migrations are backwards compatible with the previous release (expand / contract), so the old pods keep
working while new ones roll out. Roll back by redeploying the previous image tag; only roll back a
migration (`alembic downgrade -1`) when the release notes say it is safe.

Required production settings (see `backend/.env.example`): `APP_ENV=production`, `SECRET_KEY` (≥ 32 chars,
from the secrets manager), `DATABASE_URL` (pooled), `DATABASE_URL_DIRECT`, `REDIS_URL`, `PUBLIC_APP_URL`,
`EMAIL_BACKEND=smtp` and SMTP settings. Start-up refuses weak keys, disabled MFA or insecure cookies.

### Statement timeout on the pooled endpoint

`DB_STATEMENT_TIMEOUT_MS` (default 30 s) is applied automatically on direct connections. Neon's pooled
endpoint does not accept startup options, so set it once on the application role:

```sql
ALTER ROLE app_user SET statement_timeout = '30s';
```

Reports additionally run with a 15-second limit and a row cap.

## Backups and restore

* **Neon point-in-time restore (PITR):** keep the history retention at 7 days minimum (30 days
  recommended on the Scale plan). Restore by creating a branch at a timestamp, verifying it, then promoting it
  or repointing `DATABASE_URL`.
* **Nightly logical backup:** `pg_dump --format=custom --no-owner "$DATABASE_URL_DIRECT"` from a scheduled
  job, encrypted and kept in a separate account / region for 35 days (monthly copies for 7 years if required
  by your record-keeping obligations).
* **Restore drill (quarterly):** restore the latest dump into a new Neon branch, run
  `alembic current` and the smoke test, open a few records and a file, then delete the branch. Record the
  time taken (target RTO 4 h, RPO 15 min with PITR).

## Scheduled jobs (Celery beat)

| Job | Schedule | What it does |
|---|---|---|
| `marketing.dispatch_due` | every minute | Sends scheduled e-mail campaigns. |
| `activities.reminders` | every minute | Task and event reminders (in-app + e-mail). |
| `service.escalate_cases` | every 5 minutes | Flags cases past their resolution SLA and notifies owners/queues. |
| `reports.scheduled` | every 15 minutes | E-mails subscribed reports. |
| `maintenance.purge` | daily 03:00 | Purges the recycle bin (30 days), deleted fields (15 days) and applies per-object retention policies. |
| `packs.daily` | daily 06:00 | Industry-pack jobs (e.g. visa / passport / sponsorship expiry reminders). |

Check the worker logs for `Task ... succeeded`; a job that has not run in 2 × its interval should alert.

## Data retention and privacy requests

* **Retention policies** (Setup → Data Retention): per object, records not changed for *N* years move to the
  recycle bin nightly and are purged 30 days later. Object rules can veto deletion (e.g. matters with
  client-account transactions are kept).
* **Subject access request:** open the contact or lead → *Export Personal Data* (needs Manage Users).
  Downloads a JSON file with the record, its history, linked records, consents and e-mail history.
* **Erasure request:** *Erase Personal Data* anonymises the person's personal fields, removes notes, files and
  change history, deactivates any portal account and keeps business records without the personal details.
  Erasure is blocked while a legal retention obligation applies (client-account ledger). Both actions are
  written to the audit log.
* The audit log is append-only (database trigger) and is not purged automatically.

## Monitoring

* Liveness `GET /api/v1/health/live`, readiness `GET /api/v1/health/ready` (checks database and Redis).
* Logs are JSON (`LOG_JSON=true`) with a `request_id` on every line; the same id is returned in the
  `X-Request-ID` header and in error bodies, so a user's error report can be traced.
* Alert on: 5xx rate > 1 %, p95 latency > 1 s for 10 minutes, readiness failures, worker queue length,
  failed logins spike (`LOGIN_FAILED` audit entries), Neon compute at max.

## Performance

Target (plan v3 §14): list view p95 < 400 ms with 1 M records per object at 50 concurrent users.
Procedure: [`loadtest/list_views.js`](../loadtest/list_views.js) (k6) against a disposable branch filled with
`python -m app.cli seed-load --count 1000000`. Mark fields used in list filters and sorts as **indexed**
(Object Manager) so the engine creates expression indexes.

## Incident checklist

1. Check readiness, worker logs and Neon status.
2. Suspected breach: rotate `SECRET_KEY` (signs sessions and encrypts MFA secrets / encrypted fields — plan a
   re-encryption before rotating), revoke sessions (`Users → Sign out everywhere`), review the audit log by IP and
   user, and follow the Notifiable Data Breaches scheme (OAIC) timelines.
