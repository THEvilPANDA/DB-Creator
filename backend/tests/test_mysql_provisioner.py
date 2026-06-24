import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.provisioner.mysql import MySQLProvisioner
from app.services.provisioner.base import DatabaseSpec, UserSpec, PermissionSpec


def _provisioner():
    return MySQLProvisioner(
        dsn="mysql://root:secret@localhost:3306/",
        server_id=1,
        warning_threshold_pct=75.0,
        critical_threshold_pct=90.0,
    )


def _mock_conn_with_cursor(fetchone_return=None, fetchall_return=None):
    """Build a mock connection whose cursor() context manager yields a working cursor mock."""
    mock_cur = AsyncMock()
    mock_cur.fetchone.return_value = fetchone_return
    mock_cur.fetchall.return_value = fetchall_return or []

    # cursor() must be an async context manager
    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__aenter__ = AsyncMock(return_value=mock_cur)
    mock_cursor_cm.__aexit__ = AsyncMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor_cm
    mock_conn.close = MagicMock()
    return mock_conn, mock_cur


@pytest.mark.asyncio
async def test_mysql_database_exists_true():
    p = _provisioner()
    mock_conn, mock_cur = _mock_conn_with_cursor(fetchone_return=("mydb",))
    with patch.object(p, "_connect", new=AsyncMock(return_value=mock_conn)):
        result = await p.database_exists("mydb")
    assert result is True
    mock_cur.execute.assert_called_once_with("SHOW DATABASES LIKE %s", ("mydb",))
    mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_mysql_database_exists_false():
    p = _provisioner()
    mock_conn, mock_cur = _mock_conn_with_cursor(fetchone_return=None)
    with patch.object(p, "_connect", new=AsyncMock(return_value=mock_conn)):
        result = await p.database_exists("notexist")
    assert result is False


@pytest.mark.asyncio
async def test_mysql_create_database_success():
    p = _provisioner()
    mock_conn, mock_cur = _mock_conn_with_cursor()
    with patch.object(p, "database_exists", new=AsyncMock(return_value=False)), \
         patch.object(p, "_connect", new=AsyncMock(return_value=mock_conn)):
        result = await p.create_database(DatabaseSpec(name="newdb", owner="alice"))
    assert result.success is True
    assert result.db_name == "newdb"


@pytest.mark.asyncio
async def test_mysql_create_database_already_exists():
    p = _provisioner()
    with patch.object(p, "database_exists", new=AsyncMock(return_value=True)):
        result = await p.create_database(DatabaseSpec(name="existing", owner="alice"))
    assert result.success is False
    assert "already exists" in result.message


@pytest.mark.asyncio
async def test_mysql_create_user_success():
    p = _provisioner()
    mock_conn, mock_cur = _mock_conn_with_cursor(fetchone_return=None)  # user doesn't exist
    with patch.object(p, "_connect", new=AsyncMock(return_value=mock_conn)):
        result = await p.create_user(UserSpec(username="alice", password="tr1cky\\'pw", db_name="mydb"))
    assert result.success is True
    # The CREATE USER call must pass the password as a parameter tuple, never interpolated
    create_call = mock_cur.execute.call_args_list[-1]
    sql, params = create_call.args
    assert "IDENTIFIED BY %s" in sql, "password must be a %s placeholder"
    assert params == ("tr1cky\\'pw",), "password must be passed as a parameter, not interpolated"


@pytest.mark.asyncio
async def test_mysql_grant_permissions():
    p = _provisioner()
    mock_conn, mock_cur = _mock_conn_with_cursor()
    with patch.object(p, "_connect", new=AsyncMock(return_value=mock_conn)):
        await p.grant_permissions(PermissionSpec(db_name="mydb", username="alice", privileges=["SELECT", "INSERT"]))
    # Verify cursor.execute was called (GRANT + FLUSH PRIVILEGES)
    assert mock_cur.execute.called


@pytest.mark.asyncio
async def test_mysql_enable_extensions_noop():
    p = _provisioner()
    # Should complete without error — MySQL has no server extensions
    await p.enable_extensions("mydb", ["some_ext"])


@pytest.mark.asyncio
async def test_mysql_get_capacity():
    p = _provisioner()

    # Need cursor to return different values for successive calls:
    # first fetchall -> list of DBs, then fetchone -> status row
    mock_cur = AsyncMock()
    mock_cur.fetchall.return_value = [("db1",), ("db2",)]
    mock_cur.fetchone.return_value = ("Threads_connected", "5")

    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__aenter__ = AsyncMock(return_value=mock_cur)
    mock_cursor_cm.__aexit__ = AsyncMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor_cm
    mock_conn.close = MagicMock()

    with patch.object(p, "_connect", new=AsyncMock(return_value=mock_conn)):
        m = await p.get_capacity()
    assert m.server_id == 1
    assert isinstance(m.db_count, int)
