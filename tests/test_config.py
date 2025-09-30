"""設定管理のテスト."""
import os
from typing import List, Optional

import pytest

from src.config import AppConfig, ConfigurationManager, ConfigValidationError


def test_load_config_with_valid_api_key(monkeypatch):
    """有効なAPI キーで設定が読み込まれること."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key_123")

    config = ConfigurationManager.load_config()

    assert config.gemini_api_key == "test_api_key_123"
    assert config.gemini_model == "models/gemini-1.5-flash"  # デフォルト値


def test_load_config_without_api_key_raises_error(monkeypatch):
    """API キーが設定されていない場合、ConfigValidationError が発生すること."""
    # すべての関連環境変数を削除
    for key in ["GEMINI_API_KEY", "GEMINI_MODEL", "MCP_SERVER_COMMAND",
                "MCP_SERVER_ARGS", "MCP_TRANSPORT", "LOG_LEVEL"]:
        monkeypatch.delenv(key, raising=False)

    # load_dotenv() をモックして何もロードしないようにする
    monkeypatch.setattr("src.config.load_dotenv", lambda: None)

    with pytest.raises(ConfigValidationError) as exc_info:
        ConfigurationManager.load_config()

    assert exc_info.value.field == "GEMINI_API_KEY"
    assert "必須" in exc_info.value.message


def test_load_config_with_custom_model(monkeypatch):
    """カスタムモデル名が読み込まれること."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")

    config = ConfigurationManager.load_config()

    assert config.gemini_model == "gemini-1.5-pro"


def test_load_config_with_mcp_settings(monkeypatch):
    """MCP サーバー設定が読み込まれること."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "python")
    monkeypatch.setenv("MCP_SERVER_ARGS", "server.py,--port,8080")
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")

    config = ConfigurationManager.load_config()

    assert config.mcp_server_command == "python"
    assert config.mcp_server_args == ["server.py", "--port", "8080"]
    assert config.mcp_transport == "stdio"


def test_load_config_without_mcp_settings(monkeypatch):
    """MCP 設定がない場合、None になること."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
    monkeypatch.delenv("MCP_SERVER_COMMAND", raising=False)

    config = ConfigurationManager.load_config()

    assert config.mcp_server_command is None
    assert config.mcp_server_args is None


def test_load_config_with_log_level(monkeypatch):
    """ログレベルが読み込まれること."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    config = ConfigurationManager.load_config()

    assert config.log_level == "DEBUG"


def test_app_config_has_mcp_config():
    """has_mcp_config メソッドが正しく動作すること."""
    config_with_mcp = AppConfig(
        gemini_api_key="test_key",
        mcp_server_command="python",
        mcp_server_args=["server.py"],
        mcp_transport="stdio",
        log_level="INFO",
        gemini_model="models/gemini-1.5-flash"
    )

    config_without_mcp = AppConfig(
        gemini_api_key="test_key",
        mcp_server_command=None,
        mcp_server_args=None,
        mcp_transport="stdio",
        log_level="INFO",
        gemini_model="models/gemini-1.5-flash"
    )

    assert config_with_mcp.has_mcp_config() is True
    assert config_without_mcp.has_mcp_config() is False


def test_validate_api_key_with_valid_key():
    """有効なAPI キーの検証が成功すること."""
    assert ConfigurationManager.validate_api_key("valid_key_123") is True
    assert ConfigurationManager.validate_api_key("AIzaSyABC123xyz") is True


def test_validate_api_key_with_empty_key():
    """空のAPI キーの検証が失敗すること."""
    assert ConfigurationManager.validate_api_key("") is False
    assert ConfigurationManager.validate_api_key("   ") is False