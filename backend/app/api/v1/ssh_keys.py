import asyncssh
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models.machine import Machine
from app.models.ssh_key import SSHKey
from app.schemas.ssh_key import SSHKeyCreate, SSHKeyRead
from app.services.encryption import encrypt

router = APIRouter(prefix="/ssh-keys", tags=["ssh-keys"])


def _validate_private_key(pem: str, passphrase: str | None = None) -> None:
    try:
        asyncssh.import_private_key(pem, passphrase=passphrase)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid private key: {exc}")


@router.post("", response_model=SSHKeyRead, status_code=201)
async def create_ssh_key(
    payload: SSHKeyCreate,
    session: AsyncSession = Depends(get_session),
):
    _validate_private_key(payload.private_key, payload.passphrase)
    record = SSHKey(
        name=payload.name,
        username=payload.username,
        encrypted_private_key=encrypt(payload.private_key),
        passphrase_encrypted=encrypt(payload.passphrase) if payload.passphrase else None,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return SSHKeyRead.model_validate(record)


@router.get("", response_model=list[SSHKeyRead])
async def list_ssh_keys(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(SSHKey))
    return [SSHKeyRead.model_validate(k) for k in result.scalars().all()]


@router.delete("/{key_id}", response_model=SSHKeyRead)
async def delete_ssh_key(key_id: int, session: AsyncSession = Depends(get_session)):
    record = await session.get(SSHKey, key_id)
    if not record:
        raise HTTPException(status_code=404, detail="SSH key not found")
    result = await session.execute(
        select(Machine).where(Machine.ssh_key_id == key_id, Machine.is_deleted == False)  # noqa: E712
    )
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="SSH key is in use by one or more machines")
    await session.delete(record)
    await session.commit()
    return SSHKeyRead.model_validate(record)
