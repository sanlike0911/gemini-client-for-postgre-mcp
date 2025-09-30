"""設定管理モジュール."""
import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv


@dataclass
class ConfigValidationError(Exception):
    """設定検証エラー."""

    field: str
    message: str


@dataclass(frozen=True)
class AppConfig:
    """アプリケーション設定."""

    gemini_api_key: str
    mcp_server_command: Optional[str]
    mcp_server_args: Optional[List[str]]
    mcp_transport: str = "stdio"
    log_level: str = "INFO"
    gemini_model: str = "models/gemini-1.5-flash"

    def has_mcp_config(self) -> bool:
        """MCP 設定が存在するかチェックする.

        Returns:
            MCP サーバーコマンドが設定されている場合 True
        """
        return self.mcp_server_command is not None


class ConfigurationManager:
    """設定管理クラス."""

    @staticmethod
    def load_config() -> AppConfig:
        """環境変数から設定を読み込む.

        Returns:
            検証済みのアプリケーション設定

        Raises:
            ConfigValidationError: 必須設定が存在しない場合
        """
        # .env ファイルを読み込み
        load_dotenv()

        # 必須: Gemini API キー
        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not ConfigurationManager.validate_api_key(gemini_api_key):
            raise ConfigValidationError(
                field="GEMINI_API_KEY",
                message="必須設定項目が見つかりません: GEMINI_API_KEY"
            )

        # オプション: Gemini モデル
        gemini_model = os.getenv("GEMINI_MODEL", "models/gemini-1.5-flash")

        # オプション: MCP サーバー設定
        mcp_server_command = os.getenv("MCP_SERVER_COMMAND")
        mcp_server_args = None
        if mcp_server_command:
            args_str = os.getenv("MCP_SERVER_ARGS", "")
            if args_str:
                # カンマまたはスペースで分割
                mcp_server_args = [arg.strip() for arg in args_str.replace(",", " ").split() if arg.strip()]

        mcp_transport = os.getenv("MCP_TRANSPORT", "stdio")

        # オプション: ログレベル
        log_level = os.getenv("LOG_LEVEL", "INFO")

        return AppConfig(
            gemini_api_key=gemini_api_key,
            mcp_server_command=mcp_server_command,
            mcp_server_args=mcp_server_args,
            mcp_transport=mcp_transport,
            log_level=log_level,
            gemini_model=gemini_model
        )

    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """API キーの形式を検証する.

        Args:
            api_key: 検証するAPI キー

        Returns:
            有効な場合 True、無効な場合 False
        """
        return bool(api_key and api_key.strip())