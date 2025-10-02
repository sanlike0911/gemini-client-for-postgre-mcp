"""設定管理モジュール."""
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv


@dataclass
class ConfigValidationError(Exception):
    """設定検証エラー."""

    field: str
    message: str


@dataclass(frozen=True)
class MCPServerSettings:
    """mcp.json で定義される MCP サーバー設定."""

    name: str
    transport: str  # "stdio" or "sse"
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[float] = None
    read_timeout: Optional[float] = None


@dataclass(frozen=True)
class AppConfig:
    """アプリケーション設定."""

    gemini_api_key: str
    gemini_model: str = "models/gemini-1.5-flash"
    log_level: str = "INFO"
    gemini_system_instruction: Optional[str] = None
    mcp_server: Optional[MCPServerSettings] = None

    def has_mcp_config(self) -> bool:
        """MCP 設定が存在するかチェックする."""

        return self.mcp_server is not None


class ConfigurationManager:
    """設定管理クラス."""

    @staticmethod
    def load_config() -> AppConfig:
        """環境変数と mcp.json から設定を読み込む."""

        load_dotenv()

        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not ConfigurationManager.validate_api_key(gemini_api_key):
            raise ConfigValidationError(
                field="GEMINI_API_KEY",
                message="必須設定項目が見つかりません: GEMINI_API_KEY",
            )

        gemini_model = os.getenv("GEMINI_MODEL", "models/gemini-1.5-flash")
        log_level = os.getenv("LOG_LEVEL", "INFO")
        gemini_system_instruction = os.getenv("GEMINI_SYSTEM_INSTRUCTION")

        mcp_settings = ConfigurationManager._load_mcp_settings()

        return AppConfig(
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
            log_level=log_level,
            gemini_system_instruction=gemini_system_instruction,
            mcp_server=mcp_settings,
        )

    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """API キーの形式を検証する."""

        return bool(api_key and api_key.strip())

    @staticmethod
    def _load_mcp_settings() -> Optional[MCPServerSettings]:
        """mcp.json から MCP サーバー設定を読み込む."""

        config_path = Path(os.getenv("MCP_CONFIG_PATH", "mcp.json"))
        if not config_path.exists():
            return None

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigValidationError(
                field=str(config_path),
                message=f"mcp.json の解析に失敗しました: {exc}",
            ) from exc

        if not isinstance(data, dict):
            raise ConfigValidationError(
                field=str(config_path),
                message="mcp.json の形式が正しくありません (オブジェクトを想定)",
            )

        servers = data.get("mcpServers")
        if not servers:
            return None
        if not isinstance(servers, dict):
            raise ConfigValidationError(
                field="mcpServers",
                message="mcpServers はオブジェクトである必要があります",
            )

        env_selected = os.getenv("MCP_SERVER")
        default_selected = data.get("defaultServer") if isinstance(data.get("defaultServer"), str) else None
        selected_name = env_selected or default_selected
        if selected_name is not None and selected_name not in servers:
            raise ConfigValidationError(
                field="mcpServers",
                message=f"指定された MCP サーバー '{selected_name}' が定義されていません",
            )

        if selected_name is None:
            try:
                selected_name = next(iter(servers))
            except StopIteration:
                return None

        server_def = servers.get(selected_name)
        if not isinstance(server_def, dict):
            raise ConfigValidationError(
                field=f"mcpServers.{selected_name}",
                message="サーバー設定はオブジェクトである必要があります",
            )

        transport = server_def.get("transport")
        if isinstance(transport, str):
            transport = transport.lower().strip()

        if not transport:
            if "command" in server_def:
                transport = "stdio"
            elif "url" in server_def:
                transport = "sse"

        if transport not in {"stdio", "sse"}:
            raise ConfigValidationError(
                field=f"mcpServers.{selected_name}.transport",
                message="transport は 'stdio' または 'sse' を指定してください",
            )

        if transport == "stdio":
            command = server_def.get("command")
            if not isinstance(command, str) or not command.strip():
                raise ConfigValidationError(
                    field=f"mcpServers.{selected_name}.command",
                    message="stdio サーバーには command を指定してください",
                )

            args_raw = server_def.get("args")
            args: Optional[List[str]] = None
            if args_raw is not None:
                if not isinstance(args_raw, list) or not all(isinstance(item, str) for item in args_raw):
                    raise ConfigValidationError(
                        field=f"mcpServers.{selected_name}.args",
                        message="args は文字列の配列である必要があります",
                    )
                args = [item for item in args_raw]

            env_def = server_def.get("env")
            env: Optional[Dict[str, str]] = None
            if env_def is not None:
                if not isinstance(env_def, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env_def.items()):
                    raise ConfigValidationError(
                        field=f"mcpServers.{selected_name}.env",
                        message="env は文字列キーと文字列値のオブジェクトである必要があります",
                    )
                env = {k: v for k, v in env_def.items()}

            return MCPServerSettings(
                name=selected_name,
                transport="stdio",
                command=command,
                args=args,
                env=env,
            )

        url = server_def.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ConfigValidationError(
                field=f"mcpServers.{selected_name}.url",
                message="sse サーバーには url を指定してください",
            )

        headers_def = server_def.get("headers")
        headers: Optional[Dict[str, str]] = None
        if headers_def is not None:
            if not isinstance(headers_def, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in headers_def.items()):
                raise ConfigValidationError(
                    field=f"mcpServers.{selected_name}.headers",
                    message="headers は文字列キーと文字列値のオブジェクトである必要があります",
                )
            headers = {k: v for k, v in headers_def.items()}

        timeout = ConfigurationManager._coerce_float(server_def.get("timeout"), f"mcpServers.{selected_name}.timeout")
        read_timeout = ConfigurationManager._coerce_float(server_def.get("readTimeout"), f"mcpServers.{selected_name}.readTimeout")

        return MCPServerSettings(
            name=selected_name,
            transport="sse",
            url=url,
            headers=headers,
            timeout=timeout,
            read_timeout=read_timeout,
        )

    @staticmethod
    def _coerce_float(value: Optional[object], field_name: str) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigValidationError(
                field=field_name,
                message=f"数値として解釈できません: {value}",
            ) from exc