"""MCP クライアントモジュール."""
import json
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import mcp.types as mcp_types
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

DEFAULT_SSE_TIMEOUT = 5.0
DEFAULT_SSE_READ_TIMEOUT = 60.0 * 5


@dataclass
class MCPConfig:
    """MCP 設定."""

    transport: str  # "stdio" or "sse"
    server_command: Optional[str] = None
    server_args: Optional[List[str]] = None
    sse_url: Optional[str] = None
    sse_headers: Optional[Dict[str, str]] = None
    sse_timeout: Optional[float] = None
    sse_read_timeout: Optional[float] = None
    server_env: Optional[Dict[str, str]] = None


@dataclass
class MCPError(Exception):
    """MCP エラー."""

    error_type: str  # "connection", "timeout", "protocol", "tool"
    message: str


class MCPClient:
    """MCP クライアント."""

    def __init__(self, config: MCPConfig) -> None:
        """MCP クライアントを初期化する."""
        self.config = config
        self._connected = False
        self._session: Optional[ClientSession] = None
        self._read = None
        self._write = None
        self._stack: Optional[AsyncExitStack] = None
        self._tool_cache: Optional[List[mcp_types.Tool]] = None

        logger.info(f"MCP クライアントを初期化しました: transport={config.transport}")

    async def connect(self) -> bool:
        """MCP サーバーに接続する."""
        stack = AsyncExitStack()

        try:
            logger.info("MCP サーバーに接続中...")

            if self.config.transport == "stdio":
                if not self.config.server_command:
                    logger.error("stdio トランスポートには MCP サーバーコマンドが必要です")
                    await stack.aclose()
                    return False

                server_params = StdioServerParameters(
                    command=self.config.server_command,
                    args=self.config.server_args or [],
                    env=self.config.server_env or None,
                )
                client_context = stdio_client(server_params)
            elif self.config.transport == "sse":
                if not self.config.sse_url:
                    logger.error("sse トランスポートには MCP_SSE_URL が必要です")
                    await stack.aclose()
                    return False

                client_context = sse_client(
                    url=self.config.sse_url,
                    headers=self.config.sse_headers,
                    timeout=self.config.sse_timeout or DEFAULT_SSE_TIMEOUT,
                    sse_read_timeout=self.config.sse_read_timeout or DEFAULT_SSE_READ_TIMEOUT,
                )
            else:
                logger.error(f"未対応のトランスポートです: {self.config.transport}")
                await stack.aclose()
                return False

            self._read, self._write = await stack.enter_async_context(client_context)

            session_context = ClientSession(self._read, self._write)
            self._session = await stack.enter_async_context(session_context)

            await self._session.initialize()

            self._stack = stack
            self._connected = True
            self._tool_cache = None
            logger.info("MCP サーバーに接続しました")

            return True

        except Exception as e:
            logger.error(f"MCP サーバーへの接続に失敗しました: {e}")
            self._connected = False
            self._session = None
            self._read = None
            self._write = None
            await stack.aclose()
            return False

    async def list_tools(self, force_refresh: bool = False) -> List[mcp_types.Tool]:
        """利用可能な MCP ツール一覧を取得する."""
        if not self._connected or self._session is None:
            logger.warning("MCP サーバーに接続されていないためツール一覧を取得できません")
            return []

        if self._tool_cache is None or force_refresh:
            logger.debug("MCP ツール一覧を取得中...")
            try:
                tools_result = await self._session.list_tools()
            except Exception as exc:
                logger.error(f"ツール一覧の取得に失敗しました: {exc}")
                raise MCPError(
                    error_type="protocol",
                    message=f"ツール一覧の取得に失敗しました: {exc}",
                ) from exc

            self._tool_cache = list(tools_result.tools)
            logger.debug(f"MCP ツールを {len(self._tool_cache)} 件取得しました")

        return list(self._tool_cache)

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        read_timeout_seconds: Optional[float] = None,
    ) -> mcp_types.CallToolResult:
        """指定された MCP ツールを実行する."""
        if not self._connected or self._session is None:
            raise MCPError(
                error_type="connection",
                message="MCP サーバーに接続されていません",
            )

        try:
            logger.info(f"ツールを実行します: {name}")
            result = await self._session.call_tool(
                name=name,
                arguments=arguments,
                read_timeout_seconds=None if read_timeout_seconds is None else read_timeout_seconds,
            )
            return result
        except Exception as exc:
            logger.error(f"ツール実行に失敗しました: {exc}")
            raise MCPError(
                error_type="tool",
                message=f"ツール {name} の実行に失敗しました: {exc}",
            ) from exc

    @staticmethod
    def render_tool_result(result: mcp_types.CallToolResult) -> str:
        """ツール実行結果をテキストに整形する."""
        parts: List[str] = []

        if result.structuredContent:
            try:
                parts.append(json.dumps(result.structuredContent, ensure_ascii=False, indent=2))
            except (TypeError, ValueError):
                parts.append(str(result.structuredContent))

        for block in result.content or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
                continue

            data = getattr(block, "data", None)
            if isinstance(data, (bytes, bytearray)):
                parts.append("<binary data omitted>")
                continue

            if data:
                parts.append(str(data))
                continue

            resource = getattr(block, "resource", None)
            if resource is not None:
                parts.append(str(resource))
                continue

            parts.append(str(block))

        return "\n".join(p for p in parts if p)

    async def get_context(self) -> Optional[str]:
        """コンテキスト情報を取得する."""
        if not self._connected or self._session is None:
            logger.warning("MCP サーバーに接続されていません")
            return None

        try:
            logger.debug("MCP コンテキストを取得中...")

            resources_result = await self._session.list_resources()

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
                message=f"コンテキスト取得に失敗しました: {str(e)}",
            ) from e

    async def disconnect(self) -> None:
        """MCP サーバーから切断する."""
        if not self._connected:
            return

        logger.info("MCP サーバーから切断中...")

        try:
            if self._stack is not None:
                await self._stack.aclose()
        except Exception as e:
            logger.warning(f"セッション終了時のエラー: {e}")
        finally:
            self._stack = None
            self._session = None
            self._read = None
            self._write = None
            self._connected = False
            self._tool_cache = None

            logger.info("MCP サーバーから切断しました")

    def is_connected(self) -> bool:
        """接続状態を確認する."""
        return self._connected

