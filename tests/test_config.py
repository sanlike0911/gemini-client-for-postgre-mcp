"""設定管理モジュールのテスト."""
import json
from pathlib import Path

import pytest

from src.config import AppConfig, ConfigurationManager, ConfigValidationError, MCPServerSettings


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    """各テスト前に関連する環境変数と load_dotenv をリセットする."""

    monkeypatch.setattr("src.config.load_dotenv", lambda *_, **__: None)
    for key in [
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_SYSTEM_INSTRUCTION",
        "LOG_LEVEL",
        "MCP_CONFIG_PATH",
        "MCP_SERVER",
    ]:
        monkeypatch.delenv(key, raising=False)


def write_mcp_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_load_config_with_valid_api_key_without_mcp(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
    monkeypatch.setenv("MCP_CONFIG_PATH", str(tmp_path / "missing.json"))

    config = ConfigurationManager.load_config()

    assert config.gemini_api_key == "test_api_key"
    assert config.mcp_server is None


def test_load_config_with_mcp_stdio(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
    mcp_path = tmp_path / "mcp.json"
    write_mcp_config(
        mcp_path,
        {
            "mcpServers": {
                "postgres": {
                    "command": "python",
                    "args": ["server.py", "--port", "8080"],
                    "env": {"ENV": "dev"},
                }
            }
        },
    )
    monkeypatch.setenv("MCP_CONFIG_PATH", str(mcp_path))

    config = ConfigurationManager.load_config()

    assert isinstance(config.mcp_server, MCPServerSettings)
    assert config.mcp_server.transport == "stdio"
    assert config.mcp_server.command == "python"
    assert config.mcp_server.args == ["server.py", "--port", "8080"]
    assert config.mcp_server.env == {"ENV": "dev"}


def test_load_config_with_mcp_sse(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
    mcp_path = tmp_path / "mcp.json"
    write_mcp_config(
        mcp_path,
        {
            "defaultServer": "postgres-remote",
            "mcpServers": {
                "postgres-remote": {
                    "transport": "sse",
                    "url": "https://example.com/sse",
                    "headers": {"Authorization": "Bearer token"},
                    "timeout": 5,
                    "readTimeout": 30,
                }
            },
        },
    )
    monkeypatch.setenv("MCP_CONFIG_PATH", str(mcp_path))

    config = ConfigurationManager.load_config()

    assert config.mcp_server is not None
    assert config.mcp_server.transport == "sse"
    assert config.mcp_server.url == "https://example.com/sse"
    assert config.mcp_server.headers == {"Authorization": "Bearer token"}
    assert config.mcp_server.timeout == 5.0
    assert config.mcp_server.read_timeout == 30.0


def test_load_config_with_invalid_transport(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
    mcp_path = tmp_path / "mcp.json"
    write_mcp_config(
        mcp_path,
        {
            "mcpServers": {
                "bad": {"transport": "ws"}
            }
        },
    )
    monkeypatch.setenv("MCP_CONFIG_PATH", str(mcp_path))

    with pytest.raises(ConfigValidationError) as exc_info:
        ConfigurationManager.load_config()

    assert exc_info.value.field == "mcpServers.bad.transport"


def test_load_config_with_missing_sse_url(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
    mcp_path = tmp_path / "mcp.json"
    write_mcp_config(
        mcp_path,
        {
            "mcpServers": {
                "remote": {"transport": "sse"}
            }
        },
    )
    monkeypatch.setenv("MCP_CONFIG_PATH", str(mcp_path))

    with pytest.raises(ConfigValidationError) as exc_info:
        ConfigurationManager.load_config()

    assert exc_info.value.field == "mcpServers.remote.url"


def test_validate_api_key():
    assert ConfigurationManager.validate_api_key("valid_key") is True
    assert ConfigurationManager.validate_api_key("  ") is False
    assert ConfigurationManager.validate_api_key("") is False