"""アプリケーション層のテスト."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application import Application
from src.config import AppConfig


@pytest.fixture
def app_config():
    """テスト用のアプリケーション設定."""
    return AppConfig(
        gemini_api_key="test_api_key",
        mcp_server_command="python",
        mcp_server_args=["server.py"],
        mcp_transport="stdio",
        log_level="INFO",
        gemini_model="models/gemini-1.5-flash"
    )


@pytest.fixture
def app_config_without_mcp():
    """MCP なしのアプリケーション設定."""
    return AppConfig(
        gemini_api_key="test_api_key",
        mcp_server_command=None,
        mcp_server_args=None,
        mcp_transport="stdio",
        log_level="INFO",
        gemini_model="models/gemini-1.5-flash"
    )


def test_application_initialization(app_config):
    """Application が正しく初期化されること."""
    app = Application(config=app_config)

    assert app is not None
    assert app.config == app_config


@pytest.mark.asyncio
async def test_start_with_mcp(app_config):
    """MCP 付きでアプリケーションが起動すること."""
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        # モックを設定
        mock_gemini = MagicMock()
        mock_gemini_class.return_value = mock_gemini

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=True)
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config)
        await app.start()

        # Gemini クライアントが初期化されること
        mock_gemini_class.assert_called_once_with(
            api_key="test_api_key",
            model="models/gemini-1.5-flash"
        )

        # MCP クライアントが初期化され、接続されること
        mock_mcp_class.assert_called_once()
        mock_mcp.connect.assert_called_once()


@pytest.mark.asyncio
async def test_start_without_mcp(app_config_without_mcp):
    """MCP なしでアプリケーションが起動すること."""
    with patch("src.application.GeminiClient") as mock_gemini_class:
        mock_gemini = MagicMock()
        mock_gemini_class.return_value = mock_gemini

        app = Application(config=app_config_without_mcp)
        await app.start()

        # Gemini クライアントが初期化されること
        mock_gemini_class.assert_called_once()


@pytest.mark.asyncio
async def test_start_with_mcp_connection_failure(app_config):
    """MCP 接続失敗時もアプリケーションが起動すること."""
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        mock_gemini = MagicMock()
        mock_gemini_class.return_value = mock_gemini

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=False)  # 接続失敗
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config)
        await app.start()

        # アプリケーションは起動すること（MCP 接続失敗は無視）
        mock_gemini_class.assert_called_once()


@pytest.mark.asyncio
async def test_handle_user_message_without_mcp(app_config_without_mcp):
    """MCP なしでユーザーメッセージを処理できること."""
    with patch("src.application.GeminiClient") as mock_gemini_class:
        mock_gemini = MagicMock()
        mock_gemini.send_message = AsyncMock(return_value="応答テキスト")
        mock_gemini_class.return_value = mock_gemini

        app = Application(config=app_config_without_mcp)
        await app.start()

        response = await app.handle_user_message("こんにちは")

        assert response == "応答テキスト"
        mock_gemini.send_message.assert_called_once_with("こんにちは", context=None)


@pytest.mark.asyncio
async def test_handle_user_message_with_mcp(app_config):
    """MCP 付きでユーザーメッセージを処理できること."""
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        mock_gemini = MagicMock()
        mock_gemini.send_message = AsyncMock(return_value="応答テキスト")
        mock_gemini_class.return_value = mock_gemini

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=True)
        mock_mcp.is_connected = MagicMock(return_value=True)
        mock_mcp.get_context = AsyncMock(return_value="MCP context")
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config)
        await app.start()

        response = await app.handle_user_message("データベースの情報")

        assert response == "応答テキスト"
        # MCP コンテキストを取得してから Gemini に送信
        mock_mcp.get_context.assert_called_once()
        mock_gemini.send_message.assert_called_once_with("データベースの情報", context="MCP context")


@pytest.mark.asyncio
async def test_handle_user_message_with_error(app_config_without_mcp):
    """エラー発生時に適切に処理されること."""
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
async def test_shutdown(app_config):
    """アプリケーションが正しく終了すること."""
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        mock_gemini = MagicMock()
        mock_gemini_class.return_value = mock_gemini

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=True)
        mock_mcp.disconnect = AsyncMock()
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config)
        await app.start()
        await app.shutdown()

        # MCP クライアントが切断されること
        mock_mcp.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_is_mcp_connected(app_config):
    """MCP 接続状態を確認できること."""
    with patch("src.application.GeminiClient") as mock_gemini_class, \
         patch("src.application.MCPClient") as mock_mcp_class:

        mock_gemini = MagicMock()
        mock_gemini_class.return_value = mock_gemini

        mock_mcp = MagicMock()
        mock_mcp.connect = AsyncMock(return_value=True)
        mock_mcp.is_connected = MagicMock(return_value=True)
        mock_mcp_class.return_value = mock_mcp

        app = Application(config=app_config)
        await app.start()

        assert app.is_mcp_connected() is True