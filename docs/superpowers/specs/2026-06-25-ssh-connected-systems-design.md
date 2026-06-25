# SSH-Connected Systems Fleet Management — Design Spec

**Date:** 2026-06-25  
**Status:** Approved  
**Scope:** Phase 1 — System inventory, SSH key management, DB provisioning via SSH tunnel. Web terminal deferred to a future phase.

---

## 1. Overview

Add the ability for server admins to register and monitor local company machines via SSH, discover machines through network scanning, detect database engines running on those machines, and provision databases through an SSH tunnel — all from the existing DBCreator UI.

The feature introduces two new first-class entities (`SSHKey`, `Machine`) and one lightweight change to the existing `Server` model (`machine_id` FK). All existing direct-DSN connections remain fully unchanged.

---

## 2. Data Models

### 2.1 `SSHKey` — table: `ssh_keys`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `name` | varchar(255) | Display label, unique |
| `username` | varchar(255) | SSH login user (e.g. `ubuntu`, `root`) |
| `encrypted_private_key` | text | Fernet-encrypted PEM; never returned by API |
| `passphrase_encrypted` | text nullable | Fernet-encrypted passphrase if key is protected |
| `created_at` | datetime | |

**Key invariant:** Raw key material is validated (parsed) on upload and then encrypted immediately. No API endpoint ever returns key bytes — only `id`, `name`, `username`, `created_at`.

### 2.2 `Machine` — table: `machines`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `ip` | varchar(45) | IPv4 or IPv6 |
| `hostname` | varchar(255) nullable | Resolved on first successful SSH connect |
| `label` | varchar(255) nullable | Friendly admin-assigned name |
| `ssh_port` | int | Default 22 |
| `ssh_key_id` | int FK → ssh_keys | Required |
| `os_info` | text nullable | JSON string, gathered via `uname -a` on connect |
| `host_fingerprint` | text nullable | SHA-256 fingerprint of host public key, stored on first connect; used for subsequent verification |
| `status` | varchar(20) | `unknown` \| `online` \| `offline` |
| `last_checked_at` | datetime nullable | |
| `created_at` | datetime | |
| `is_deleted` | bool | Soft-delete |
| `deleted_at` | datetime nullable | |

### 2.3 `Server` model change

Add one nullable column: `machine_id` (int FK → machines). When set, the provisioner tunnels through that machine. When null, direct-DSN behaviour is unchanged.

---

## 3. API Routes

### 3.1 SSH Keys — `/api/v1/ssh-keys`

| Method | Path | Description |
|---|---|---|
| `POST` | `/` | Upload new key. Body: `name`, `username`, `private_key` (PEM text), `passphrase` (optional). Validates key parses before storing. |
| `GET` | `/` | List all keys. Returns `id`, `name`, `username`, `created_at` only. |
| `DELETE` | `/{key_id}` | Delete key. Returns 409 if any Machine references it. |

### 3.2 Machines — `/api/v1/machines`

| Method | Path | Description |
|---|---|---|
| `POST` | `/` | Manually register a machine. Body: `ip`, `ssh_port`, `ssh_key_id`, `label`. |
| `GET` | `/` | List all non-deleted machines with status. |
| `GET` | `/{machine_id}` | Single machine detail. |
| `PUT` | `/{machine_id}` | Update `label`, `ssh_key_id`, `ssh_port`. |
| `DELETE` | `/{machine_id}` | Soft-delete. Returns 409 if any Server references it. |
| `POST` | `/{machine_id}/check` | Test SSH connectivity. Updates `status`, `hostname`, `os_info`, `last_checked_at`. |
| `POST` | `/{machine_id}/detect-engines` | SSH in, scan ports 5432/3306/27017/6333. Returns list of `{port, engine, open}`. |
| `POST` | `/scan` | Network scan. Body: `cidr`, `method: "ping" \| "port22" \| "both"`. Returns discovered IPs as an ephemeral HTTP response — results are **not persisted** anywhere. Does **not** auto-register machines. |

### 3.3 Server routes change

`ServerCreate` and `ServerUpdate` schemas gain an optional `machine_id` field. No other changes to `/api/v1/servers`.

---

## 4. SSH Tunnel + Provisioner Integration

### 4.1 `SSHTunnelManager` (`backend/app/services/ssh_tunnel.py`)

Async context manager wrapping `asyncssh`:

```python
async with SSHTunnelManager(machine, decrypted_key, passphrase) as tunnel:
    local_port = tunnel.local_port  # random free port on 127.0.0.1
    # provisioner connects to 127.0.0.1:local_port
```

- Opens SSH connection to `machine.ip:machine.ssh_port`
- Forwards `machine_ip:db_port → 127.0.0.1:<random_local_port>`
- Key material passed as an in-memory string — never written to disk
- Tears down cleanly on context exit (including on exception)

### 4.2 Provisioner factory change (`backend/app/services/provisioner/factory.py`)

`get_provisioner()` becomes an async context manager. Callers change from:

```python
provisioner = get_provisioner(server)
```

to:

```python
async with get_provisioner(server, session) as provisioner:
    await provisioner.create_database(spec)
```

Inside:
- If `server.machine_id` is **set**: fetch Machine + SSHKey from DB, decrypt key, open SSH tunnel, rewrite DSN to `127.0.0.1:<local_port>`, construct provisioner normally.
- If `server.machine_id` is **null**: construct provisioner exactly as today. No change in behaviour.

All existing provisioner classes (`PostgreSQLProvisioner`, `MySQLProvisioner`, etc.) are untouched.

**Existing call sites that must be migrated:**
- `backend/app/workers/tasks.py:58` — current sync call `get_provisioner(server)` must become `async with get_provisioner(server, session) as provisioner:`
- `backend/app/api/v1/servers.py` (`_live_capacity`) — same migration required

### 4.3 Network Scanner (`backend/app/services/network_scanner.py`)

- **Ping sweep:** `asyncio.create_subprocess_exec("ping", ...)` — no extra deps, cross-platform.
- **Port-22 scan:** `asyncio.open_connection(ip, 22, timeout=1)` — pure asyncio.
- **Both:** ping first, then port-22 on hosts that responded.
- Concurrency: semaphore-limited to 50 concurrent probes to avoid network flooding.
- Returns: `list[{ip, ping_ok: bool, ssh_open: bool}]`

### 4.4 New dependency

`asyncssh` added to `requirements.txt`.

---

## 5. Frontend

### 5.1 New "Systems" page

Added to main nav (alongside Dashboard, Jobs, Settings). Two tabs:

**SSH Keys tab**
- Table: Name, Username, Created At, Delete
- "Add Key" inline form: name, username, private key (PEM textarea), optional passphrase
- Key material is write-only in the UI — not shown after save

**Machines tab**
- Table: Label/IP, Hostname, Status badge (`online`/`offline`/`unknown`), Last Checked, SSH Key name, Actions
- Per-row actions: **Check** (test SSH), **Detect Engines** (scan → modal with detected engines + "Register as Server" per engine), **Delete**
- "Add Machine" inline form: IP, SSH port (default 22), SSH key dropdown, label
- "Scan Network" button → modal: CIDR input, method selector (Ping / Port 22 / Both), async scan, results table with "Add" button per discovered IP

### 5.2 Server form change

Add optional "SSH Tunnel via Machine" dropdown (lists all non-deleted machines). When a machine is selected, the host/port fields are labelled as "DB host on remote machine" and "DB port on remote machine" to clarify they refer to the address as seen from inside the machine, not the network.

### 5.3 API client additions (`frontend/src/api.ts`)

```
sshKeys.list()
sshKeys.create({ name, username, private_key, passphrase? })
sshKeys.delete(id)

machines.list()
machines.create({ ip, ssh_port, ssh_key_id, label? })
machines.update(id, patch)
machines.delete(id)
machines.check(id)
machines.detectEngines(id)
machines.scan({ cidr, method })
```

---

## 6. Error Handling

| Scenario | Behaviour |
|---|---|
| SSH connection fails (wrong key, unreachable) | `check` endpoint returns `{status: "offline", error: "<reason>"}` — no 500 |
| SSH key parse fails on upload | 422 with message indicating the key format is invalid |
| Delete SSH key with machines referencing it | 409 Conflict |
| Delete Machine with Servers referencing it | 409 Conflict |
| Tunnel fails mid-provisioning | Provisioner raises, job marked failed with SSH error detail |
| SQL console used on SSH-tunneled Server | 400 returned with message: "SQL console is not supported for SSH-tunneled servers" — console bypasses the provisioner factory and cannot open a tunnel |
| Network scan on invalid CIDR | 422 |
| Network scan partial timeout (some hosts slow) | Return results for completed hosts, mark timed-out as `{ping_ok: false, ssh_open: false}` |

---

## 7. Security Considerations

- SSH private keys are Fernet-encrypted at rest using the existing `FERNET_KEY` from config; same mechanism already planned for `admin_dsn`.
- Key material is decrypted in memory only, for the duration of the SSH session, and never logged.
- Network scan CIDR is validated to reject public IP ranges (only RFC-1918 / RFC-4193 ranges allowed) to prevent scanning external networks.
- The `detect-engines` endpoint only probes a fixed allowlist of ports (5432, 3306, 27017, 6333) — no arbitrary port scanning.
- SSH `known_hosts` verification: Phase 1 uses `known_hosts=None` (trust on first connect) with a host fingerprint stored on the Machine record for subsequent verification. Full known_hosts enforcement is a Phase 2 hardening item.

---

## 8. Out of Scope (This Phase)

- Web terminal / interactive SSH session in the browser
- Agent-based discovery (machines phone home)
- Active Directory / LDAP machine inventory import
- Windows machine support (RDP / WinRM)
- SSH known_hosts strict enforcement (Phase 2 hardening)
- Automatic machine registration from scan results (admin always reviews first)
