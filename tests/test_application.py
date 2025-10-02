"""アプリケーション層のテスト."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application import Application
from src.config import AppConfig, MCPServerSettings


@pytest.fixture
def app_config_stdio() -> AppConfig:
    return AppConfig(
        gemini_api_key="test_api_key",
        mcp_server=MCPServerSettings(
            name="local",
            transport="stdio",
            command="python",
            args=["server.py"],
        ),
    )


@pytest.fixture
def app_config_sse() -> AppConfig:
    return AppConfig(
        gemini_api_key="test_api_key",
        mcp_server=MCPServerSettings(
            name="remote",
            transport="sse",
            url="http://localhost:8000/sse",
            headers={"Authorization": "Bearer token"},
            timeout=10.0,
            read_timeout=120.0,
        ),
    )


@pytest.fixture
def app_config_without_mcp() -> AppConfig:
    return AppConfig(
        gemini_api_key="test_api_key",
    )


def test_application_initialization(app_config_stdio):
    app = Application(config=app_config_stdio)

    assert app is not None
    assert app.config == app_config_stdio


@pytest.mark.asyncio
async def test_start_with_mcp_fetches_tools(app_config_stdio):
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        mock_gemini_class.return_value = MagicMock()

        mock_tool = MagicMock()
        mock_tool.name = "execute_sql"
        mock_tool.description = "Execute read-only SQL"

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=True)
        mock_mcp.list_tools = AsyncMock(return_value=[mock_tool])
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config_stdio)
        await app.start()

        mock_gemini_class.assert_called_once()
        mock_mcp_class.assert_called_once()
        mock_mcp.connect.assert_awaited_once()
        mock_mcp.list_tools.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_sse_configuration(app_config_sse):
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        mock_gemini_class.return_value = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=True)
        mock_mcp.list_tools = AsyncMock(return_value=[])
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config_sse)
        await app.start()

        passed_config = mock_mcp_class.call_args.kwargs.get("config") or mock_mcp_class.call_args.args[0]
        assert passed_config.transport == "sse"
        assert passed_config.sse_url == "http://localhost:8000/sse"
        assert passed_config.sse_headers == {"Authorization": "Bearer token"}
        assert passed_config.sse_timeout == 10.0
        assert passed_config.sse_read_timeout == 120.0


@pytest.mark.asyncio
async def test_start_without_mcp(app_config_without_mcp):
    with patch("src.application.GeminiClient") as mock_gemini_class:
        mock_gemini_class.return_value = MagicMock()

        app = Application(config=app_config_without_mcp)
        await app.start()

        mock_gemini_class.assert_called_once()


@pytest.mark.asyncio
async def test_handle_user_message_without_mcp(app_config_without_mcp):
    with patch("src.application.GeminiClient") as mock_gemini_class:
        mock_gemini = MagicMock()
        mock_gemini.send_message = AsyncMock(return_value="応答テキスト")
        mock_gemini_class.return_value = mock_gemini

        app = Application(config=app_config_without_mcp)
        await app.start()

        response = await app.handle_user_message("こんにちは")

        assert response == "応答テキスト"
        mock_gemini.send_message.assert_awaited_once()
        args, kwargs = mock_gemini.send_message.await_args
        assert args[0] == "こんにちは"
        assert "context" not in kwargs


@pytest.mark.asyncio
async def test_handle_user_message_with_mcp_tool_plan(app_config_stdio):
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        mock_gemini = MagicMock()
        mock_gemini.send_json = AsyncMock(return_value={
            "action": "call_tool",
            "tool": "execute_sql",
            "arguments": {"sql": "SELECT * FROM employees"},
        })
        mock_gemini.send_message = AsyncMock(return_value="最終回答")
        mock_gemini_class.return_value = mock_gemini

        mock_tool = MagicMock()
        mock_tool.name = "execute_sql"
        mock_tool.description = "Execute read-only SQL"

        tool_result = MagicMock()
        tool_result.isError = False
        tool_result.content = [MagicMock(text="id\tname\n1\tAlice")]
        tool_result.structuredContent = None

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=True)
        mock_mcp.list_tools = AsyncMock(return_value=[mock_tool])
        mock_mcp.call_tool = AsyncMock(return_value=tool_result)
        mock_mcp.is_connected = MagicMock(return_value=True)
        mock_mcp.get_context = AsyncMock(return_value="context")
        mock_mcp.render_tool_result = MagicMock(return_value="id name\n1 Alice")
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config_stdio)
        await app.start()

        response = await app.handle_user_message("社員一覧を教えて")

        assert response == "最終回答"
        mock_gemini.send_json.assert_awaited_once()
        mock_mcp.call_tool.assert_awaited_once_with("execute_sql", {"sql": "SELECT * FROM employees"})
        mock_gemini.send_message.assert_awaited_once()
        assert mock_gemini.send_message.await_args.kwargs["persist_history"] is False


@pytest.mark.asyncio
async def test_handle_user_message_with_mcp_direct_response(app_config_stdio):
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        mock_gemini = MagicMock()
        mock_gemini.send_json = AsyncMock(return_value={"action": "respond", "message": "対応しました"})
        mock_gemini.send_message = AsyncMock()
        mock_gemini_class.return_value = mock_gemini

        mock_tool = MagicMock()
        mock_tool.name = "execute_sql"
        mock_tool.description = "Execute"

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=True)
        mock_mcp.list_tools = AsyncMock(return_value=[mock_tool])
        mock_mcp.call_tool = AsyncMock()
        mock_mcp.is_connected = MagicMock(return_value=True)
        mock_mcp.get_context = AsyncMock(return_value="context")
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config_stdio)
        await app.start()

        response = await app.handle_user_message("社員数は？")

        assert response == "対応しました"
        mock_mcp.call_tool.assert_not_called()
        mock_gemini.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_handle_user_message_error(app_config_without_mcp):
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.ErrorHandler") as mock_error_handler_class:

        mock_gemini = MagicMock()
        error = Exception("API Error")
        mock_gemini.send_message = AsyncMock(side_effect=error)
        mock_gemini_class.return_value = mock_gemini

        mock_error_context = MagicMock()
        mock_error_context.user_message = "エラーが発生しました"
        mock_error_handler_class.handle_error = MagicMock(return_value=mock_error_context)

        app = Application(config=app_config_without_mcp)
        await app.start()

        response = await app.handle_user_message("テスト")

        assert response == "エラーが発生しました"
        mock_error_handler_class.handle_error.assert_called_once_with(error, context="メッセージ処理中")


@pytest.mark.asyncio
async def test_shutdown(app_config_stdio):
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        mock_gemini_class.return_value = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=True)
        mock_mcp.disconnect = AsyncMock()
        mock_mcp.list_tools = AsyncMock(return_value=[])
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config_stdio)
        await app.start()
        await app.shutdown()

        mock_mcp.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_is_mcp_connected(app_config_stdio):
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        mock_gemini_class.return_value = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=True)
        mock_mcp.is_connected = MagicMock(return_value=True)
        mock_mcp.list_tools = AsyncMock(return_value=[])
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config_stdio)
        await app.start()

        assert app.is_mcp_connected() is True


def test_app_config_has_mcp_config():
    stdio_config = AppConfig(
        gemini_api_key="key",
        mcp_server=MCPServerSettings(
            name="stdio",
            transport="stdio",
            command="python",
            args=["server.py"],
        ),
    )
    sse_config = AppConfig(
        gemini_api_key="key",
        mcp_server=MCPServerSettings(
            name="sse",
            transport="sse",
            url="http://localhost:8000/sse",
        ),
    )
    none_config = AppConfig(
        gemini_api_key="key",
    )

    assert stdio_config.has_mcp_config() is True
    assert sse_config.has_mcp_config() is True
    assert none_config.has_mcp_config() is False