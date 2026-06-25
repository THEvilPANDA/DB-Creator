import asyncio
import ipaddress
import platform
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


async def scan(cidr: str, method: str) -> list[dict]:
    network = _validate_cidr(cidr)
    hosts = [str(h) for h in network.hosts()]
    sem = asyncio.Semaphore(_SCAN_CONCURRENCY)

    async def _probe(ip: str) -> dict:
        ping_ok = False
        ssh_open = False
        if method in ("ping", "both"):
            ping_ok = await _ping(ip, sem)
        if method == "port22" or (method == "both" and ping_ok):
            ssh_open = await _check_port(ip, 22, sem)
        return {"ip": ip, "ping_ok": ping_ok, "ssh_open": ssh_open}

    return await asyncio.gather(*[_probe(ip) for ip in hosts])


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


async def detect_db_engines_via_ssh(run_fn) -> list[dict]:
    """Check DB ports on the remote machine by running nc via SSH."""
    results = []
    for port, engine in _ENGINE_BY_PORT.items():
        out = await run_fn(
            f"nc -z -w1 localhost {port} 2>/dev/null && echo open || echo closed"
        )
        results.append({"port": port, "engine": engine, "open": out.strip() == "open"})
    return results
