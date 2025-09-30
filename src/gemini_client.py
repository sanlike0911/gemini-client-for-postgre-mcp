"""Gemini API クライアントモジュール."""
import logging
from dataclasses import dataclass
from typing import List, Optional

import google.genai as genai

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """会話メッセージ."""

    role: str  # "user" or "model"
    content: str


@dataclass
class GeminiError(Exception):
    """Gemini API エラー."""

    error_type: str  # "network", "rate_limit", "auth", "unknown"
    message: str
    original_error: Optional[Exception]


class GeminiClient:
    """Gemini API クライアント."""

    def __init__(self, api_key: str, model: str = "models/gemini-1.5-flash") -> None:
        """Gemini クライアントを初期化する.

        Args:
            api_key: Gemini API キー
            model: 使用するモデル名（デフォルト: gemini-1.5-flash）
        """
        self.api_key = api_key
        self.model = model
        self._conversation_history: List[Message] = []
        self._client = None  # 遅延初期化

        logger.info(f"Gemini クライアントを初期化しました: model={model}")

    def _ensure_client(self):
        """クライアントが初期化されていることを確認する."""
        if self._client is None:
            # クライアントを作成（API キーを使用）
            self._client = genai.Client(api_key=self.api_key)

    async def send_message(
        self, message: str, context: Optional[str] = None
    ) -> str:
        """メッセージを送信して応答を取得する.

        Args:
            message: ユーザーメッセージ
            context: MCP から取得したコンテキスト情報（オプション）

        Returns:
            Gemini API からの応答テキスト

        Raises:
            GeminiError: API 通信エラー
        """
        try:
            # クライアントを確保
            self._ensure_client()

            # コンテキスト付きメッセージを構築
            full_message = message
            if context:
                full_message = f"[Context]\n{context}\n\n[User Message]\n{message}"

            logger.debug(f"メッセージを送信: {message[:50]}...")

            # API 呼び出し
            response = await self._client.aio.models.generate_content(
                model=self.model, contents=full_message
            )

            # 応答テキストを取得
            response_text = response.text

            # 会話履歴に追加
            self._conversation_history.append(Message(role="user", content=message))
            self._conversation_history.append(
                Message(role="model", content=response_text)
            )

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

            # レート制限エラー
            if "429" in error_str or "Too Many Requests" in error_str:
                logger.error(f"レート制限エラー: {e}")
                raise GeminiError(
                    error_type="rate_limit",
                    message="API のレート制限に達しました",
                    original_error=e,
                )

            # 認証エラー
            if "401" in error_str or "403" in error_str or "Unauthorized" in error_str:
                logger.error(f"認証エラー: {e}")
                raise GeminiError(
                    error_type="auth",
                    message="API キーの認証に失敗しました",
                    original_error=e,
                )

            # その他のエラー
            logger.error(f"未知のエラー: {e}")
            raise GeminiError(
                error_type="unknown",
                message="予期しないエラーが発生しました",
                original_error=e,
            )

    def get_conversation_history(self) -> List[Message]:
        """会話履歴を取得する.

        Returns:
            会話履歴のリスト
        """
        return self._conversation_history.copy()

    async def reset_conversation(self) -> None:
        """会話履歴をリセットする."""
        self._conversation_history.clear()
        logger.info("会話履歴をリセットしました")