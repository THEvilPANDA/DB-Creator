import asyncio
import json
import secrets
from datetime import datetime, timezone
from typing import Optional

import asyncssh
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.dependencies import require_admin
from app.models.machine import Machine
from app.models.server import Server
from app.models.ssh_key import SSHKey
from app.models.user import User
from app.schemas.machine import (
    EngineDetectionResult,
    MachineCreate,
    MachineRead,
    MachineUpdate,
    ScanRequest,
    ScanResult,
)
from app.services.auth import decode_token
from app.services.encryption import decrypt
from app.services.network_scanner import NetworkScanError, detect_db_engines_via_ssh, scan, scan_stream
from app.services.ssh_tunnel import open_ssh

_INSTALL_CMDS_LINUX: dict[str, list[str]] = {  # noqa: E501
    "postgresql": [
        "sudo apt-get update -qq 2>&1",
        "sudo apt-get install -y postgresql 2>&1",
        "sudo systemctl enable postgresql 2>&1",
        "sudo systemctl start postgresql 2>&1",
        "sudo systemctl is-active postgresql && echo 'PostgreSQL running on port 5432'",
    ],
    "mysql": [
        "sudo apt-get update -qq 2>&1",
        "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server 2>&1",
        "sudo systemctl enable mysql 2>&1",
        "sudo systemctl start mysql 2>&1",
        "sudo systemctl is-active mysql && echo 'MySQL running on port 3306'",
    ],
    "mongodb": [
        "curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor 2>&1",
        "echo 'deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse' | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list",
        "sudo apt-get update -qq 2>&1",
        "sudo apt-get install -y mongodb-org 2>&1",
        "sudo systemctl enable mongod 2>&1",
        "sudo systemctl start mongod 2>&1",
        "sudo systemctl is-active mongod && echo 'MongoDB running on port 27017'",
    ],
    "qdrant": [
        "curl -L https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-musl.tar.gz | tar -xz -C /tmp 2>&1",
        "sudo mv /tmp/qdrant /usr/local/bin/qdrant 2>&1",
        "nohup /usr/local/bin/qdrant > /tmp/qdrant.log 2>&1 &",
        "sleep 2 && curl -sf http://localhost:6333/ > /dev/null && echo 'Qdrant running on port 6333'",
    ],
    "chroma": [
        "sudo pip3 install chromadb 2>&1",
        "python3 -c \"import shutil; p=shutil.which('chroma'); assert p, 'chroma binary not found after install'; svc='[Unit]\\nDescription=Chroma Vector DB\\n[Service]\\nExecStart=' + p + ' run --host 0.0.0.0 --port 8001 --path /var/lib/chroma\\nRestart=always\\n[Install]\\nWantedBy=multi-user.target\\n'; open('/tmp/chroma.service','w').write(svc); print('Service file ready, chroma at:', p)\" && sudo mv /tmp/chroma.service /etc/systemd/system/chroma.service 2>&1",
        "sudo mkdir -p /var/lib/chroma && sudo systemctl daemon-reload && sudo systemctl enable chroma && sudo systemctl start chroma 2>&1",
        "sleep 3 && curl -sf http://localhost:8001/api/v1/heartbeat > /dev/null && echo 'Chroma running on port 8001' || echo 'WARNING: Chroma not responding on port 8001'",
    ],
}

_INSTALL_CMDS_WINDOWS: dict[str, list[str]] = {
    "postgresql": [
        # Idempotent check — if service exists, start if needed and done
        "powershell -Command \"$svc=Get-Service 'postgresql-x64-17' -EA SilentlyContinue; if ($svc) { if ($svc.Status -ne 'Running') { Start-Service 'postgresql-x64-17' -EA SilentlyContinue }; Write-Output ('PostgreSQL ' + (Get-Service 'postgresql-x64-17').Status + ' on port 5432'); exit 0 }; Write-Output 'Downloading PostgreSQL 17 binary package (no installer - bypasses desktop session requirement)...'\"",
        # Download binary ZIP using WebClient (no timeout, streams to disk — Invoke-WebRequest times out on large files)
        "powershell -Command \"New-Item -ItemType Directory -Force -Path C:\\PostgreSQL | Out-Null; if (Test-Path 'C:/PostgreSQL/17/pgsql/bin/initdb.exe') { Write-Output 'Binaries already present' } else { if (-not (Test-Path 'C:/PostgreSQL/pg17.zip')) { Write-Output 'Downloading PostgreSQL 17 binaries (~300MB)...'; (New-Object Net.WebClient).DownloadFile('https://get.enterprisedb.com/postgresql/postgresql-17.10-1-windows-x64-binaries.zip', 'C:\\PostgreSQL\\pg17.zip'); Write-Output 'Download complete' } else { Write-Output 'ZIP already downloaded' }; Write-Output 'Extracting...'; Expand-Archive -Path 'C:/PostgreSQL/pg17.zip' -DestinationPath 'C:/PostgreSQL/17' -Force; Write-Output 'Binaries ready' }\"",
        # initdb + pg_ctl register + start — all without any installer
        "powershell -Command \"$pw='{pg_pw}'; $bin='C:/PostgreSQL/17/pgsql/bin'; $data='C:/PostgreSQL/17/data'; if (-not (Test-Path $data)) { Write-Output 'Initializing data directory...'; $pw | Out-File -FilePath 'C:/PostgreSQL/pwfile.txt' -Encoding ascii -NoNewline; & (Join-Path $bin 'initdb.exe') -D $data -U postgres --pwfile='C:/PostgreSQL/pwfile.txt' -A md5 2>&1 | ForEach-Object { Write-Output $_ }; Remove-Item 'C:/PostgreSQL/pwfile.txt' -Force -EA SilentlyContinue; Write-Output 'Data directory ready' } else { Write-Output 'Data directory already exists' }; if (-not (Get-Service 'postgresql-x64-17' -EA SilentlyContinue)) { Write-Output 'Registering Windows service...'; & (Join-Path $bin 'pg_ctl.exe') register -N 'postgresql-x64-17' -D $data 2>&1 | ForEach-Object { Write-Output $_ } }; net start 'postgresql-x64-17' 2>&1 | Out-Null; $s=Get-Service 'postgresql-x64-17' -EA SilentlyContinue; if ($s -and $s.Status -eq 'Running') { Write-Output 'PostgreSQL running on port 5432'; Write-Output ('Superuser: postgres  Password: ' + $pw) } else { Write-Output 'WARNING: service not running after setup'; Write-Output ('Check: & ' + $bin + '\\pg_ctl.exe status -D ' + $data) }\"",
    ],
    "mysql": [
        "winget install --id Oracle.MySQL --accept-source-agreements --accept-package-agreements --silent",
        "powershell -Command \"$svc=Get-Service MySQL -EA SilentlyContinue; if ($svc) { Write-Output ('MySQL service already registered (State: ' + $svc.Status + ') - skipping init'); exit 0 }; $m=Get-ChildItem 'C:\\Program Files\\MySQL' -Recurse -Filter mysqld.exe -EA SilentlyContinue | Select-Object -First 1; if (-not $m) { Write-Output 'ERROR: mysqld.exe not found - MySQL install may have failed'; exit 1 }; Write-Output ('Found mysqld: ' + $m.FullName); & $m.FullName --initialize-insecure 2>&1 | ForEach-Object { Write-Output $_ }; & $m.FullName --install MySQL 2>&1 | ForEach-Object { Write-Output $_ }; Write-Output 'Service setup done'; exit 0\"",
        "net start MySQL || echo MySQL already running or start failed",
        "sc query MySQL | findstr RUNNING && echo MySQL running on port 3306 || echo WARNING: MySQL service not running",
    ],
    "mongodb": [
        "winget install --id MongoDB.Server --accept-source-agreements --accept-package-agreements --silent",
        "net start MongoDB || echo MongoDB already running or start failed",
        "sc query MongoDB | findstr RUNNING && echo MongoDB running on port 27017 || echo WARNING: MongoDB service not running",
    ],
    "qdrant": [
        "powershell -Command \"$running=Get-Process qdrant -EA SilentlyContinue; if ($running) { Write-Output 'Qdrant already running'; exit 0 }; New-Item -ItemType Directory -Force -Path C:\\qdrant | Out-Null; Invoke-WebRequest -Uri https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-pc-windows-msvc.zip -OutFile C:\\qdrant\\qdrant.zip -UseBasicParsing\"",
        "powershell -Command \"if (Test-Path C:\\qdrant\\qdrant.zip) { Expand-Archive -Path C:\\qdrant\\qdrant.zip -DestinationPath C:\\qdrant -Force }\"",
        "powershell -Command \"$running=Get-Process qdrant -EA SilentlyContinue; if (-not $running) { Start-Process -FilePath C:\\qdrant\\qdrant.exe -WindowStyle Hidden }; Start-Sleep 3; try{(Invoke-WebRequest http://localhost:6333/ -UseBasicParsing -TimeoutSec 3) | Out-Null; Write-Output 'Qdrant running on port 6333'}catch{Write-Output 'WARNING: Qdrant not responding on port 6333'}\"",
    ],
    "chroma": [
        "pip install chromadb",
        "powershell -Command \"$c=Get-Command chroma -EA SilentlyContinue; if (-not $c) { Write-Output 'ERROR: chroma not in PATH after install'; exit 1 }; Write-Output ('chroma at: ' + $c.Source); $running=Get-Process -Name chroma -EA SilentlyContinue; if ($running) { Write-Output 'Chroma already running'; exit 0 }; New-Item -ItemType Directory -Force -Path C:\\chroma-data | Out-Null; Start-Process -FilePath $c.Source -ArgumentList @('run','--host','0.0.0.0','--port','8001','--path','C:\\chroma-data') -WindowStyle Hidden; Start-Sleep 5; try{(Invoke-WebRequest http://localhost:8001/api/v1/heartbeat -UseBasicParsing -TimeoutSec 5) | Out-Null; Write-Output 'Chroma running on port 8001'}catch{Write-Output 'WARNING: Chroma not responding on port 8001'}\"",
    ],
}

_UNINSTALL_CMDS_LINUX: dict[str, list[str]] = {
    "postgresql": [
        "sudo systemctl stop postgresql 2>&1 || true",
        "sudo apt-get remove -y postgresql postgresql-* 2>&1",
        "echo 'PostgreSQL removed.'",
    ],
    "mysql": [
        "sudo systemctl stop mysql 2>&1 || true",
        "sudo apt-get remove -y mysql-server mysql-client 2>&1",
        "echo 'MySQL removed.'",
    ],
    "mongodb": [
        "sudo systemctl stop mongod 2>&1 || true",
        "sudo apt-get remove -y mongodb-org 2>&1",
        "echo 'MongoDB removed.'",
    ],
    "qdrant": [
        "sudo rm -f /usr/local/bin/qdrant 2>&1",
        "echo 'Qdrant binary removed.'",
    ],
    "chroma": [
        "sudo systemctl stop chroma 2>&1 || true",
        "sudo systemctl disable chroma 2>&1 || true",
        "sudo rm -f /etc/systemd/system/chroma.service && sudo systemctl daemon-reload 2>&1",
        "echo 'Chroma removed.'",
    ],
}

_UNINSTALL_CMDS_WINDOWS: dict[str, list[str]] = {
    "postgresql": [
        "powershell -Command \"net stop 'postgresql-x64-17' 2>&1 | Out-Null; if (Test-Path 'C:/PostgreSQL/17/pgsql/bin/pg_ctl.exe') { & 'C:/PostgreSQL/17/pgsql/bin/pg_ctl.exe' unregister -N 'postgresql-x64-17' 2>&1 | Out-Null } else { sc.exe delete 'postgresql-x64-17' 2>&1 | Out-Null }; winget uninstall --id PostgreSQL.PostgreSQL.17 --accept-source-agreements 2>&1 | Out-Null; Remove-Item 'C:\\PostgreSQL' -Recurse -Force -EA SilentlyContinue; Write-Output 'PostgreSQL removed'\"",
    ],
    "mysql": [
        "net stop MySQL 2>nul & winget uninstall --id Oracle.MySQL --accept-source-agreements 2>nul",
        "echo MySQL uninstalled.",
    ],
    "mongodb": [
        "net stop MongoDB 2>nul & winget uninstall --id MongoDB.Server --accept-source-agreements 2>nul",
        "echo MongoDB uninstalled.",
    ],
    "qdrant": [
        "powershell -Command \"Get-Process qdrant -EA SilentlyContinue | Stop-Process -Force; Remove-Item C:\\qdrant -Recurse -Force -EA SilentlyContinue; Write-Output 'Qdrant removed.'\"",
    ],
    "chroma": [
        "powershell -Command \"Get-Process -Name chroma -EA SilentlyContinue | Stop-Process -Force; Write-Output 'Chroma stopped.'\"",
    ],
}

# winget exit codes that mean "already installed / already up to date" — treat as success
_WINGET_OK_CODES = {0, None, 43, -1978335189}

router = APIRouter(prefix="/machines", tags=["machines"])


async def _get_key_material(session: AsyncSession, machine: Machine) -> tuple[str, Optional[str], str]:
    ssh_key_rec = await session.get(SSHKey, machine.ssh_key_id)
    if not ssh_key_rec:
        raise HTTPException(status_code=400, detail="SSH key not found for this machine")
    key_material = decrypt(ssh_key_rec.encrypted_private_key)
    passphrase = decrypt(ssh_key_rec.passphrase_encrypted) if ssh_key_rec.passphrase_encrypted else None
    return key_material, passphrase, ssh_key_rec.username


@router.post("", response_model=MachineRead, status_code=201)
async def create_machine(
    payload: MachineCreate,
    session: AsyncSession = Depends(get_session),
    _: "User" = Depends(require_admin),
):
    machine = Machine(**payload.model_dump())
    session.add(machine)
    await session.commit()
    await session.refresh(machine)
    return MachineRead.model_validate(machine)


@router.get("", response_model=list[MachineRead])
async def list_machines(
    session: AsyncSession = Depends(get_session),
    _: "User" = Depends(require_admin),
):
    result = await session.execute(
        select(Machine).where(Machine.is_deleted == False)  # noqa: E712
    )
    return [MachineRead.model_validate(m) for m in result.scalars().all()]


@router.post("/scan", response_model=list[ScanResult])
async def scan_network(
    payload: ScanRequest,
    _: "User" = Depends(require_admin),
):
    try:
        results = await scan(payload.cidr, payload.method)
    except NetworkScanError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return [ScanResult(**r) for r in results]


@router.get("/scan/stream")
async def scan_network_stream(
    cidr: str = Query(...),
    method: str = Query(...),
    _: "User" = Depends(require_admin),
):
    async def generate():
        try:
            async for result in scan_stream(cidr, method):
                yield f"data: {json.dumps(result)}\n\n"
        except NetworkScanError as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield 'data: {"done":true}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.websocket("/{machine_id}/terminal")
async def machine_terminal(
    websocket: WebSocket,
    machine_id: int,
    session: AsyncSession = Depends(get_session),
):
    await websocket.accept()
    # First message must be {"type": "auth", "token": "<jwt>"}
    # Avoids leaking the JWT into access logs via query params.
    try:
        auth_text = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        auth_msg = json.loads(auth_text)
        if auth_msg.get("type") != "auth":
            raise ValueError("Expected auth message")
        payload = decode_token(auth_msg["token"])
        if payload.get("type") != "access" or not payload.get("is_admin"):
            await websocket.close(code=4003)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        await websocket.close(code=4004)
        return

    key_material, passphrase, username = await _get_key_material(session, machine)

    conn = None
    try:
        private_key = asyncssh.import_private_key(key_material, passphrase=passphrase)
        known_hosts = asyncssh.import_known_hosts(machine.host_fingerprint) if machine.host_fingerprint else None
        conn = await asyncssh.connect(
            machine.ip,
            port=machine.ssh_port,
            username=username,
            client_keys=[private_key],
            known_hosts=known_hosts,
        )
        os_result = await conn.run("uname -s 2>/dev/null || echo Windows", check=False, timeout=5)
        os_name = (os_result.stdout or "").strip()
        is_windows = os_name == "Windows" or os_name == ""
        await websocket.send_text(json.dumps({"type": "os", "data": "windows" if is_windows else "linux"}))
        process = await conn.create_process(
            request_pty=True,
            term_type="xterm-256color",
            encoding=None,
        )

        async def ws_to_ssh():
            try:
                while True:
                    text = await websocket.receive_text()
                    msg = json.loads(text)
                    if msg.get("type") == "input":
                        process.stdin.write(msg["data"].encode())
                    elif msg.get("type") == "resize":
                        process.change_terminal_size(msg["cols"], msg["rows"])
            except (WebSocketDisconnect, Exception):
                pass
            finally:
                try:
                    process.stdin.write_eof()
                except Exception:
                    pass

        async def ssh_to_ws():
            try:
                while True:
                    data = await process.stdout.read(4096)
                    if not data:
                        break
                    await websocket.send_text(
                        json.dumps({"type": "output", "data": data.decode("utf-8", errors="replace")})
                    )
            except Exception:
                pass

        await asyncio.gather(ws_to_ssh(), ssh_to_ws())

    except Exception as exc:
        try:
            await websocket.send_text(json.dumps({"type": "error", "data": str(exc)}))
        except Exception:
            pass
    finally:
        if conn:
            conn.close()
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/{machine_id}/install-db")
async def install_db_stream(
    machine_id: int,
    engine: str = Query(...),
    action: str = Query("install"),
    _: "User" = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    if action not in ("install", "uninstall"):
        raise HTTPException(400, "action must be 'install' or 'uninstall'")
    valid_engines = set(_INSTALL_CMDS_LINUX) | set(_INSTALL_CMDS_WINDOWS)
    if engine not in valid_engines:
        raise HTTPException(400, f"Unknown engine: {engine}. Choose from: {sorted(valid_engines)}")

    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(404, "Machine not found")

    key_material, passphrase, username = await _get_key_material(session, machine)

    async def generate():
        conn = None
        try:
            private_key = asyncssh.import_private_key(key_material, passphrase=passphrase)
            known_hosts = asyncssh.import_known_hosts(machine.host_fingerprint) if machine.host_fingerprint else None
            conn = await asyncssh.connect(
                machine.ip,
                port=machine.ssh_port,
                username=username,
                client_keys=[private_key],
                known_hosts=known_hosts,
            )
            # Detect OS
            os_result = await conn.run("uname -s 2>/dev/null || echo Windows", check=False, timeout=10)
            os_name = (os_result.stdout or "").strip()
            is_windows = os_name == "Windows" or os_name == ""
            cmds = _INSTALL_CMDS_WINDOWS if is_windows else _INSTALL_CMDS_LINUX
            os_label = "Windows" if is_windows else os_name
            yield f"data: {json.dumps({'type': 'output', 'data': 'Detected OS: ' + os_label})}\n\n"

            if engine not in cmds:
                platform_label = "Windows" if is_windows else "Linux"
                yield f"data: {json.dumps({'type': 'error', 'data': engine + ' install not supported on ' + platform_label})}\n\n"
                return

            if action == "uninstall":
                cmds = _UNINSTALL_CMDS_WINDOWS if is_windows else _UNINSTALL_CMDS_LINUX
            ok_codes = _WINGET_OK_CODES if is_windows else {0, None}
            pg_pw = secrets.token_urlsafe(16)
            for cmd in cmds[engine]:
                cmd = cmd.replace("{pg_pw}", pg_pw)
                yield f"data: {json.dumps({'type': 'cmd', 'data': cmd})}\n\n"
                result = await conn.run(cmd, check=False, timeout=600)
                output = (result.stdout or "") + (result.stderr or "")
                for line in output.splitlines():
                    if line.strip():
                        yield f"data: {json.dumps({'type': 'output', 'data': line})}\n\n"
                if result.returncode not in ok_codes:
                    yield f"data: {json.dumps({'type': 'error', 'data': f'Step failed (exit {result.returncode})'})}\n\n"
                    break
            else:
                yield f"data: {json.dumps({'type': 'done', 'data': f'{engine} {action}ed successfully'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'data': str(exc)})}\n\n"
        finally:
            if conn:
                conn.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{machine_id}", response_model=MachineRead)
async def get_machine(
    machine_id: int,
    session: AsyncSession = Depends(get_session),
    _: "User" = Depends(require_admin),
):
    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")
    return MachineRead.model_validate(machine)


@router.put("/{machine_id}", response_model=MachineRead)
async def update_machine(
    machine_id: int,
    payload: MachineUpdate,
    session: AsyncSession = Depends(get_session),
    _: "User" = Depends(require_admin),
):
    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(machine, key, value)
    session.add(machine)
    await session.commit()
    await session.refresh(machine)
    return MachineRead.model_validate(machine)


@router.delete("/{machine_id}", response_model=MachineRead)
async def delete_machine(
    machine_id: int,
    session: AsyncSession = Depends(get_session),
    _: "User" = Depends(require_admin),
):
    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")
    result = await session.execute(
        select(Server).where(Server.machine_id == machine_id, Server.is_deleted == False)  # noqa: E712
    )
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="Machine is in use by one or more servers")
    machine.is_deleted = True
    machine.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(machine)
    await session.commit()
    await session.refresh(machine)
    return MachineRead.model_validate(machine)


@router.post("/{machine_id}/check", response_model=MachineRead)
async def check_machine(
    machine_id: int,
    session: AsyncSession = Depends(get_session),
    _: "User" = Depends(require_admin),
):
    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")
    key_material, passphrase, username = await _get_key_material(session, machine)
    try:
        async with open_ssh(
            host=machine.ip,
            port=machine.ssh_port,
            username=username,
            key_material=key_material,
            passphrase=passphrase,
        ) as ssh:
            hostname = (await ssh.run("hostname")).strip()
            os_info = (await ssh.run("uname -a")).strip()
            host_key = ssh.export_host_key(machine.ip, machine.ssh_port)
        machine.status = "online"
        machine.hostname = hostname or None
        machine.os_info = os_info or None
        machine.host_fingerprint = host_key
    except Exception as exc:
        machine.status = "offline"
        machine.os_info = str(exc)[:500]
    machine.last_checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(machine)
    await session.commit()
    await session.refresh(machine)
    return MachineRead.model_validate(machine)


@router.post("/{machine_id}/detect-engines", response_model=list[EngineDetectionResult])
async def detect_engines(
    machine_id: int,
    session: AsyncSession = Depends(get_session),
    _: "User" = Depends(require_admin),
):
    machine = await session.get(Machine, machine_id)
    if not machine or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")
    key_material, passphrase, username = await _get_key_material(session, machine)
    async with open_ssh(
        host=machine.ip,
        port=machine.ssh_port,
        username=username,
        key_material=key_material,
        passphrase=passphrase,
        known_hosts_entry=machine.host_fingerprint,
    ) as ssh:
        os_out = (await ssh.run("uname -s 2>/dev/null || echo Windows")).strip()
        is_windows = os_out == "Windows" or os_out == ""
        results = await detect_db_engines_via_ssh(ssh.run, is_windows=is_windows)
    return [EngineDetectionResult(**r) for r in results]
