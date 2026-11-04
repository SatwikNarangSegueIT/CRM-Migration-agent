# Security and compliance controls

Mapping of plan v3 section 14 (and sections 9–10) to the implementation and the tests that verify it.

| Control | Implementation | Verified by |
|---|---|---|
| Sessions | Opaque 256-bit token, only the SHA-256 hash stored; HttpOnly, SameSite=Lax, Secure outside dev; 12 h absolute / 60 min idle; revoked on password, profile or role change and deactivation | `tests/test_auth_api.py` |
| CSRF | Per-session token in `X-CSRF-Token` on every unsafe request, plus an Origin allow-list | `tests/test_auth_api.py` |
| Passwords | Argon2id; ≥ 12 chars, common / personal passwords rejected; lockout after 5 failures | `tests/test_auth_api.py`, `tests/test_security.py` |
| MFA | TOTP with replay protection and recovery codes; mandatory for staff in production (start-up check) | `tests/test_auth_api.py`, `tests/test_config.py` |
| Rate limits | Redis fixed windows on sign-in, MFA, password reset, invitations and public forms | `tests/test_auth_api.py` |
| Authorisation | Four layers on every request: system permissions, object permissions, field-level security, record sharing (OWD, role hierarchy, queues, manual shares, sharing rules); invisible records return 404 | `tests/test_permissions.py` (plan matrix), `tests/test_records_engine.py` |
| Portal isolation | Portal users can't call staff APIs and only see records tied to their contact/account; staff can't use portal APIs | `tests/test_apps.py::test_customer_portal` |
| Query safety | Filters are parsed into an AST and compiled against validated metadata; all values bound; DDL names validated | `tests/test_records_engine.py` |
| Audit | Append-only `audit_logs` (database trigger) for sign-ins, user, permission, sharing, metadata, record, export and privacy actions | `tests/test_admin_api.py` |
| Field history | Tracked fields write old/new values; encrypted values are never recorded | `tests/test_records_engine.py` |
| Encryption | Encrypted field type (Fernet, key derived from `SECRET_KEY`); MFA secrets encrypted; TLS to Neon (`sslmode=require`) | `tests/test_apps.py::test_migration_agency_pack` |
| Files | Stored in the database; 25 MB limit; executable types blocked; malware-scan hook (EICAR rejected); `nosniff`, attachment disposition | `tests/test_hardening.py` |
| Exports | CSV export and report export need *Export Data*; audited; spreadsheet formula injection neutralised | `tests/test_apps.py` |
| Privacy | Consent records and unsubscribe; subject-access export; erasure (anonymise) with legal-hold check; per-object retention | `tests/test_hardening.py`, `tests/test_apps.py` |
| Marketing law | Consent filtering, unsubscribe link and sender identity in every e-mail (Spam Act 2003); signed click redirects (no open redirect) | `tests/test_apps.py` |
| Security headers | CSP, HSTS (staging/production), X-Frame-Options, Referrer-Policy, Permissions-Policy (API middleware and nginx) | `tests/test_errors_and_middleware.py`, CI image smoke test |
| Dependencies | `pip-audit` and `npm audit` on every PR; Trivy image scan, gitleaks and OWASP ZAP baseline weekly | `.github/workflows/ci.yml`, `security.yml` |
| Accessibility | axe-core WCAG 2.1 AA checks on the main screens | `frontend/src/test/a11y.test.tsx` |

## Known limitations / residual risks

* Encrypted fields use a key derived from `SECRET_KEY`; rotating it requires re-encrypting those values.
* The malware-scan hook only rejects the EICAR test signature; connect a scanner (e.g. ClamAV) in
  `app/routers/workspace.py::_scan` before accepting files from the public.
* Public web-to-lead/case forms use a honeypot and rate limits; add a CAPTCHA provider in
  `app/routers/public.py::_verify_human` if spam is observed.
* Penetration testing by an independent party is recommended before go-live.
