"""MCP クライアントのテスト."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp_client import MCPClient, MCPConfig, MCPError


@pytest.fixture
def mcp_config():
    """テスト用の MCP 設定."""
    return MCPConfig(
        server_command="python",
        server_args=["server.py"],
        transport="stdio"
    )


@pytest.fixture
def mcp_client(mcp_config):
    """テスト用の MCP クライアント."""
    return MCPClient(config=mcp_config)


def test_mcp_client_initialization(mcp_config):
    """MCP クライアントが正しく初期化されること."""
    client = MCPClient(config=mcp_config)

    assert client is not None
    assert client.config == mcp_config
    assert client.is_connected() is False  # 初期状態では未接続


@pytest.mark.asyncio
async def test_connect_success(mcp_client):
    """MCP サーバーへの接続が成功すること."""
    # stdio_client をモック
    with patch("src.mcp_client.stdio_client") as mock_stdio:
        # コンテキストマネージャーをモック
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        # ClientSession をモック
        with patch("src.mcp_client.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.initialize = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            result = await mcp_client.connect()

            assert result is True
            assert mcp_client.is_connected() is True


@pytest.mark.asyncio
async def test_connect_failure(mcp_client):
    """MCP サーバーへの接続が失敗すること."""
    # stdio_client で例外を発生させる
    with patch("src.mcp_client.stdio_client") as mock_stdio:
        mock_stdio.side_effect = ConnectionError("Failed to connect")

        result = await mcp_client.connect()

        assert result is False
        assert mcp_client.is_connected() is False


@pytest.mark.asyncio
async def test_get_context_success(mcp_client):
    """コンテキスト情報の取得が成功すること."""
    # 接続状態をモック
    with patch("src.mcp_client.stdio_client") as mock_stdio:
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("src.mcp_client.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.initialize = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            # list_resources をモック
            mock_resource = MagicMock()
            mock_resource.name = "test_resource"
            mock_resource.uri = "file:///test"
            mock_session.list_resources = AsyncMock(return_value=MagicMock(resources=[mock_resource]))

            mock_session_class.return_value = mock_session

            await mcp_client.connect()
            context = await mcp_client.get_context()

            assert context is not None
            assert isinstance(context, str)
            assert "test_resource" in context or "file:///test" in context


@pytest.mark.asyncio
async def test_get_context_when_not_connected(mcp_client):
    """未接続時にコンテキスト取得が None を返すこと."""
    context = await mcp_client.get_context()

    assert context is None


@pytest.mark.asyncio
async def test_get_context_failure(mcp_client):
    """コンテキスト取得失敗時に MCPError が発生すること."""
    # 接続状態をモック
    with patch("src.mcp_client.stdio_client") as mock_stdio:
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("src.mcp_client.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.initialize = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            # list_resources でエラーを発生させる
            mock_session.list_resources = AsyncMock(side_effect=Exception("Protocol error"))

            mock_session_class.return_value = mock_session

            await mcp_client.connect()

            with pytest.raises(MCPError) as exc_info:
                await mcp_client.get_context()

            assert exc_info.value.error_type == "protocol"


@pytest.mark.asyncio
async def test_disconnect(mcp_client):
    """MCP サーバーから切断できること."""
    # 接続状態をモック
    with patch("src.mcp_client.stdio_client") as mock_stdio:
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("src.mcp_client.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.initialize = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            await mcp_client.connect()
            assert mcp_client.is_connected() is True

            await mcp_client.disconnect()

            assert mcp_client.is_connected() is False


def test_is_connected_initially_false(mcp_client):
    """初期状態で未接続であること."""
    assert mcp_client.is_connected() is False


def test_mcp_config_dataclass():
    """MCPConfig データクラスが正しく動作すること."""
    config = MCPConfig(
        server_command="python",
        server_args=["server.py", "--port", "8080"],
        transport="stdio"
    )

    assert config.server_command == "python"
    assert config.server_args == ["server.py", "--port", "8080"]
    assert config.transport == "stdio"


def test_mcp_error_dataclass():
    """MCPError データクラスが正しく動作すること."""
    error = MCPError(
        error_type="connection",
        message="接続に失敗しました"
    )

    assert error.error_type == "connection"
    assert error.message == "接続に失敗しました"