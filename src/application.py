"""アプリケーション層モジュール."""
import json
import logging
from typing import Dict, List, Optional

import mcp.types as mcp_types

from src.config import AppConfig, MCPServerSettings
from src.error_handler import ErrorHandler
from src.gemini_client import GeminiClient, GeminiError
from src.mcp_client import MCPClient, MCPConfig, MCPError

logger = logging.getLogger(__name__)


class Application:
    """アプリケーションクラス."""

    def __init__(self, config: AppConfig) -> None:
        """アプリケーションを初期化する."""
        self.config = config
        self._gemini_client: Optional[GeminiClient] = None
        self._mcp_client: Optional[MCPClient] = None
        self._available_tools: List[mcp_types.Tool] = []

        logger.info("アプリケーションを初期化しました")

    async def start(self) -> None:
        """アプリケーションを起動する."""
        logger.info("アプリケーションを起動中...")

        self._gemini_client = GeminiClient(
            api_key=self.config.gemini_api_key,
            model=self.config.gemini_model,
            system_instruction=self.config.gemini_system_instruction,
        )
        logger.info("Gemini クライアントを初期化しました")

        server_settings = self.config.mcp_server
        if server_settings:
            try:
                mcp_config = self._build_mcp_config(server_settings)
                self._mcp_client = MCPClient(config=mcp_config)

                connected = await self._mcp_client.connect()
                if connected:
                    logger.info("MCP サーバーに接続しました")
                    try:
                        self._available_tools = await self._mcp_client.list_tools()
                        logger.info(f"MCP ツールを {len(self._available_tools)} 件取得しました")
                    except MCPError as exc:
                        logger.warning(f"MCP ツール一覧の取得に失敗しました（継続）: {exc.message}")
                        self._available_tools = []
                else:
                    logger.warning("MCP サーバーへの接続に失敗しました（継続）")
                    self._mcp_client = None
            except Exception as exc:
                logger.warning(f"MCP クライアント初期化エラー（継続）: {exc}")
                self._mcp_client = None
        else:
            logger.info("MCP 設定がないため、MCP クライアントは初期化されません")

        logger.info("アプリケーションの起動が完了しました")

    def _build_mcp_config(self, settings: MCPServerSettings) -> MCPConfig:
        """MCPClient 用の設定を構築する."""

        if settings.transport == "stdio":
            return MCPConfig(
                transport="stdio",
                server_command=settings.command,
                server_args=settings.args,
                server_env=settings.env,
            )

        return MCPConfig(
            transport="sse",
            sse_url=settings.url,
            sse_headers=settings.headers,
            sse_timeout=settings.timeout,
            sse_read_timeout=settings.read_timeout,
        )

    def _format_tool_summary(self) -> str:
        if not self._available_tools:
            return "（利用可能な MCP ツールはありません）"

        lines: List[str] = []
        for tool in self._available_tools:
            description = tool.description or "説明が提供されていません"
            lines.append(f"- {tool.name}: {description}")
        return "\n".join(lines)

    def _build_tool_decision_prompt(self, user_message: str) -> str:
        tool_summary = self._format_tool_summary()
        return (
            "あなたは Model Context Protocol に対応したアシスタントです。\n"
            "以下の MCP ツールを最大 1 回まで利用してから、ユーザーの質問に回答できます。\n"
            "必要なければツールを使わずに回答してください。\n\n"
            f"利用可能なツール一覧:\n{tool_summary}\n\n"
            "必ず次の JSON 形式で応答してください。\n"
            "- ツールが不要な場合: {\"action\": \"respond\", \"message\": \"<回答>\"}\n"
            "- ツールを使う場合: {\"action\": \"call_tool\", \"tool\": \"<ツール名>\", \"arguments\": { ... }}\n"
            "SQL を実行する際は `execute_sql` を選び、arguments に `sql` キーを含めてください。\n"
            "JSON 以外の文字や説明は含めないでください。\n\n"
            f"ユーザーからの依頼:\n{user_message}\n"
        )

    async def _handle_with_tools(self, message: str) -> Optional[str]:
        if not self._gemini_client or not self._mcp_client or not self._mcp_client.is_connected():
            return None
        if not self._available_tools:
            return None

        try:
            plan = await self._gemini_client.send_json(
                self._build_tool_decision_prompt(message)
            )
        except GeminiError as exc:
            logger.warning(f"Gemini から JSON プランを取得できませんでした（継続）: {exc.message}")
            return None

        if not isinstance(plan, dict):
            logger.warning("Gemini からのプランが辞書形式ではありません: %s", plan)
            return None

        action = plan.get("action")
        if action == "respond":
            message_text = plan.get("message")
            if isinstance(message_text, str) and message_text.strip():
                return message_text
            return None

        if action != "call_tool":
            logger.warning("未知のアクションが指定されました: %s", action)
            return None

        tool_name = plan.get("tool")
        if not isinstance(tool_name, str) or not tool_name:
            logger.warning("ツール名が指定されていません: %s", plan)
            return None

        available_tool_names = {tool.name for tool in self._available_tools}
        if tool_name not in available_tool_names:
            logger.warning("指定されたツールが利用可能一覧に存在しません: %s", tool_name)
            return None

        arguments = plan.get("arguments")
        if arguments is not None and not isinstance(arguments, dict):
            logger.warning("ツール引数が辞書形式ではありません: %s", arguments)
            arguments = None

        try:
            tool_result = await self._mcp_client.call_tool(tool_name, arguments)
        except MCPError as exc:
            logger.warning(f"ツール実行に失敗しました（継続）: {exc.message}")
            return None

        if tool_result.isError:
            error_text = self._mcp_client.render_tool_result(tool_result) or "ツール実行でエラーが発生しました"
            logger.warning("ツール実行結果がエラーでした: %s", error_text)
            return f"ツール {tool_name} の実行に失敗しました。詳細: {error_text}"

        tool_output = self._mcp_client.render_tool_result(tool_result)
        arguments_json = json.dumps(arguments or {}, ensure_ascii=False)

        final_prompt = (
            "以下はユーザーからの質問と、MCP ツールの実行結果です。"
            "結果を踏まえてユーザーが理解しやすい最終回答を日本語で作成してください。\n\n"
            f"[ユーザーの質問]\n{message}\n\n"
            f"[使用したツール]\n{tool_name}\n"
            f"[ツール引数]\n{arguments_json}\n\n"
            f"[ツール結果]\n{tool_output}\n"
        )

        try:
            final_answer = await self._gemini_client.send_message(
                final_prompt,
                persist_history=False,
            )
        except GeminiError as exc:
            logger.warning(f"Gemini から最終回答を取得できませんでした（継続）: {exc.message}")
            return tool_output or "ツールの結果を取得しましたが、Gemini の応答に失敗しました。"

        return final_answer

    async def handle_user_message(self, message: str) -> str:
        """ユーザーメッセージを処理して応答を返す."""
        if self._gemini_client is None:
            raise RuntimeError("Gemini クライアントが初期化されていません")

        try:
            if self._mcp_client and self._mcp_client.is_connected():
                try:
                    context = await self._mcp_client.get_context()
                except MCPError as exc:
                    logger.warning(f"MCP コンテキスト取得エラー（継続）: {exc.message}")
                    context = None

                tool_based_answer = await self._handle_with_tools(message)
                if tool_based_answer:
                    return tool_based_answer

                return await self._gemini_client.send_message(message, context=context)

            return await self._gemini_client.send_message(message)

        except (GeminiError, MCPError) as error:
            error_context = ErrorHandler.handle_error(error, context="メッセージ処理中")
            return error_context.user_message

        except Exception as error:
            error_context = ErrorHandler.handle_error(error, context="メッセージ処理中")
            return error_context.user_message

    async def shutdown(self) -> None:
        """アプリケーションを終了する."""
        logger.info("アプリケーションを終了中...")

        if self._mcp_client:
            try:
                await self._mcp_client.disconnect()
                logger.info("MCP クライアントを切断しました")
            except Exception as exc:
                logger.warning(f"MCP クライアント切断エラー: {exc}")

        self._available_tools = []
        logger.info("アプリケーションを終了しました")

    def is_mcp_connected(self) -> bool:
        """MCP 接続状態を確認する."""
        return self._mcp_client is not None and self._mcp_client.is_connected()