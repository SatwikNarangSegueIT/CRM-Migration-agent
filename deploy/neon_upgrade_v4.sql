-- Meridian CRM: upgrade the existing Neon database to plan v4 (multi-tenant).
--
-- From: public schema at Alembic revision b51c2e7a9d40 (single firm).
-- To:   public schema at 4a708a753f1b + the shared "platform" schema (p0002), with the existing data
--       registered as the first workspace ("main"). No firm data is moved or changed.
--
-- Generated with `alembic upgrade --sql` (tenant and platform environments) plus the statements of
-- app.db.migrate.ensure_first_tenant. Equivalent to running `python -m app.cli migrate` from the
-- deployed API. Review, then run in one go against the DIRECT (non-pooled) connection:
--
--   psql "$DATABASE_URL_DIRECT" -v ON_ERROR_STOP=1 -1 -f deploy/neon_upgrade_v4.sql
--
-- Afterwards `python -m app.cli migrate` applies later migrations (e.g. c3f1d2e8a901, date-field indexes).
--
-- Take a Neon branch (or rely on point-in-time restore) first. The script stops if the database is not
-- at the expected revision.

DO $$
BEGIN
  IF (SELECT version_num FROM public.alembic_version) <> 'b51c2e7a9d40' THEN
    RAISE EXCEPTION 'Expected public schema at revision b51c2e7a9d40, found %', (SELECT version_num FROM public.alembic_version);
  END IF;
END $$;

-- ---------------------------------------------------------------- tenant schema (public)

-- Running upgrade b51c2e7a9d40 -> 4a708a753f1b

ALTER TABLE metadata_revision ADD COLUMN security BIGINT DEFAULT '1' NOT NULL;

INSERT INTO metadata_revision (id, revision, security) VALUES (1, 1, 1) ON CONFLICT (id) DO NOTHING;

UPDATE alembic_version SET version_num='4a708a753f1b' WHERE alembic_version.version_num = 'b51c2e7a9d40';


-- ---------------------------------------------------------------- platform schema
CREATE SCHEMA IF NOT EXISTS platform;


CREATE TABLE platform.alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> p0001

CREATE SCHEMA IF NOT EXISTS extensions;

CREATE TABLE platform.tenants (
    id UUID NOT NULL, 
    slug VARCHAR(41) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    domain VARCHAR(40) DEFAULT 'general' NOT NULL, 
    schema_name VARCHAR(63) NOT NULL, 
    status VARCHAR(20) DEFAULT 'active' NOT NULL, 
    region VARCHAR(40) DEFAULT 'ap-southeast-2' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    verified_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_tenants PRIMARY KEY (id), 
    CONSTRAINT ck_tenants_ck_tenants_slug_format CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,40}$'), 
    CONSTRAINT ck_tenants_ck_tenants_status_valid CHECK (status IN ('active', 'provisioning', 'suspended', 'deleted')), 
    CONSTRAINT uq_tenants_slug UNIQUE (slug), 
    CONSTRAINT uq_tenants_schema_name UNIQUE (schema_name)
);

CREATE TABLE platform.user_directory (
    tenant_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    CONSTRAINT pk_user_directory PRIMARY KEY (tenant_id, user_id), 
    CONSTRAINT fk_user_directory_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES platform.tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_user_directory_email ON platform.user_directory (email);

INSERT INTO platform.alembic_version (version_num) VALUES ('p0001') RETURNING platform.alembic_version.version_num;

-- Running upgrade p0001 -> p0002

CREATE TABLE platform.signup_requests (
    id UUID NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    firm_name VARCHAR(200) NOT NULL, 
    domain VARCHAR(40) NOT NULL, 
    abn VARCHAR(20), 
    password_hash VARCHAR(255), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    verified_at TIMESTAMP WITH TIME ZONE, 
    tenant_id UUID, 
    CONSTRAINT pk_signup_requests PRIMARY KEY (id), 
    CONSTRAINT fk_signup_requests_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES platform.tenants (id) ON DELETE SET NULL, 
    CONSTRAINT uq_signup_requests_token_hash UNIQUE (token_hash)
);

CREATE INDEX ix_signup_requests_email ON platform.signup_requests (email);

CREATE TABLE platform.warm_schemas (
    schema_name VARCHAR(63) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_warm_schemas PRIMARY KEY (schema_name)
);

UPDATE platform.alembic_version SET version_num='p0002' WHERE platform.alembic_version.version_num = 'p0001';


-- ---------------------------------------------------------------- existing data = first workspace

INSERT INTO platform.tenants (id, slug, name, domain, schema_name, status, verified_at)
SELECT gen_random_uuid(), 'main',
       COALESCE((SELECT NULLIF(value->>'legal_name', '') FROM public.org_settings WHERE key = 'company'), 'My firm'),
       'migration', 'public', 'active', now()
WHERE NOT EXISTS (SELECT 1 FROM platform.tenants WHERE schema_name = 'public');

INSERT INTO platform.user_directory (tenant_id, user_id, email)
SELECT t.id, u.id, u.email FROM public.users u CROSS JOIN platform.tenants t
WHERE t.schema_name = 'public'
ON CONFLICT DO NOTHING;
