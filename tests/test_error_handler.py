"""エラーハンドリングのテスト."""
import logging
from typing import Optional

import pytest

from src.error_handler import ErrorCategory, ErrorContext, ErrorHandler


def test_handle_network_error():
    """ネットワークエラーが正しく分類されること."""
    error = ConnectionError("Connection failed")

    context = ErrorHandler.handle_error(error)

    assert context.category == ErrorCategory.NETWORK
    assert "ネットワーク" in context.user_message or "接続" in context.user_message
    assert context.recoverable is True


def test_handle_rate_limit_error():
    """レート制限エラーが正しく分類されること."""
    # HTTP 429 エラーをシミュレート
    error = Exception("429: Too Many Requests")

    context = ErrorHandler.handle_error(error)

    assert context.category == ErrorCategory.RATE_LIMIT
    assert "レート制限" in context.user_message or "制限" in context.user_message
    assert context.recoverable is True


def test_handle_auth_error():
    """認証エラーが正しく分類されること."""
    # HTTP 401 エラーをシミュレート
    error = Exception("401: Unauthorized")

    context = ErrorHandler.handle_error(error)

    assert context.category == ErrorCategory.AUTH
    assert "認証" in context.user_message or "API キー" in context.user_message
    assert context.recoverable is False


def test_handle_mcp_connection_error():
    """MCP 接続エラーが正しく分類されること."""
    error = Exception("MCP connection failed")

    context = ErrorHandler.handle_error(error, error_source="mcp")

    assert context.category == ErrorCategory.MCP_CONNECTION
    assert "MCP" in context.user_message
    assert context.recoverable is True


def test_handle_unknown_error():
    """未知のエラーが正しく分類されること."""
    error = ValueError("Some unknown error")

    context = ErrorHandler.handle_error(error)

    assert context.category == ErrorCategory.UNKNOWN
    assert "エラー" in context.user_message
    assert context.recoverable is False


def test_log_error_records_to_logger(caplog):
    """エラーがロガーに記録されること."""
    error = ConnectionError("Test error")

    with caplog.at_level(logging.ERROR):
        ErrorHandler.log_error(error)

    assert len(caplog.records) > 0
    assert "Test error" in caplog.text


def test_log_error_with_context(caplog):
    """コンテキスト付きでエラーがロガーに記録されること."""
    error = ValueError("Test error")
    context_info = "While processing user message"

    with caplog.at_level(logging.ERROR):
        ErrorHandler.log_error(error, context=context_info)

    assert "While processing user message" in caplog.text


def test_get_user_message_returns_friendly_message():
    """ユーザーフレンドリーなメッセージが返されること."""
    error = ConnectionError("Connection timeout")

    message = ErrorHandler.get_user_message(error)

    assert isinstance(message, str)
    assert len(message) > 0
    assert "Connection timeout" not in message  # 技術的な詳細は含まない


def test_is_recoverable_for_network_error():
    """ネットワークエラーが回復可能と判定されること."""
    error = ConnectionError("Network error")

    assert ErrorHandler.is_recoverable(error) is True


def test_is_recoverable_for_auth_error():
    """認証エラーが回復不可能と判定されること."""
    error = Exception("401: Unauthorized")

    assert ErrorHandler.is_recoverable(error) is False


def test_error_context_has_required_fields():
    """ErrorContext が必要なフィールドを持つこと."""
    context = ErrorContext(
        category=ErrorCategory.NETWORK,
        user_message="ネットワークエラーが発生しました",
        log_message="ConnectionError: Connection failed",
        recoverable=True
    )

    assert context.category == ErrorCategory.NETWORK
    assert context.user_message == "ネットワークエラーが発生しました"
    assert context.log_message == "ConnectionError: Connection failed"
    assert context.recoverable is True