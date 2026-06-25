import socket
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import asyncssh


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class SSHConnection:
    def __init__(self, conn: asyncssh.SSHClientConnection):
        self._conn = conn

    async def run(self, command: str) -> str:
        result = await self._conn.run(command, check=False)
        return result.stdout or ""

    def host_fingerprint(self) -> Optional[str]:
        key = self._conn.get_server_host_key()
        return key.get_fingerprint() if key else None

    async def forward_port(
        self, remote_host: str, remote_port: int
    ) -> tuple[asyncssh.SSHListener, int]:
        local_port = _find_free_port()
        listener = await self._conn.forward_local_port(
            "127.0.0.1", local_port, remote_host, remote_port
        )
        return listener, local_port


@asynccontextmanager
async def open_ssh(
    host: str,
    port: int,
    username: str,
    key_material: str,
    passphrase: Optional[str] = None,
) -> AsyncIterator[SSHConnection]:
    private_key = asyncssh.import_private_key(key_material, passphrase=passphrase)
    conn = await asyncssh.connect(
        host,
        port=port,
        username=username,
        client_keys=[private_key],
        known_hosts=None,
    )
    try:
        yield SSHConnection(conn)
    finally:
        conn.close()


@asynccontextmanager
async def open_tunnel(
    host: str,
    ssh_port: int,
    username: str,
    key_material: str,
    db_port: int,
    passphrase: Optional[str] = None,
) -> AsyncIterator[int]:
    async with open_ssh(host, ssh_port, username, key_material, passphrase) as ssh:
        listener, local_port = await ssh.forward_port(host, db_port)
        try:
            yield local_port
        finally:
            listener.close()
