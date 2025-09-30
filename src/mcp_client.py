"""MCP クライアントモジュール."""
import logging
from dataclasses import dataclass
from typing import List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


@dataclass
class MCPConfig:
    """MCP 設定."""

    server_command: str  # e.g., "python"
    server_args: List[str]  # e.g., ["server.py"]
    transport: str  # "stdio" or "sse"


@dataclass
class MCPError(Exception):
    """MCP エラー."""

    error_type: str  # "connection", "timeout", "protocol"
    message: str


class MCPClient:
    """MCP クライアント."""

    def __init__(self, config: MCPConfig) -> None:
        """MCP クライアントを初期化する.

        Args:
            config: MCP 設定
        """
        self.config = config
        self._connected = False
        self._session: Optional[ClientSession] = None
        self._read = None
        self._write = None

        logger.info(f"MCP クライアントを初期化しました: command={config.server_command}")

    async def connect(self) -> bool:
        """MCP サーバーに接続する.

        Returns:
            接続成功時 True、失敗時 False
        """
        try:
            logger.info("MCP サーバーに接続中...")

            # StdioServerParameters を作成
            server_params = StdioServerParameters(
                command=self.config.server_command,
                args=self.config.server_args
            )

            # stdio_client で接続
            client_context = stdio_client(server_params)
            self._read, self._write = await client_context.__aenter__()

            # ClientSession を作成
            session_context = ClientSession(self._read, self._write)
            self._session = await session_context.__aenter__()

            # 初期化
            await self._session.initialize()

            self._connected = True
            logger.info("MCP サーバーに接続しました")

            return True

        except Exception as e:
            logger.error(f"MCP サーバーへの接続に失敗しました: {e}")
            self._connected = False
            self._session = None
            return False

    async def get_context(self) -> Optional[str]:
        """コンテキスト情報を取得する.

        Returns:
            コンテキスト文字列、取得失敗時 None

        Raises:
            MCPError: プロトコルエラー
        """
        if not self._connected or self._session is None:
            logger.warning("MCP サーバーに接続されていません")
            return None

        try:
            logger.debug("MCP コンテキストを取得中...")

            # リソース一覧を取得
            resources_result = await self._session.list_resources()

            # コンテキスト文字列を構築
            context_parts = []
            for resource in resources_result.resources:
                context_parts.append(f"Resource: {resource.name} ({resource.uri})")

            context = "\n".join(context_parts) if context_parts else "No resources available"

            logger.debug(f"MCP コンテキストを取得しました: {len(context_parts)} resources")

            return context

        except Exception as e:
            logger.error(f"MCP コンテキスト取得エラー: {e}")
            raise MCPError(
                error_type="protocol",
                message=f"コンテキスト取得に失敗しました: {str(e)}"
            )

    async def disconnect(self) -> None:
        """MCP サーバーから切断する."""
        if self._connected and self._session:
            logger.info("MCP サーバーから切断中...")

            try:
                # セッションを終了
                await self._session.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"セッション終了時のエラー: {e}")

            self._session = None
            self._read = None
            self._write = None
            self._connected = False

            logger.info("MCP サーバーから切断しました")

    def is_connected(self) -> bool:
        """接続状態を確認する.

        Returns:
            接続中の場合 True、未接続の場合 False
        """
        return self._connected