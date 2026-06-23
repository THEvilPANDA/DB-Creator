# DB Creator — Kanban Board (Enterprise Architecture v3)

**Last Updated**: 2026-06-24
**Current Focus**: Phase 1 — Server Management + Capacity + Placement

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

## 🟠 To Do (Phase 2 — Naming + Templates)

- [ ] Naming engine: resolve pattern, collision detection against live DB list
- [ ] Reserved name enforcement on job submission
- [ ] Database template seeding (Standard, AI/RAG, ERP, Analytics, Custom)
- [ ] Request template: auto-populate job fields when `request_template_id` provided
- [ ] `GET /api/v1/naming-profiles/{id}/preview` endpoint

---

## 🔵 To Do (Phase 3 — Full Creator Flow)

- [ ] Full job submission flow: capacity gate → placement → naming → approval → Arq enqueue
- [ ] `PostgreSQLProvisioner` wired into worker (server credentials from DB)
- [ ] SSE endpoint: `GET /api/v1/jobs/{id}/events` (real-time status stream)
- [ ] Connection helpers in job response (URI, env vars, PgAdmin/DBeaver config)
- [ ] IaC export: YAML + Terraform snippets in `CreationLog`

---

## 🟣 To Do (Phase 4 — Events + Audit)

- [ ] `AuditLog` writes on every state change (job submit, approval, cancel, delete)
- [ ] Domain event consumers (placeholder Slack/Teams/SIEM hooks)
- [ ] IaC export generation on provisioning success

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
