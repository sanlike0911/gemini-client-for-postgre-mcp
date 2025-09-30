"""エラーハンドリングモジュール."""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """エラーカテゴリ."""

    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    MCP_CONNECTION = "mcp_connection"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """エラーコンテキスト."""

    category: ErrorCategory
    user_message: str
    log_message: str
    recoverable: bool


class ErrorHandler:
    """エラーハンドリングクラス."""

    @staticmethod
    def handle_error(
        error: Exception, context: Optional[str] = None, error_source: Optional[str] = None
    ) -> ErrorContext:
        """エラーを処理してコンテキストを返す.

        Args:
            error: 発生した例外
            context: エラー発生時のコンテキスト情報
            error_source: エラー発生元（"mcp" など）

        Returns:
            エラーコンテキスト
        """
        # エラーを分類
        category = ErrorHandler._classify_error(error, error_source)

        # ユーザーメッセージを生成
        user_message = ErrorHandler.get_user_message(error)

        # ログメッセージを生成
        log_message = f"{type(error).__name__}: {str(error)}"
        if context:
            log_message = f"{context} - {log_message}"

        # 回復可能性を判定
        recoverable = ErrorHandler.is_recoverable(error)

        # ログに記録
        ErrorHandler.log_error(error, context=context)

        return ErrorContext(
            category=category,
            user_message=user_message,
            log_message=log_message,
            recoverable=recoverable,
        )

    @staticmethod
    def _classify_error(error: Exception, error_source: Optional[str] = None) -> ErrorCategory:
        """エラーを分類する.

        Args:
            error: 発生した例外
            error_source: エラー発生元

        Returns:
            エラーカテゴリ
        """
        error_str = str(error)

        # MCP エラー
        if error_source == "mcp" or "MCP" in error_str:
            return ErrorCategory.MCP_CONNECTION

        # ネットワークエラー
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorCategory.NETWORK

        # レート制限エラー
        if "429" in error_str or "Too Many Requests" in error_str:
            return ErrorCategory.RATE_LIMIT

        # 認証エラー
        if "401" in error_str or "403" in error_str or "Unauthorized" in error_str or "Forbidden" in error_str:
            return ErrorCategory.AUTH

        # 未知のエラー
        return ErrorCategory.UNKNOWN

    @staticmethod
    def log_error(error: Exception, context: Optional[str] = None) -> None:
        """エラーをログに記録する.

        Args:
            error: 発生した例外
            context: エラー発生時のコンテキスト情報
        """
        if context:
            logger.error(f"{context} - {type(error).__name__}: {str(error)}", exc_info=True)
        else:
            logger.error(f"{type(error).__name__}: {str(error)}", exc_info=True)

    @staticmethod
    def get_user_message(error: Exception) -> str:
        """ユーザーに表示するエラーメッセージを取得する.

        Args:
            error: 発生した例外

        Returns:
            ユーザーフレンドリーなエラーメッセージ
        """
        error_str = str(error)

        # ネットワークエラー
        if isinstance(error, (ConnectionError, TimeoutError)):
            return "ネットワーク接続に問題が発生しました。インターネット接続を確認してください。"

        # レート制限エラー
        if "429" in error_str or "Too Many Requests" in error_str:
            return "API のレート制限に達しました。しばらく待ってから再試行してください。"

        # 認証エラー
        if "401" in error_str or "403" in error_str or "Unauthorized" in error_str or "Forbidden" in error_str:
            return "API キーの認証に失敗しました。API キーが正しく設定されているか確認してください。"

        # MCP エラー
        if "MCP" in error_str:
            return "MCP サーバーへの接続に失敗しました。MCP サーバーが起動しているか確認してください。"

        # 未知のエラー
        return "予期しないエラーが発生しました。ログを確認してください。"

    @staticmethod
    def is_recoverable(error: Exception) -> bool:
        """エラーが回復可能かどうかを判定する.

        Args:
            error: 発生した例外

        Returns:
            回復可能な場合 True、不可能な場合 False
        """
        error_str = str(error)

        # 認証エラーは回復不可能
        if "401" in error_str or "403" in error_str or "Unauthorized" in error_str or "Forbidden" in error_str:
            return False

        # ネットワークエラー、レート制限エラー、MCP エラーは回復可能
        if isinstance(error, (ConnectionError, TimeoutError)):
            return True

        if "429" in error_str or "Too Many Requests" in error_str:
            return True

        if "MCP" in error_str:
            return True

        # その他のエラーは回復不可能とみなす
        return False