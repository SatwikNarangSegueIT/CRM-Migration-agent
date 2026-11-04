-- Meridian CRM: database changes for the e-mail settings release (run once; safe to run again).
--
-- Paste into the Neon SQL Editor (it runs as one transaction) or:
--   psql "$DATABASE_URL_DIRECT" -v ON_ERROR_STOP=1 -1 -f deploy/neon_upgrade_v6.sql
--
-- Run deploy/neon_upgrade_v5.sql first if you haven't. This script adds platform.settings, where the
-- outgoing e-mail settings saved in Setup -> E-mail & Sign-up are kept (the SMTP password and ZeptoMail token
-- are stored encrypted with SECRET_KEY). Same result as platform migration p0003 (`python -m app.cli migrate`).
-- Until it has run, the app keeps working with the e-mail settings from its environment variables.

CREATE TABLE IF NOT EXISTS platform.settings (
    key VARCHAR(60) NOT NULL,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_by VARCHAR(254),
    CONSTRAINT pk_settings PRIMARY KEY (key)
);

UPDATE platform.alembic_version SET version_num = 'p0003' WHERE version_num = 'p0002';

-- Expect: one row, p0003.
SELECT version_num AS platform_version FROM platform.alembic_version;
