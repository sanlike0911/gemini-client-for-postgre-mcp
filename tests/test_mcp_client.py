"""MCP クライアントのテスト."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp_client import MCPClient, MCPConfig, MCPError


@pytest.fixture
def mcp_config() -> MCPConfig:
    return MCPConfig(
        transport="stdio",
        server_command="python",
        server_args=["server.py"],
    )


@pytest.fixture
def mcp_client(mcp_config) -> MCPClient:
    return MCPClient(config=mcp_config)


def test_mcp_client_initialization(mcp_config):
    client = MCPClient(config=mcp_config)

    assert client is not None
    assert client.config == mcp_config
    assert client.is_connected() is False


@pytest.mark.asyncio
async def test_connect_success_stdio(mcp_client):
    with patch("src.mcp_client.stdio_client") as mock_stdio, \
         patch("src.mcp_client.ClientSession") as mock_session_class:

        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        result = await mcp_client.connect()

        assert result is True
        assert mcp_client.is_connected() is True


@pytest.mark.asyncio
async def test_connect_failure_stdio(mcp_client):
    with patch("src.mcp_client.stdio_client") as mock_stdio:
        mock_stdio.side_effect = ConnectionError("Failed to connect")

        result = await mcp_client.connect()

        assert result is False
        assert mcp_client.is_connected() is False


@pytest.mark.asyncio
async def test_connect_success_sse():
    config = MCPConfig(
        transport="sse",
        sse_url="http://localhost:8000/sse",
        sse_headers={"Authorization": "Bearer token"},
        sse_timeout=10.0,
        sse_read_timeout=20.0,
    )
    client = MCPClient(config=config)

    with patch("src.mcp_client.sse_client") as mock_sse, \
         patch("src.mcp_client.ClientSession") as mock_session_class:

        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_sse.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_sse.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        result = await client.connect()

        assert result is True
        assert client.is_connected() is True
        mock_sse.assert_called_once_with(
            url="http://localhost:8000/sse",
            headers={"Authorization": "Bearer token"},
            timeout=10.0,
            sse_read_timeout=20.0,
        )


@pytest.mark.asyncio
async def test_connect_sse_missing_url():
    config = MCPConfig(transport="sse")
    client = MCPClient(config=config)

    result = await client.connect()

    assert result is False
    assert client.is_connected() is False


@pytest.mark.asyncio
async def test_list_tools_caches_results(mcp_client):
    with patch("src.mcp_client.stdio_client") as mock_stdio, \
         patch("src.mcp_client.ClientSession") as mock_session_class:

        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_tool = MagicMock()
        mock_tool.name = "execute_sql"
        mock_tool.description = "Execute SQL"

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[mock_tool]))
        mock_session_class.return_value = mock_session

        await mcp_client.connect()

        tools = await mcp_client.list_tools()
        assert len(tools) == 1
        mock_session.list_tools.assert_awaited_once()

        await mcp_client.list_tools()
        mock_session.list_tools.assert_awaited_once()

        await mcp_client.list_tools(force_refresh=True)
        assert mock_session.list_tools.await_count == 2


@pytest.mark.asyncio
async def test_list_tools_failure_raises(mcp_client):
    with patch("src.mcp_client.stdio_client") as mock_stdio, \
         patch("src.mcp_client.ClientSession") as mock_session_class:

        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.list_tools = AsyncMock(side_effect=Exception("boom"))
        mock_session_class.return_value = mock_session

        await mcp_client.connect()

        with pytest.raises(MCPError) as exc_info:
            await mcp_client.list_tools(force_refresh=True)

        assert exc_info.value.error_type == "protocol"


@pytest.mark.asyncio
async def test_call_tool_success(mcp_client):
    with patch("src.mcp_client.stdio_client") as mock_stdio, \
         patch("src.mcp_client.ClientSession") as mock_session_class:

        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        tool_result = MagicMock()
        tool_result.isError = False

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.call_tool = AsyncMock(return_value=tool_result)
        mock_session_class.return_value = mock_session

        await mcp_client.connect()

        result = await mcp_client.call_tool("execute_sql", {"sql": "SELECT 1"})

        assert result is tool_result
        mock_session.call_tool.assert_awaited_once_with(
            name="execute_sql",
            arguments={"sql": "SELECT 1"},
            read_timeout_seconds=None,
        )


@pytest.mark.asyncio
async def test_call_tool_failure_raises(mcp_client):
    with patch("src.mcp_client.stdio_client") as mock_stdio, \
         patch("src.mcp_client.ClientSession") as mock_session_class:

        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.call_tool = AsyncMock(side_effect=Exception("timeout"))
        mock_session_class.return_value = mock_session

        await mcp_client.connect()

        with pytest.raises(MCPError) as exc_info:
            await mcp_client.call_tool("execute_sql", {"sql": "SELECT 1"})

        assert exc_info.value.error_type == "tool"


def test_render_tool_result_handles_content():
    from types import SimpleNamespace

    result = MagicMock()
    result.isError = False
    result.structuredContent = {"rows": 1}
    result.content = [
        SimpleNamespace(text="id\tname\n1\tAlice"),
        SimpleNamespace(data="metadata"),
    ]

    text = MCPClient.render_tool_result(result)

    assert "rows" in text
    assert "Alice" in text
    assert "metadata" in text


@pytest.mark.asyncio
async def test_get_context_success(mcp_client):
    with patch("src.mcp_client.stdio_client") as mock_stdio, \
         patch("src.mcp_client.ClientSession") as mock_session_class:

        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_resource = MagicMock()
        mock_resource.name = "test_resource"
        mock_resource.uri = "file:///test"

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.list_resources = AsyncMock(return_value=MagicMock(resources=[mock_resource]))
        mock_session_class.return_value = mock_session

        await mcp_client.connect()
        context = await mcp_client.get_context()

        assert context is not None
        assert "test_resource" in context


@pytest.mark.asyncio
async def test_get_context_when_not_connected(mcp_client):
    context = await mcp_client.get_context()
    assert context is None


@pytest.mark.asyncio
async def test_get_context_failure(mcp_client):
    with patch("src.mcp_client.stdio_client") as mock_stdio, \
         patch("src.mcp_client.ClientSession") as mock_session_class:

        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.list_resources = AsyncMock(side_effect=Exception("Protocol error"))
        mock_session_class.return_value = mock_session

        await mcp_client.connect()

        with pytest.raises(MCPError) as exc_info:
            await mcp_client.get_context()

        assert exc_info.value.error_type == "protocol"


@pytest.mark.asyncio
async def test_disconnect(mcp_client):
    with patch("src.mcp_client.stdio_client") as mock_stdio, \
         patch("src.mcp_client.ClientSession") as mock_session_class:

        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.initialize = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        await mcp_client.connect()
        await mcp_client.disconnect()

        assert mcp_client.is_connected() is False


def test_is_connected_initially_false(mcp_client):
    assert mcp_client.is_connected() is False


def test_mcp_config_dataclass():
    config = MCPConfig(
        transport="sse",
        server_command="python",
        server_args=["server.py", "--port", "8080"],
        sse_url="http://localhost:8000/sse",
        sse_headers={"Authorization": "Bearer token"},
        sse_timeout=10.0,
        sse_read_timeout=15.0,
    )

    assert config.transport == "sse"
    assert config.server_command == "python"
    assert config.server_args == ["server.py", "--port", "8080"]
    assert config.sse_url == "http://localhost:8000/sse"
    assert config.sse_headers == {"Authorization": "Bearer token"}
    assert config.sse_timeout == 10.0
    assert config.sse_read_timeout == 15.0


def test_mcp_error_dataclass():
    error = MCPError(
        error_type="connection",
        message="接続に失敗しました",
    )

    assert error.error_type == "connection"
    assert error.message == "接続に失敗しました"
