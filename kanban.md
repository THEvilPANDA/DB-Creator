# DB Creator — Kanban Board (Enterprise Architecture v3)

**Last Updated**: 2026-06-24
**Current Focus**: Phase 5 — Dashboard + Observability

---

## ✅ Done (Phase 0 — Foundation)

- [x] Project skeleton + Docker Compose (Postgres 16 + Redis 7)
- [x] pydantic-settings config + async SQLAlchemy engine + `get_session` dependency
- [x] ORM models: `Server`, `NamingProfile`, `DatabaseTemplate`, `RequestTemplate` (with soft-delete)
- [x] ORM models: `Job`, `ApprovalRequest`, `CreationLog`, `AuditLog`
- [x] Alembic async setup + initial migration (all 8 tables)
- [x] Pydantic v2 request/response schemas for all entities
- [x] Abstract `DatabaseProvisioner` ABC + spec dataclasses (`DatabaseSpec`, `UserSpec`, etc.)
- [x] `PostgreSQLProvisioner` (asyncpg-backed full implementation)
- [x] Service layer: `EventPublisher`, `ApprovalService`, `NamingService`, `CapacityService`, `PlacementService`
- [x] FastAPI app with CORS, lifespan, OpenAPI auto-docs (`/docs`)
- [x] Health endpoints: `/health`, `/health/database`, `/health/queue`
- [x] Servers API: `POST/GET/PUT/DELETE /api/v1/servers` + `GET /{id}/capacity`
- [x] Naming Profiles API: full CRUD with soft delete
- [x] Database Templates API: full CRUD with soft delete
- [x] Request Templates API: full CRUD with soft delete
- [x] Jobs API: submit (with auto-approval for dev/staging), get, cancel, approve
- [x] History API: paginated creation log
- [x] Arq worker: `provision_database` task + `WorkerSettings`
- [x] Domain events: `DatabaseRequested`, `DatabaseProvisioningStarted`, `DatabaseProvisioningCompleted`, `DatabaseProvisioningFailed`
- [x] 23 unit tests passing (models, services, provisioner)

---

## ✅ Done (Phase 1 — Server Management + Capacity)

- [x] `admin_dsn` field on Server (Alembic migration b1c2d3e4f5a6); `has_admin_dsn` in API response
- [x] Live capacity metrics via `PostgreSQLProvisioner.get_capacity()` wired into `GET /servers/{id}/capacity` (5s timeout, graceful fallback to `health=unknown`)
- [x] `GET /api/v1/servers/health-summary` — aggregate health across all servers
- [x] Placement strategies: `least_dbs`, `round_robin`, `environment_default` (default)
- [x] Capacity gate on job submission: blocks if health=critical OR connections ≥ 90% of max
- [x] Auto-placement on job submission when `server_id` is omitted
- [x] Integration test stubs in `tests/api/test_servers.py`

---

## ✅ Done (Phase 2 — Naming + Templates)

- [x] `NamingService.apply_profile()` — resolves pattern + applies prefix/suffix/separator
- [x] `NamingService.generate()` — async, validates name, detects + resolves collisions (up to 99 retries)
- [x] `GET /api/v1/naming-profiles/{id}/preview` — resolves pattern with given context, returns errors
- [x] Job submission: applies naming profile (with live collision check via provisioner if server has admin_dsn)
- [x] Job submission: request template auto-fill (template fills blanks; caller values win)
- [x] `POST /api/v1/admin/seed` — idempotent seeder for 5 DB templates + 3 naming profiles
- [x] 11 new unit tests for naming service (34 total passing)

---

## ✅ Done (Phase 3 — Full Creator Flow)

- [x] Arq pool created in FastAPI lifespan (graceful degradation if Redis unavailable)
- [x] Auto-approval + manual approval both enqueue `provision_database` task to Arq
- [x] Worker: `PostgreSQLProvisioner` fully wired — create_user → create_database → grant_permissions → enable_extensions
- [x] Worker: writes `CreationLog` with `connection_uri`, `iac_yaml`, `iac_terraform`
- [x] `GET /api/v1/jobs/{id}/events` — SSE stream (1s polling, ends on terminal state, 5-min timeout)
- [x] `GET /api/v1/jobs/{id}/connection` — returns URI, env vars, IaC snippets after provisioning
- [x] `app/services/iac.py` — YAML + Terraform snippet generators
- [x] 5 IaC unit tests (39 total passing)

---

## ✅ Done (Phase 4 — Events + Audit)

- [x] `AuditLog` writes on every state change: job submit, approval decided, job cancel, provision start/complete/fail, credential access
- [x] `write_audit()` helper in `app/services/audit.py` (used by jobs API + worker)
- [x] Domain event consumers: `app/services/consumers.py` — placeholder log-based handlers for all 4 domain events; registered at startup via `register_consumers()`
- [x] `GET /jobs/{id}/connection` now writes AuditLog on every credential access
- [x] SSE sanitized: raw `error_message` no longer leaks into stream (returns `"error": true`; full message via `GET /jobs/{id}`)
- [x] Security finding acknowledged: IDOR on connection + SSE endpoints flagged for Phase 7 (needs `get_current_user`); Phase 7 TODO comments in code
- [x] IaC export generation: done in Phase 3
- [x] 4 new consumer tests (43 unit tests total passing)

---

## 🟢 To Do (Phase 5 — Dashboard + Observability)

- [ ] OpenTelemetry instrumentation
- [ ] Prometheus metrics endpoint `/metrics`: provisioning duration, failure rate, queue length, success rate
- [ ] Grafana dashboard templates
- [ ] Full-text search across jobs/servers/templates
- [ ] History with advanced filters (environment, expiration status, template, approver)
- [ ] Frontend components: Dashboard, Job History, Server List

---

## 🔵 To Do (Phase 6 — Settings Management UI)

- [ ] Settings pages for Servers, Naming Profiles, Database Templates, Request Templates
- [ ] Quota fields exposed in forms
- [ ] API-backed admin actions for approval policy configuration

---

## 🔴 Backlog (Future)

- Multi-engine support (MySQL, MongoDB) via abstract interface
- Full approval UI + multi-stage approval policies
- Secret rotation actions + quota enforcement
- Resource quota enforcement (connection/storage/schema limits)
- Credential encryption at rest (Fernet) for `connection_uri` in `CreationLog`
- Event consumers (Slack/Teams notifications, ERP sync, SIEM)
- SSO / SAML / LDAP integration
- Terraform Provider / CLI / GitHub Actions official support
- JWT auth + refresh tokens + rate limiting + CSRF (Phase 7)
- Performance: connection pooling, caching, query optimization (Phase 7)
