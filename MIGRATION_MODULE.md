# Sites Migration Module

## Data Model

### `sites`
The portable website definition. Not tied to a server — describes the "what."

| Field | Type | Notes |
|-------|------|-------|
| `id` | int PK | |
| `name` | str(255) | Human label |
| `template` | str(255) | Application template identifier |
| `subdomain` | str(255) | Left side of dot in domain |
| `domain` | str(255) | Right side; `web_url = f"{subdomain}.{domain}"` |
| `prefix` | str(255)? | URL path prefix (e.g. `/api`) |
| `routing_mode` | str `port\|directory` | Controls which fields are required |
| `app_port` | int? | Required if `routing_mode == "port"` |
| `web_root` | str(255) | Base dir on the server (default `/var/www`) |
| `directory` | str(500)? | Subpath under web_root; required if `routing_mode == "directory"` |
| `web_server` | str `apache\|haproxy` | Controls vhost/backend provisioning |
| `notes` | text? | Free text |
| soft-delete | `is_deleted`, `deleted_at`, `deleted_by` | |

### `site_deployments`
Tracks a site placed on a specific server. Keeps history; multiple rows per site.

| Field | Type | Notes |
|-------|------|-------|
| `site_id` | int FK → sites | |
| `server_id` | int FK → servers | Existing server from dropdown |
| `status` | str `staging\|active\|retired\|failed` | |
| `port` | int? | Resolved port on this server (may differ from site.app_port) |
| `directory` | str(500)? | Resolved path on this server |
| `retired_at` | datetime? | Set when status → retired |

No soft-delete — rows are retired, not deleted.

### `site_migrations`
One row per migrate operation. Modelled after `jobs`.

| Field | Type | Notes |
|-------|------|-------|
| `site_id` | int FK → sites | |
| `source_deployment_id` | int? FK → site_deployments | Nullable for first migration |
| `target_server_id` | int FK → servers | The server chosen from dropdown |
| `status` | str `pending\|running\|succeeded\|failed` | |
| `log` | text? | Step-by-step shell output |
| `error_message` | str? | Terminal error if failed |

## Migration Flow (`POST /sites/{id}/migrate`)

1. **Validate** — site exists, body.site_id matches URL.
2. **Find source** — the most recent `active` deployment for the site (nullable).
3. **Create** `SiteMigration` row (status=pending) + write audit log.
4. **`run_migration(session, migration)`**:
   a. Mark migration `running`, set `started_at`.
   b. Load site + target server; resolve SSH via `server.machine_id → Machine → SSHKey → decrypt → open_ssh()`.
   c. Create `SiteDeployment` row (status=`staging`).
   d. Over SSH: `mkdir -p web_root`, `mkdir -p site_dir`.
   e. If `routing_mode == "port"`: probe for a free port with `ss -tlnp`; write Apache vhost **or** log a TODO for HAProxy.
   f. If `routing_mode == "directory"`: write Apache vhost with `DocumentRoot` **or** log TODO for HAProxy.
   g. Best-effort `rsync` from source machine (non-fatal; see TODO #3 below).
   h. Flip `target_deployment.status → active`; `source_deployment.status → retired`.
   i. On any error: `status=failed`, `error_message`, leave source active.
5. Return `MigrationRead`.

## TODOs / Assumptions for Operator Review

### TODO 1 — Apache layout assumes Debian/Ubuntu
`write_apache_vhost` writes to `/etc/apache2/sites-available/` and runs `a2ensite` + `systemctl reload apache2`.  
**RHEL/CentOS/AlmaLinux** use `/etc/httpd/conf.d/` and `systemctl reload httpd`. Add a distro-detection step (check `os_info` field on the Machine) or make the path a configurable field on Site.

### TODO 2 — HAProxy is a no-op stub
`write_haproxy_backend` returns a `TODO:` string and makes no SSH calls.  
HAProxy config modification is complex: the format varies, it may be managed by Ansible/Puppet, and reloading requires careful validation (`haproxy -c -f`). An operator must either: (a) implement a template-based haproxy.cfg generator, or (b) integrate with their config management tool. The stub logs the intent so the migration still completes (as `succeeded` with a TODO note in the log).

### TODO 3 — rsync requires cross-machine SSH access
`_best_effort_rsync` runs `rsync` on the **target** machine pointing back at the source machine IP. This only works if the target has SSH access to the source (i.e., the target's SSH agent can reach the source). This is often not the case. Alternatives: (a) rsync via the operator's machine (three-way transfer), (b) use `scp` with the source private key forwarded, (c) tar-pipe through the operator. The step is marked best-effort — failure is logged but does not abort the migration; source deployment remains active until flip succeeds.

### TODO 4 — `sudo` access on target
The Apache vhost commands use `sudo tee` and `sudo a2ensite`. The SSH user must have passwordless sudo for these commands on the target machine. Add a pre-flight check to the migration that validates sudo access before creating the staging deployment.

### TODO 5 — Apache `mod_proxy` must be enabled
The port-proxy vhost requires `mod_proxy` and `mod_proxy_http`. The migration does not check or enable them. Add `sudo a2enmod proxy proxy_http` to the vhost step.

### TODO 6 — Port conflict window
`find_free_port` probes with `ss -tlnp` then proceeds. There is a TOCTOU window where another process could claim the port between the check and the app starting. For production use, reserve the port atomically (e.g. bind a socket, configure the app, release).

### TODO 7 — Migration runs synchronously
`POST /sites/{id}/migrate` blocks until the migration completes. For long rsync operations this may time out at the reverse proxy. Move `run_migration` to an Arq background task (see `app.workers`) and poll via `GET /sites/migrations/{id}`. The `MigrationRead.status` field already supports this pattern.
