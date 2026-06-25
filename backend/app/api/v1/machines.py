from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
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
from app.services.encryption import decrypt
from app.services.network_scanner import NetworkScanError, detect_db_engines_via_ssh, scan
from app.services.ssh_tunnel import open_ssh

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
            fingerprint = ssh.host_fingerprint()
        machine.status = "online"
        machine.hostname = hostname or None
        machine.os_info = os_info or None
        machine.host_fingerprint = fingerprint
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
    ) as ssh:
        results = await detect_db_engines_via_ssh(ssh.run)
    return [EngineDetectionResult(**r) for r in results]
