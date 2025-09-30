"""アプリケーション層モジュール."""
import logging
from typing import Optional

from src.config import AppConfig
from src.error_handler import ErrorHandler
from src.gemini_client import GeminiClient
from src.mcp_client import MCPClient, MCPConfig

logger = logging.getLogger(__name__)


class Application:
    """アプリケーションクラス."""

    def __init__(self, config: AppConfig) -> None:
        """アプリケーションを初期化する.

        Args:
            config: アプリケーション設定
        """
        self.config = config
        self._gemini_client: Optional[GeminiClient] = None
        self._mcp_client: Optional[MCPClient] = None

        logger.info("アプリケーションを初期化しました")

    async def start(self) -> None:
        """アプリケーションを起動する."""
        logger.info("アプリケーションを起動中...")

        # Gemini クライアントを初期化
        self._gemini_client = GeminiClient(
            api_key=self.config.gemini_api_key,
            model=self.config.gemini_model
        )
        logger.info("Gemini クライアントを初期化しました")

        # MCP クライアントを初期化（オプショナル）
        if self.config.has_mcp_config():
            try:
                mcp_config = MCPConfig(
                    server_command=self.config.mcp_server_command,
                    server_args=self.config.mcp_server_args,
                    transport=self.config.mcp_transport
                )
                self._mcp_client = MCPClient(config=mcp_config)

                # MCP サーバーに接続
                connected = await self._mcp_client.connect()
                if connected:
                    logger.info("MCP サーバーに接続しました")
                else:
                    logger.warning("MCP サーバーへの接続に失敗しました（継続）")
                    self._mcp_client = None

            except Exception as e:
                logger.warning(f"MCP クライアント初期化エラー（継続）: {e}")
                self._mcp_client = None
        else:
            logger.info("MCP 設定がないため、MCP クライアントは初期化されません")

        logger.info("アプリケーションの起動が完了しました")

    async def handle_user_message(self, message: str) -> str:
        """ユーザーメッセージを処理して応答を返す.

        Args:
            message: ユーザーメッセージ

        Returns:
            Gemini API からの応答
        """
        try:
            # MCP コンテキストを取得（接続されている場合）
            context = None
            if self._mcp_client and self._mcp_client.is_connected():
                try:
                    context = await self._mcp_client.get_context()
                    logger.debug("MCP コンテキストを取得しました")
                except Exception as e:
                    logger.warning(f"MCP コンテキスト取得エラー（継続）: {e}")

            # Gemini API にメッセージを送信
            response = await self._gemini_client.send_message(message, context=context)

            return response

        except Exception as e:
            # エラーハンドリング
            error_context = ErrorHandler.handle_error(e, context="メッセージ処理中")
            return error_context.user_message

    async def shutdown(self) -> None:
        """アプリケーションを終了する."""
        logger.info("アプリケーションを終了中...")

        # MCP クライアントを切断
        if self._mcp_client:
            try:
                await self._mcp_client.disconnect()
                logger.info("MCP クライアントを切断しました")
            except Exception as e:
                logger.warning(f"MCP クライアント切断エラー: {e}")

        logger.info("アプリケーションを終了しました")

    def is_mcp_connected(self) -> bool:
        """MCP 接続状態を確認する.

        Returns:
            MCP クライアントが接続されている場合 True
        """
        return self._mcp_client is not None and self._mcp_client.is_connected()