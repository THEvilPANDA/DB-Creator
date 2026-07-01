import asyncio
import ipaddress
import platform
import socket
from typing import Optional

_PRIVATE_NETWORKS = [
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv6Network("fc00::/7"),
]

_ENGINE_BY_PORT: dict[int, str] = {
    5432: "postgresql",
    3306: "mysql",
    27017: "mongodb",
    6333: "qdrant",
    8001: "chroma",
}

_SCAN_CONCURRENCY = 50


class NetworkScanError(ValueError):
    pass


def _validate_cidr(cidr: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        raise NetworkScanError(f"Invalid CIDR: {cidr!r}")
    for private in _PRIVATE_NETWORKS:
        try:
            if network.subnet_of(private):
                return network
        except TypeError:
            continue
    raise NetworkScanError(
        f"Only private IP ranges are allowed for scanning (RFC-1918 / RFC-4193). Got: {cidr}"
    )


async def _check_port(ip: str, port: int, sem: asyncio.Semaphore, timeout: float = 1.0) -> bool:
    async with sem:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=timeout
            )
            writer.close()
            return True
        except Exception:
            return False


async def _ping(ip: str, sem: asyncio.Semaphore) -> bool:
    async with sem:
        flag = "-n" if platform.system() == "Windows" else "-c"
        proc = await asyncio.create_subprocess_exec(
            "ping", flag, "1", ip,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0


_COMMON_PORTS = [22, 80, 443, 445, 3389, 8080, 8443]


def _resolve_hostname(ip: str) -> Optional[str]:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None


async def _probe_host(ip: str, method: str, sem: asyncio.Semaphore) -> dict:
    ping_ok = False
    ssh_open = False
    open_ports: list[int] = []
    if method in ("ping", "both"):
        ping_ok = await _ping(ip, sem)
    if method == "port22" or (method == "both" and ping_ok):
        ssh_open = await _check_port(ip, 22, sem)
        if ssh_open:
            open_ports = [22]
    if method == "tcp":
        checks = await asyncio.gather(*[_check_port(ip, p, sem) for p in _COMMON_PORTS])
        open_ports = [p for p, ok in zip(_COMMON_PORTS, checks) if ok]
        ssh_open = 22 in open_ports
        ping_ok = bool(open_ports)
    hostname = None
    if ping_ok or ssh_open:
        hostname = await asyncio.get_event_loop().run_in_executor(None, _resolve_hostname, ip)
    return {"ip": ip, "ping_ok": ping_ok, "ssh_open": ssh_open, "open_ports": open_ports, "hostname": hostname}


async def scan(cidr: str, method: str) -> list[dict]:
    network = _validate_cidr(cidr)
    hosts = [str(h) for h in network.hosts()]
    sem = asyncio.Semaphore(_SCAN_CONCURRENCY)
    results = await asyncio.gather(*[_probe_host(ip, method, sem) for ip in hosts])
    return [r for r in results if r["ping_ok"] or r["ssh_open"]]


async def scan_stream(cidr: str, method: str):
    """Async generator yielding found hosts as each probe completes."""
    network = _validate_cidr(cidr)
    hosts = [str(h) for h in network.hosts()]
    sem = asyncio.Semaphore(_SCAN_CONCURRENCY)
    queue: asyncio.Queue = asyncio.Queue()

    async def _probe_and_enqueue(ip: str):
        result = await _probe_host(ip, method, sem)
        await queue.put(result)

    tasks = [asyncio.create_task(_probe_and_enqueue(ip)) for ip in hosts]
    for _ in range(len(hosts)):
        result = await queue.get()
        if result["ping_ok"] or result["ssh_open"]:
            yield result

    for task in tasks:
        if not task.done():
            task.cancel()


async def detect_db_engines(
    ip: str,
    sem: Optional[asyncio.Semaphore] = None,
) -> list[dict]:
    """Probe each known DB port on `ip` and return detection results."""
    if sem is None:
        sem = asyncio.Semaphore(10)

    async def _probe(port: int, engine: str) -> dict:
        is_open = await _check_port(ip, port, sem)
        return {"port": port, "engine": engine, "open": is_open}

    return list(await asyncio.gather(*(_probe(p, e) for p, e in _ENGINE_BY_PORT.items())))


_VERSION_CMDS_LINUX: dict[str, str] = {
    "postgresql": "psql --version 2>/dev/null | head -1",
    "mysql": "mysql --version 2>/dev/null | head -1",
    "mongodb": "mongod --version 2>/dev/null | head -1",
    "qdrant": "curl -s http://localhost:6333/ 2>/dev/null | grep -o '\"version\":\"[^\"]*\"' | head -1",
    "chroma": "curl -s http://localhost:8001/api/v1/version 2>/dev/null",
}

_DB_LIST_CMDS_LINUX: dict[str, str] = {
    "postgresql": r"sudo -u postgres psql -qt -c '\l' 2>/dev/null | grep -E '^\s*\w' | awk '{print $1}' | grep -v '^template'",
    "mysql": "sudo mysql --silent -e 'SHOW DATABASES;' 2>/dev/null",
    "mongodb": "mongosh --quiet --eval 'db.adminCommand({listDatabases:1}).databases.forEach(function(d){print(d.name)})' 2>/dev/null",
    "qdrant": "curl -s http://localhost:6333/collections 2>/dev/null | python3 -c 'import sys,json; [print(c[\"name\"]) for c in json.load(sys.stdin).get(\"result\",{}).get(\"collections\",[])]' 2>/dev/null",
    "chroma": "curl -s http://localhost:8001/api/v1/collections 2>/dev/null | python3 -c 'import sys,json; [print(c[\"name\"]) for c in json.load(sys.stdin)]' 2>/dev/null",
}

_VERSION_CMDS_WINDOWS: dict[str, str] = {
    "postgresql": "powershell -Command \"Get-Command psql -ErrorAction SilentlyContinue | ForEach-Object { & $_.Source --version }\"",
    "mysql": "mysql --version 2>nul",
    "mongodb": "mongod --version 2>nul",
    "qdrant": "powershell -Command \"try{(Invoke-WebRequest http://localhost:6333/ -UseBasicParsing).Content}catch{}\"",
    "chroma": "powershell -Command \"try{(Invoke-WebRequest http://localhost:8001/api/v1/version -UseBasicParsing).Content}catch{}\"",
}

_DB_LIST_CMDS_WINDOWS: dict[str, str] = {
    "postgresql": "powershell -Command \"Get-Command psql -ErrorAction SilentlyContinue | ForEach-Object { & $_.Source -U postgres -qt -c '\\l' 2>$null }\"",
    "mysql": "mysql -u root --silent -e \"SHOW DATABASES;\" 2>nul",
    "mongodb": "mongosh --quiet --eval \"db.adminCommand({listDatabases:1}).databases.forEach(function(d){print(d.name)})\" 2>nul",
    "qdrant": "powershell -Command \"try{$r=(Invoke-WebRequest http://localhost:6333/collections -UseBasicParsing).Content|ConvertFrom-Json;$r.result.collections|ForEach-Object{$_.name}}catch{}\"",
    "chroma": "powershell -Command \"try{$r=(Invoke-WebRequest http://localhost:8001/api/v1/collections -UseBasicParsing).Content|ConvertFrom-Json;$r|ForEach-Object{$_.name}}catch{}\"",
}


async def detect_db_engines_via_ssh(run_fn, is_windows: bool = False) -> list[dict]:
    """Check DB ports on the remote machine via SSH, with version and database info."""
    version_cmds = _VERSION_CMDS_WINDOWS if is_windows else _VERSION_CMDS_LINUX
    db_list_cmds = _DB_LIST_CMDS_WINDOWS if is_windows else _DB_LIST_CMDS_LINUX

    results = []
    for port, engine in _ENGINE_BY_PORT.items():
        if is_windows:
            port_cmd = (
                f"powershell -Command \"$r='closed';"
                f"try{{$c=New-Object Net.Sockets.TcpClient('localhost',{port});$c.Close();$r='open'}}catch{{}};"
                f"Write-Output $r\""
            )
        else:
            port_cmd = f"nc -z -w1 localhost {port} 2>/dev/null && echo open || echo closed"

        out = await run_fn(port_cmd)
        is_open = "open" in out.strip().lower()
        version: Optional[str] = None
        databases: list[str] = []
        if is_open:
            if engine in version_cmds:
                v = (await run_fn(version_cmds[engine])).strip()
                version = v or None
            if engine in db_list_cmds:
                db_out = await run_fn(db_list_cmds[engine])
                databases = [line.strip() for line in db_out.splitlines() if line.strip()]
        results.append({"port": port, "engine": engine, "open": is_open, "version": version, "databases": databases})
    return results
