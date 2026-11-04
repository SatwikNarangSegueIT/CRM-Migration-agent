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

## Upgrading the existing Neon database to v4 (multi-tenant)

The single-firm database (public schema at revision `b51c2e7a9d40`) is upgraded by
[`deploy/neon_upgrade_v4.sql`](../deploy/neon_upgrade_v4.sql). The script:
- brings the public schema to the latest revision;
- creates the `platform` schema (tenants, user directory, sign-up requests, warm pool);
- registers the existing data as the first workspace (`main`). No firm data moves.

The script stops if the database is at another revision, so running it twice is harmless. Take a Neon
branch first, then run it against the direct (non-pooled) connection:

```bash
psql "$DATABASE_URL_DIRECT" -v ON_ERROR_STOP=1 -1 -f deploy/neon_upgrade_v4.sql
```

`python -m app.cli migrate` from the deployed API does the same thing.

## Upgrading to v5 (sign-up fixes, domain layouts)

Run [`deploy/neon_upgrade_v5.sql`](../deploy/neon_upgrade_v5.sql) once, in the Neon SQL Editor or with
`psql "$DATABASE_URL_DIRECT" -v ON_ERROR_STOP=1 -1 -f deploy/neon_upgrade_v5.sql`. It is safe to run again.
It brings the `public` schema to `c3f1d2e8a901` if it is behind, repairs "Contact Person People" labels and
gives every profession workspace related lists that match its apps (Matters on a client instead of
Opportunities and Cases); related lists an administrator already changed are left alone. The same is done by
`python -m app.cli refresh-domain-layouts`.

## Upgrading to v6 (e-mail settings)

Run [`deploy/neon_upgrade_v6.sql`](../deploy/neon_upgrade_v6.sql) once (after v5), in the Neon SQL Editor or
with `psql "$DATABASE_URL_DIRECT" -v ON_ERROR_STOP=1 -1 -f deploy/neon_upgrade_v6.sql`. It adds
`platform.settings`, where e-mail settings saved through the API are kept. Safe to run again;
`python -m app.cli migrate` does the same.

## Profession forms and layouts (automatic)

When the API starts it brings every profession workspace's forms up to date: the profession's own client and
organisation fields (passport, TFN, sponsorship, ID checks, ACN…) on the layouts, sales-only fields taken
off, lifecycle fields (stage, decision, lodgement and settlement details) left off create forms, hints on fields
the system fills in, and related lists that match the apps. It runs once per workspace (recorded as
`forms_version` in the `workspace` setting), is safe with several API processes, and needs no SQL.
`python -m app.cli refresh-domain-layouts` re-applies it on demand. Fields taken off a layout aren't
deleted; an administrator can put them back in Setup → Object Manager.

## Sign-up checklist

Sign-up creates a schema per firm and e-mails a confirmation link, so it needs more than the rest of the app.
`GET /api/v1/platform/status` (below) checks all of it and says what to fix.

- **E-mail that actually leaves.** With `EMAIL_BACKEND=console` (the default, and what `docker-compose.yml`
  uses) e-mails are only written to the log. Set up Zoho (below). Outside production, with e-mail not set up,
  `SIGNUP_EMAIL_VERIFICATION=auto` creates the workspace straight away instead, so sign-up still works for
  testing; production always requires the confirmation e-mail.
- **No worker needed.** `EMAIL_DELIVERY=auto` (default) hands e-mail to the Celery worker only when one is
  running (it sends a heartbeat); otherwise the API sends it, and a failed confirmation e-mail is reported to
  the person signing up instead of disappearing. Imports and index builds fall back the same way.
- **`DATABASE_URL_DIRECT`** set to the *direct* Neon endpoint (no `-pooler` in the host): new workspaces build
  faster on it. Through the pooler also works.
- **`PUBLIC_APP_URL`** is the address people open (links in e-mails use it).
- The **warm pool** (`SIGNUP_WARM_POOL_SIZE`, default 2) keeps ready-made workspaces so confirming takes about a
  second. The API refills it at start-up and after each sign-up.
- `PASSWORD_BREACH_CHECK=true` (default) rejects passwords found in known breaches via Have I Been Pwned
  (only 5 characters of the SHA-1 hash leave the server; fails open if the service can't be reached).

## E-mail delivery (Zoho)

**In the environment** (defaults), see [`backend/.env.production.example`](../backend/.env.production.example):
`EMAIL_BACKEND=smtp`, `SMTP_HOST` (Zoho India: `smtppro.zoho.in` for paid organisation accounts, `smtp.zoho.in`
for personal ones; other data centres: `smtp.zoho.com` or, for paid
organisation accounts, `smtppro.zoho.com` on zoho.com), `SMTP_PORT=465` + `SMTP_SECURITY=ssl` (or 587 +
`starttls`), `SMTP_USERNAME` = the full mailbox, `SMTP_PASSWORD` = an application-specific password when the
Zoho account uses two-factor sign-in, and `EMAIL_FROM` = that mailbox or one of its aliases. Zoho shows the
exact host in Zoho Mail -> Settings -> Mail Accounts -> IMAP/SMTP.

If your host blocks outbound SMTP ports, use **Zoho ZeptoMail** over HTTPS instead: `EMAIL_BACKEND=zeptomail`,
`ZEPTOMAIL_TOKEN` (ZeptoMail -> Mail Agents -> SMTP/API -> Send Mail token) and, for an account outside the
US data centre, the `ZEPTOMAIL_API_URL` ZeptoMail shows.

**Through the API** (no redeploy; overrides the environment, takes effect within 20 seconds everywhere).
Only System Administrators of the operator workspace (`PLATFORM_OPERATOR_WORKSPACE`, default the first
workspace, `main`) can use it. Passwords and tokens are stored encrypted with `SECRET_KEY` and never returned.

```bash
APP=https://crm.yourfirm.com.au
# 1. Sign in (add the two-step code with /auth/mfa/verify if it asks for one)
curl -s -c jar.txt -H "Origin: $APP" -H 'Content-Type: application/json' \
  "$APP/api/v1/auth/login" -d '{"email":"you@yourfirm.com.au","password":"YOUR_PASSWORD"}'
CSRF=$(awk '$6=="crm_csrf"{print $7}' jar.txt)
curl -s -b jar.txt -c jar.txt -H "Origin: $APP" -H "X-CSRF-Token: $CSRF" -H 'Content-Type: application/json' \
  "$APP/api/v1/auth/mfa/verify" -d '{"code":"123456"}'

# 2. Save the Zoho settings
curl -s -b jar.txt -X PUT -H "Origin: $APP" -H "X-CSRF-Token: $CSRF" -H 'Content-Type: application/json' \
  "$APP/api/v1/platform/email" -d '{
    "provider": "smtp",
    "from_name": "Meridian CRM",
    "from_email": "no-reply@yourfirm.com.au",
    "smtp_host": "smtppro.zoho.in",
    "smtp_port": 465,
    "smtp_security": "ssl",
    "smtp_username": "no-reply@yourfirm.com.au",
    "smtp_password": "ZOHO_APP_PASSWORD"
  }'

# 3. Send a test e-mail (reports the server's reason in plain words if it fails)
curl -s -b jar.txt -H "Origin: $APP" -H "X-CSRF-Token: $CSRF" -H 'Content-Type: application/json' \
  "$APP/api/v1/platform/email/test" -d '{"to":"you@yourfirm.com.au"}'

# 4. Check everything sign-up depends on
curl -s -b jar.txt "$APP/api/v1/platform/status"
```

| Endpoint | Does |
|---|---|
| `GET /api/v1/platform/email` | Current settings (secrets shown only as set / not set), the environment defaults and Zoho host suggestions. |
| `PUT /api/v1/platform/email` | Save settings. `provider`: `smtp`, `zeptomail` or `console`. A blank `smtp_password` / `zeptomail_token` keeps the saved one. Audited. |
| `DELETE /api/v1/platform/email` | Go back to the environment settings. |
| `POST /api/v1/platform/email/test` | Send a test to `to`, with the saved settings or unsaved ones in `settings`. |
| `GET /api/v1/platform/status` | Database versions, direct URL, e-mail, sign-up mode, worker, warm pool, link address: each ok / warn / error with what to do. |

Outside production the interactive API docs at `/api/v1/docs` let you call these from the browser after
signing in. A Setup screen for the same settings is planned.

Common Zoho errors, as the test reports them: *rejected the username or password (535)*: use an
application-specific password; *won't send from …*: `from_email` must be the mailbox or an alias;
*timed out / couldn't connect*: wrong host or port, or the host blocks SMTP (use ZeptoMail).

## Deploying

The `Deploy` workflow builds both images, then for **staging** and (after approval) **production**:

1. `python -m app.cli migrate` against the environment's direct Neon endpoint (the platform schema, then
   every tenant schema and the warm pool);
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

- Host the API in the **same region as Neon** (AWS ap-southeast-2, Sydney). Each API request makes a few
  SQL round trips; at 150 ms per trip from another continent a page feels slow whatever the code does.
- On Neon, turn off **scale to zero** for production (or raise the suspend timeout): waking a suspended
  compute adds 0.5-2 s to the first request. The API also opens its first connections at start-up.
- `WEB_CONCURRENCY` sets uvicorn workers (about 2 per CPU). Responses are gzip-compressed by the API and
  nginx; static assets are cached for a year (file names are content-hashed).

Target (plan v3 §14): list view p95 < 400 ms with 1 M records per object at 50 concurrent users.
Procedure: [`loadtest/list_views.js`](../loadtest/list_views.js) (k6) against a disposable branch filled with
`python -m app.cli seed-load --count 1000000`. Mark fields used in list filters and sorts as **indexed**
(Object Manager) so the engine creates expression indexes.

## Incident checklist

1. Check readiness, worker logs and Neon status.
2. Suspected breach: rotate `SECRET_KEY` (signs sessions and encrypts MFA secrets / encrypted fields — plan a
   re-encryption before rotating), revoke sessions (`Users → Sign out everywhere`), review the audit log by IP and
   user, and follow the Notifiable Data Breaches scheme (OAIC) timelines.
