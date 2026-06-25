import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_open_ssh_connects_with_key():
    mock_conn = MagicMock()
    mock_conn.get_server_host_key.return_value = None

    with patch("app.services.ssh_tunnel.asyncssh.connect", new=AsyncMock(return_value=mock_conn)) as mock_connect, \
         patch("app.services.ssh_tunnel.asyncssh.import_private_key", return_value=MagicMock()) as mock_import:
        from app.services.ssh_tunnel import open_ssh
        async with open_ssh("1.2.3.4", 22, "ubuntu", "FAKE_PEM") as conn:
            assert conn is not None
        mock_connect.assert_called_once()
        mock_import.assert_called_once_with("FAKE_PEM", passphrase=None)
        mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_open_tunnel_yields_local_port():
    mock_listener = MagicMock()
    mock_conn = MagicMock()
    mock_conn.get_server_host_key.return_value = None
    mock_conn.forward_local_port = AsyncMock(return_value=mock_listener)

    with patch("app.services.ssh_tunnel.asyncssh.connect", new=AsyncMock(return_value=mock_conn)), \
         patch("app.services.ssh_tunnel.asyncssh.import_private_key", return_value=MagicMock()), \
         patch("app.services.ssh_tunnel._find_free_port", return_value=54321):
        from app.services.ssh_tunnel import open_tunnel
        async with open_tunnel("1.2.3.4", 22, "ubuntu", "FAKE_PEM", 5432) as local_port:
            assert local_port == 54321
        mock_listener.close.assert_called_once()
