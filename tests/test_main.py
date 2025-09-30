"""メインエントリーポイントのテスト."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.main import main


@pytest.mark.asyncio
async def test_main_with_valid_config(monkeypatch):
    """有効な設定でアプリケーションが起動すること."""
    # 環境変数を設定
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")

    with patch("src.main.ConfigurationManager") as mock_config_manager, \
         patch("src.main.Application") as mock_app_class, \
         patch("src.main.setup_logging") as mock_setup_logging, \
         patch("builtins.input", side_effect=KeyboardInterrupt()):

        # 設定をモック
        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config_manager.load_config.return_value = mock_config

        # アプリケーションをモック
        mock_app = MagicMock()
        mock_app.start = AsyncMock()
        mock_app.shutdown = AsyncMock()
        mock_app.is_mcp_connected = MagicMock(return_value=False)
        mock_app_class.return_value = mock_app

        # main を実行
        result = await main()

        # ログ設定が呼ばれること
        assert mock_setup_logging.call_count == 2  # デフォルトと設定後

        # アプリケーションが起動されること
        mock_app.start.assert_called_once()

        # シャットダウンが呼ばれること
        mock_app.shutdown.assert_called_once()

        # 正常終了
        assert result == 0


@pytest.mark.asyncio
async def test_main_with_config_error(monkeypatch):
    """設定エラー時にアプリケーションが終了すること."""
    # 環境変数を削除
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with patch("src.main.ConfigurationManager") as mock_config_manager, \
         patch("src.main.setup_logging") as mock_setup_logging, \
         patch("src.main.load_dotenv"):

        # 設定エラーをモック
        from src.config import ConfigValidationError
        mock_config_manager.load_config.side_effect = ConfigValidationError(
            field="GEMINI_API_KEY",
            message="必須設定項目が見つかりません"
        )

        # main を実行
        result = await main()

        # エラーコードが返されること
        assert result == 1


@pytest.mark.asyncio
async def test_main_handles_keyboard_interrupt(monkeypatch):
    """KeyboardInterrupt でアプリケーションが正常終了すること."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")

    with patch("src.main.ConfigurationManager") as mock_config_manager, \
         patch("src.main.Application") as mock_app_class, \
         patch("src.main.setup_logging"), \
         patch("builtins.input", side_effect=KeyboardInterrupt()):

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config_manager.load_config.return_value = mock_config

        mock_app = MagicMock()
        mock_app.start = AsyncMock()
        mock_app.shutdown = AsyncMock()
        mock_app.is_mcp_connected = MagicMock(return_value=False)
        mock_app_class.return_value = mock_app

        result = await main()

        # シャットダウンが呼ばれること
        mock_app.shutdown.assert_called_once()

        # 正常終了コード
        assert result == 0