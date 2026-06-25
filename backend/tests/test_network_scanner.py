import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.network_scanner import scan, NetworkScanError


@pytest.mark.asyncio
async def test_rejects_public_cidr():
    with pytest.raises(NetworkScanError, match="private"):
        await scan("8.8.8.0/24", "port22")


@pytest.mark.asyncio
async def test_rejects_invalid_cidr():
    with pytest.raises(NetworkScanError, match="Invalid"):
        await scan("not-a-cidr", "port22")


@pytest.mark.asyncio
async def test_port22_scan_finds_open_hosts():
    async def fake_open_connection(ip, port, **kwargs):
        if ip == "192.168.1.1":
            reader, writer = MagicMock(), MagicMock()
            writer.close = MagicMock()
            return reader, writer
        raise OSError("refused")

    with patch("asyncio.open_connection", side_effect=fake_open_connection):
        results = await scan("192.168.1.0/30", "port22")

    assert any(r["ip"] == "192.168.1.1" and r["ssh_open"] for r in results)
    assert any(r["ip"] == "192.168.1.2" and not r["ssh_open"] for r in results)
