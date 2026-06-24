import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_mysql_query_dispatched_via_aiomysql():
    """Engine=mysql should use aiomysql, not asyncpg."""
    from app.api.v1.databases import _run_mysql_query
    mock_conn = AsyncMock()
    mock_conn.fetchall.return_value = [(1, "alice")]
    mock_conn.description = (("id", None), ("name", None))
    result = await _run_mysql_query(mock_conn, "SELECT id, name FROM users")
    assert result.columns == ["id", "name"]
    assert result.rows == [[1, "alice"]]
    assert result.row_count == 1


@pytest.mark.asyncio
async def test_mongodb_find_query():
    """Engine=mongodb with op=find returns rows from motor cursor."""
    from app.api.v1.databases import _run_mongodb_query
    import json
    docs = [{"_id": "abc", "name": "Alice"}, {"_id": "def", "name": "Bob"}]
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=docs)
    mock_col = MagicMock()
    mock_col.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_client = MagicMock()
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    payload = json.dumps({"op": "find", "coll": "users", "filter": {}, "limit": 100})
    result = await _run_mongodb_query(mock_client, payload)
    assert result.row_count == 2
    assert "_id" in result.columns or "name" in result.columns


@pytest.mark.asyncio
async def test_mongodb_list_collections():
    from app.api.v1.databases import _run_mongodb_query
    import json
    mock_db = MagicMock()
    mock_db.list_collection_names = AsyncMock(return_value=["users", "orders"])
    mock_client = MagicMock()
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    payload = json.dumps({"op": "list_collections"})
    result = await _run_mongodb_query(mock_client, payload)
    assert result.row_count == 2
    assert "collection" in result.columns


@pytest.mark.asyncio
async def test_qdrant_list_query():
    from app.api.v1.databases import _run_qdrant_query
    import httpx, json
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {"collections": [{"name": "a"}, {"name": "b"}]}}
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = mock_response
    payload = json.dumps({"op": "list"})
    with patch("app.api.v1.databases.httpx.AsyncClient", return_value=mock_client):
        result = await _run_qdrant_query("http://localhost:6333", None, payload)
    assert result.row_count == 2
    assert "collection" in result.columns
