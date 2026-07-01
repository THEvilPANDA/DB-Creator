# Network & SSH Security Audit — DBCreator

**Auditor:** Hermes Agent (DeepSeek V4)  
**Repo:** `G:\AI\DBCreator`  
**Date:** 2026-07-01  

---

## Finding Summary

| ID | Severity | Category | Summary |
|----|----------|----------|---------|
| NET-001 | **CRITICAL** | Fernet Key Exposure | Live Fernet key hardcoded in `.env.example` (committed to repo) |
| NET-002 | **CRITICAL** | Dev Secrets in Repo | `backend/.env.example` contains live dev secrets: ADMIN_KEY, JWT_SECRET, DEFAULT_ADMIN_PASSWORD |
| NET-003 | **HIGH** | SSH Known Hosts — Optional | `known_hosts_entry` is `Optional[str]` — connections proceed without host key verification if not provided |
| NET-004 | **HIGH** | SSH Host Key — Never Mandated | No code path enforces known_hosts must be set before SSH connections are established |
| NET-005 | **HIGH** | No SSH Session Timeout | `open_ssh` and `machine_terminal` have no `timeout` parameter on `asyncssh.connect()` — hangs forever if remote is unresponsive |
| NET-006 | **HIGH** | Port Forwarding SSRF Risk | `forward_port()` accepts arbitrary `remote_host` — if any caller passes user-controlled input, could tunnel to internal network hosts behind the SSH bastion |
| NET-007 | **HIGH** | WebSocket Terminal — No Rate Limiting | `machine_terminal` WebSocket endpoint has zero rate limiting — attacker can spam connections |
| NET-088 | **HIGH** | Install/Uninstall — No Audit Trail | `install_db_stream` runs `sudo` commands across SSH with zero audit logging |
| NET-009 | **HIGH** | Destructive Operations — No MFA/Confirmation | `install_db_stream` with `action=uninstall` requires no confirmation beyond admin JWT |
| NET-010 | **MEDIUM** | CIDR Size — No Hard Limit | `scan()` and `scan_stream()` materialise all host IPs from CIDR into a list — a `/16` (65K hosts) blocks memory |
| NET-011 | **MEDIUM** | Scanner Timeout — 1s Fixed | `_check_port()` uses fixed 1.0s timeout — fine for LAN, too tight for WAN (false negatives) |
| NET-012 | **MEDIUM** | Known Hosts Stored / Reused | `host_fingerprint` stored on `Machine` model and reused as `known_hosts_entry` in `open_ssh()` — no rotation mechanism |
| NET-013 | **MEDIUM** | Connection Cleanup in Error Paths | Error handling in `install_db_stream` and `detect_engines` may leak SSH connections on exceptions before the `finally` block |
| NET-014 | **LOW** | SSH Keys in API Responses | `SSHKeyRead` schema omits `encrypted_private_key` and `passphrase_encrypted` — NOT exposed to API consumers |
| NET-015 | **LOW** | WebSocket Terminal Auth — Present But Basic | Token is validated once on connect but there is no per-message re-validation |
| NET-016 | **MEDIUM** | IaaC Generated Resources Have `prevent_destroy` | Terraform output includes `prevent_destroy = true` — safe by default |
| NET-017 | **MEDIUM** | scan_stream — No Cancellation | Long-running scans cannot be cancelled by the client |


---

## Finding Details

### NET-001 [CRITICAL] — Fernet Key Hardcoded in `.env.example`

**File:** `backend/.env.example`  
**Line:** 4  
**Current Value:**
```
FERNET_KEY=YnF46Ea_bY5OsdxJ2xOGoAo471HkEJslQfMpTxaRsNU=
```

**Risk:** This is a *live* Fernet key committed to version control. Anyone with repo access can decrypt all SSH private keys stored in the database via `encryption.py`.

**Verification:** The actual `backend/.env` file was **blocked from reading** by the security guard, confirming this key is treated as a production secret. The `.env.example` copy is a plaintext duplication of the live key.

**Remediation:** Rotate the Fernet key immediately. Remove the key value from `.env.example` (use `FERNET_KEY=change-me-in-production`). All encrypted SSH keys in the database must be re-encrypted under the new key.

---

### NET-002 [CRITICAL] — Dev Secrets Committed in `.env.example`

**File:** `backend/.env.example`

```
ADMIN_KEY=dev-admin-key
JWT_SECRET=dev-jwt-secret-change-in-production
DEFAULT_ADMIN_PASSWORD=admin123
```

**Risk:** Three hardcoded credentials in version control. `admin123` is trivially guessable for the default admin account. `ADMIN_KEY=dev-admin-key` and `JWT_SECRET=dev-jwt-secret-change-in-production` are weak defaults that could match production if.env is not properly configured.

**Cascade risk:** `frontend/.env.example` also contains `VITE_ADMIN_KEY=dev-admin-key`, leaking the admin key to the frontend source.

---

### NET-003 [HIGH] — SSH Known-Hosts Verification Is Optional

**File:** `backend/app/services/ssh_tunnel.py` (line 48, 51)  

```python
async def open_ssh(
    ...
    known_hosts_entry: Optional[str] = None,  # ← OPTIONAL
) -> AsyncIterator[SSHConnection]:
    ...
    known_hosts = asyncssh.import_known_hosts(known_hosts_entry) if known_hosts_entry else None
    #                                                                    ^^^^^^^^^^^^^^^^
    #                                    If None, asyncssh.connect skips host key verification entirely
```

**Risk:** When `known_hosts_entry` is `None` (the default), `asyncssh.connect()` is called with `known_hosts=None`, which **disables host key verification** per asyncssh documentation. This allows MITM attacks against SSH connections.

**Evidence in code paths:**
- `open_tunnel()` → passes through `known_hosts_entry` (optional, no default enforcement)
- `check_machine()` (line 450–464) — does NOT pass `known_hosts_entry` at all
- `machine_terminal()` (line 250) — uses `machine.host_fingerprint` if present, `None` if absent
- `install_db_stream()` (line 337) — same pattern
- `detect_engines()` (line 491) — does pass `known_hosts_entry`

**Only `site_migration.py` (line 196) enforces:** it raises `ValueError` if `host_fingerprint` is None before calling `open_ssh` — but machines.py does not.

---

### NET-004 [HIGH] — No Code Path Mandates Known-Hosts Before SSH

**Files:** `backend/app/api/v1/machines.py`, `backend/app/services/ssh_tunnel.py`

The `check_machine()` endpoint (line 450–464) **discovered** the host key (via `ssh.export_host_key()`) after connecting without one, then stores it. But there is no lifecycle gate ensuring that subsequent connections use that stored key.

**Attack scenario:** First connection to a machine has no known_hosts → MITM possible on the first check. The stored fingerprint is whatever the MITM presents.

---

### NET-005 [HIGH] — No SSH Session Timeout

**File:** `backend/app/services/ssh_tunnel.py` (line 52–58)

```python
conn = await asyncssh.connect(
    host,
    port=port,
    username=username,
    client_keys=[private_key],
    known_hosts=known_hosts,
    # NO timeout parameter
)
```

**Risk:** If the remote host is unresponsive, `asyncssh.connect()` can hang indefinitely. The default TCP connect timeout in asyncssh is system-dependent and may be extremely long.

**Also in `machine_terminal()`** (line 251): the same call without a timeout.

`install_db_stream()` additionally runs each command with `timeout=600` (line 365), but the SSH connect itself has no timeout.

---

### NET-006 [HIGH] — Port Forwarding SSRF via `forward_port()`

**File:** `backend/app/services/ssh_tunnel.py` (line 31–38)

```python
async def forward_port(
    self, remote_host: str, remote_port: int
) -> tuple[asyncssh.SSHListener, int]:
    local_port = _find_free_port()
    listener = await self._conn.forward_local_port(
        "127.0.0.1", local_port, remote_host, remote_port
    )
    return listener, local_port
```

**Risk:** `forward_port()` accepts an arbitrary `remote_host` with no validation. If a future caller or endpoint passes user-controlled `remote_host`, the SSH tunnel can be used to proxy connections to **any host reachable from the SSH target machine** — including internal network hosts (RFC 1918 addresses, cloud metadata services like 169.254.169.254, Kubernetes internal DNS, etc.).

**Current mitigation:** The only call site in `open_tunnel()` (line 76) hardcodes the SSH host itself:
```python
listener, local_port = await ssh.forward_port(host, db_port)
```
But `forward_port` is a **public method** on `SSHConnection`, and nothing prevents a future code path from using it unsafely.

**Test:** `test_ssh_tunnel.py` line 46 tests `open_tunnel` with `host="1.2.3.4"` and `db_port=5432`. No test validates that `forward_port` with a user-controlled `remote_host` is rejected.

---

### NET-007 [HIGH] — WebSocket Terminal Has No Rate Limiting

**File:** `backend/app/api/v1/machines.py` (line 223–310)

The `/machines/{machine_id}/terminal` WebSocket endpoint:
1. Accepts a JWT token as a query parameter (line 227)
2. On validation, accepts the WebSocket (line 245)
3. Spawns a full SSH session + PTY per connection
4. Has **zero rate limiting** — no client IP bucketing, no per-machine limit, no global concurrent connection cap

**Risk:** An attacker with a valid JWT (or SSRF to an internal endpoint) can open hundreds of concurrent SSH sessions, exhausting resources on both the API server and remote machines.

The main app (`main.py` line 48) imports `slowapi` for rate limiting but **never applies it to any route** — only the exception handler is registered.

---

### NET-008 [HIGH] — Install/Uninstall Commands Have No Audit Trail

**File:** `backend/app/api/v1/machines.py` (line 313–386)

The `install_db_stream` endpoint:
- Runs arbitrary `sudo` commands across SSH (apt-get install, systemctl, pip3, curl pipes to shell)
- Allows `action=uninstall` which permanently removes packages
- **Calls `write_audit` zero times**

Compare with `sites.py` and `jobs.py` which consistently audit every CRUD operation. The destructive install/uninstall path has no audit logging whatsoever.

---

### NET-009 [HIGH] — Destructive Operations (Uninstall) No MFA / Confirmation

**File:** `backend/app/api/v1/machines.py` (line 313–386)

The endpoint accepts `action=install|uninstall` via a query parameter. There is:
- No confirmation step
- No MFA
- No `dry_run` mode
- No double-opt-in for `action=uninstall`
- No "are you sure?" prompt

A single admin with a valid JWT can trigger full removal of PostgreSQL, MySQL, MongoDB, Qdrant, or Chroma from a remote machine instantly.

---

### NET-010 [MEDIUM] — No CIDR Size Limit on Network Scanner

**File:** `backend/app/services/network_scanner.py` (line 100–105)

```python
async def scan(cidr: str, method: str) -> list[dict]:
    network = _validate_cidr(cidr)
    hosts = [str(h) for h in network.hosts()]  # ← materialises ALL hosts
    sem = asyncio.Semaphore(_SCAN_CONCURRENCY)  # 50
    results = await asyncio.gather(*[_probe_host(ip, method, sem) for ip in hosts])
    return [r for r in results if r["ping_ok"] or r["ssh_open"]]
```

**Risk:** A `/16` network (65,534 hosts) creates 65K+ asyncio tasks in a single gather, allocating a 65K-element list of results. A `/8` (16M hosts) would exhaust server memory entirely.

**Mitigation present:** Only private RFC-1918 CIDRs are accepted (`_validate_cidr`), which limits the blast radius but doesn't prevent large RFC-1918 ranges.

---

### NET-011 [MEDIUM] — Scanner Port-Timeout Is a Fixed 1 Second

**File:** `backend/app/services/network_scanner.py` (line 45–54)

```python
async def _check_port(ip: str, port: int, sem: asyncio.Semaphore, timeout: float = 1.0) -> bool:
```

**Risk:** 1 second is appropriate for low-latency LAN scanning but will produce false negatives on high-latency or congested WAN links. Not configurable.

---

### NET-012 [MEDIUM] — Known Hosts Stored but No Rotation

**File:** `backend/app/models/machine.py` (line 24–26)

```python
host_fingerprint: Optional[str] = Field(
    default=None, sa_column=sa.Column(sa.Text, nullable=True)
)
```

The fingerprint is set once by `check_machine()` and reused forever. There is:
- No re-verification mechanism
- No expiry/rotation policy
- If a host key changes (e.g. server rebuild), the stored fingerprint becomes stale and connections fail silently (or pass if `known_hosts_entry` is not provided, per NET-003)

---

### NET-013 [MEDIUM] — SSH Connection Cleanup on Error

**File:** `backend/app/api/v1/machines.py`

- `install_db_stream()` (line 333–384): the `finally` block (line 378) does close `conn` — **good**. However, if `asyncssh.connect()` itself raises an exception (line 338), `conn` is never assigned, so `finally` is a no-op — but `asyncssh.connect` manages its own cleanup. **Acceptable.**

- `machine_terminal()` (line 304–306): `finally` block closes `conn` — **good**.

- `detect_engines()` (line 476–496): uses `async with open_ssh(...)` — the context manager handles cleanup in its own `finally` (line 61–62). **Good.**

**No leaks identified in current code**, but `open_ssh`'s `try/finally` pattern at line 61 is correct only because `yield` is inside `try` — if `conn.close()` is expensive or raises, the caller's `finally` completes first. This is acceptable as-written.

---

### NET-014 [LOW] — SSH Keys NOT Exposed in API Responses

**File:** `backend/app/schemas/ssh_key.py` (line 14–20)

```python
class SSHKeyRead(BaseModel):
    id: int
    name: str
    username: str
    created_at: datetime
    model_config = {"from_attributes": True}
```

**Verdict:** The read schema explicitly omits `encrypted_private_key` and `passphrase_encrypted`. The Wave 1 auditor's concern is **not a finding** — SSH keys are not exposed in API responses.

---

### NET-015 [LOW] — WebSocket Terminal Auth Is Validate-Once

**File:** `backend/app/api/v1/machines.py` (line 223–237)

```python
try:
    payload = decode_token(token)
    if payload.get("type") != "access" or not payload.get("is_admin"):
        await websocket.close(code=4003)
        return
except Exception:
    await websocket.close(code=4001)
    return
```

The JWT token is validated once on connection. There is no per-message re-validation. If the token expires mid-session, the terminal remains open. The token is passed as a query parameter (logged in server access logs).

---

### NET-016 [MEDIUM] — No Scan Cancellation

**File:** `backend/app/services/network_scanner.py` (line 108–128)

`scan_stream()` launches tasks and never checks for client disconnection. If the HTTP client disconnects, the scan continues running server-side until completion. Non-streaming `scan()` is also uncancellable once started.

---

## Overall Risk

| Domain | Rating | Rationale |
|--------|--------|-----------|
| **SSH Security** | 🔴 HIGH | Known hosts optional (MITM), no session timeout, first-connect trust, no re-verification |
| **Network Scanner** | 🟡 MEDIUM | No CIDR size cap, fixed 1s timeout, no cancellation |
| **Port Forwarding** | 🔴 HIGH | SSRF surface via `forward_port()` if callers pass user input |
| **WebSocket Terminal** | 🟡 MEDIUM | No rate limiting, validate-once auth, no per-message re-auth |
| **Destructive Operations** | 🔴 HIGH | No audit trail on install/uninstall, no MFA/confirmation |
| **Secrets Management** | 🔴 CRITICAL | Fernet key and admin secrets committed to `.env.example` |

**Overall Rating: HIGH** — Immediate action required on NET-001, NET-002, NET-003, NET-006, NET-008, NET-009.
