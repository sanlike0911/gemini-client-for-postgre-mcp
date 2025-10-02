"""Gemini API クライアントモジュール."""
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import google.genai as genai

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """会話メチE��ージ."""

    role: str  # "user" or "model"
    content: str


@dataclass
class GeminiError(Exception):
    """Gemini API エラー."""

    error_type: str  # "network", "rate_limit", "auth", "unknown"
    message: str
    original_error: Optional[Exception]


class GeminiClient:
    """Gemini API クライアンチE"""

    def __init__(
        self,
        api_key: str,
        model: str = "models/gemini-1.5-flash",
        system_instruction: Optional[str] = None,
    ) -> None:
        """Gemini クライアントを初期化すめE"""
        self.api_key = api_key
        self.model = model
        self.system_instruction = system_instruction
        self._conversation_history: List[Message] = []
        self._client = None  # 遁E��初期匁E
        logger.info(f"Gemini クライアントを初期化しました: model={model}")

    def _ensure_client(self):
        """クライアントが初期化されてぁE��ことを確認すめE"""
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)

    async def send_message(
        self,
        message: str,
        context: Optional[str] = None,
        *,
        response_mime_type: Optional[str] = None,
        system_instruction_override: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        persist_history: bool = True,
    ) -> str:
        """メチE��ージを送信して応答を取得すめE"""
        try:
            self._ensure_client()

            full_message = message
            if context:
                full_message = f"[Context]\n{context}\n\n[User Message]\n{message}"

            logger.debug(f"メチE��ージを送信: {message[:50]}...")

            request_kwargs: Dict[str, Any] = {
                "model": self.model,
                "contents": full_message,
            }

            config: Dict[str, Any] = {}
            instruction = system_instruction_override or self.system_instruction
            if instruction:
                config["system_instruction"] = instruction

            generation_kwargs: Dict[str, Any] = {}
            if generation_config:
                generation_kwargs.update(generation_config)
            if response_mime_type:
                generation_kwargs["response_mime_type"] = response_mime_type

            if config:
                request_kwargs["config"] = config
            if generation_kwargs:
                request_kwargs["generation_config"] = generation_kwargs

            response = await self._client.aio.models.generate_content(**request_kwargs)
            response_text = response.text

            if persist_history:
                self._conversation_history.append(Message(role="user", content=message))
                self._conversation_history.append(Message(role="model", content=response_text))

            logger.debug(f"応答を受信: {response_text[:50]}...")

            return response_text

        except ConnectionError as e:
            logger.error(f"ネットワークエラー: {e}")
            raise GeminiError(
                error_type="network",
                message="ネットワーク接続に失敗しました",
                original_error=e,
            )

        except Exception as e:
            error_str = str(e)

            if "429" in error_str or "Too Many Requests" in error_str:
                logger.error(f"レート制限エラー: {e}")
                raise GeminiError(
                    error_type="rate_limit",
                    message="API のレート制限に達しました",
                    original_error=e,
                )

            if "401" in error_str or "403" in error_str or "Unauthorized" in error_str:
                logger.error(f"認証エラー: {e}")
                raise GeminiError(
                    error_type="auth",
                    message="API キーの認証に失敗しました",
                    original_error=e,
                )

            logger.error(f"未知のエラー: {e}")
            raise GeminiError(
                error_type="unknown",
                message="予期しなぁE��ラーが発生しました",
                original_error=e,
            )

    async def send_json(self, message: str, context: Optional[str] = None) -> Dict[str, Any]:
        """JSON 応答を要求し、辞書として返す."""
        response_text = await self.send_message(
            message,
            context=context,
            response_mime_type="application/json",
            persist_history=False,
        )

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as exc:
            logger.error(f"JSON 応答の解析に失敗しました: {exc}")
            raise GeminiError(
                error_type="unknown",
                message="Gemini からの JSON 応答を解釈できませんでした",
                original_error=exc,
            )

    def get_conversation_history(self) -> List[Message]:
        """会話履歴を取得すめE"""
        return self._conversation_history.copy()

    async def reset_conversation(self) -> None:
        """会話履歴をリセチE��する."""
        self._conversation_history.clear()
        logger.info("会話履歴をリセチE��しました")
