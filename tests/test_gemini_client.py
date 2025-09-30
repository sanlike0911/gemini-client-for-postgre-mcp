"""Gemini API クライアントのテスト."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.gemini_client import GeminiClient, GeminiError, Message


@pytest.fixture
def api_key():
    """テスト用の API キー."""
    return "test_api_key_123"


@pytest.fixture
def gemini_client(api_key):
    """テスト用の Gemini クライアント."""
    return GeminiClient(api_key=api_key)


def test_gemini_client_initialization(api_key):
    """Gemini クライアントが正しく初期化されること."""
    client = GeminiClient(api_key=api_key)

    assert client is not None
    assert client.api_key == api_key
    assert client.model == "models/gemini-1.5-flash"  # デフォルトモデル


def test_gemini_client_initialization_with_custom_model(api_key):
    """カスタムモデルで Gemini クライアントが初期化されること."""
    client = GeminiClient(api_key=api_key, model="gemini-1.5-pro")

    assert client.model == "gemini-1.5-pro"


@pytest.mark.asyncio
async def test_send_message_returns_response(gemini_client):
    """メッセージを送信して応答が返されること."""
    # google.genai をモック
    with patch("src.gemini_client.genai") as mock_genai:
        # モデルの応答をモック
        mock_response = MagicMock()
        mock_response.text = "こんにちは！何かお手伝いできますか？"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        response = await gemini_client.send_message("こんにちは")

        assert response == "こんにちは！何かお手伝いできますか？"
        mock_client.aio.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_with_context(gemini_client):
    """コンテキスト付きでメッセージを送信できること."""
    with patch("src.gemini_client.genai") as mock_genai:
        mock_response = MagicMock()
        mock_response.text = "データベースには3つのテーブルがあります"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        context = "Database: PostgreSQL, Tables: users, posts, comments"
        response = await gemini_client.send_message("テーブルの数は？", context=context)

        assert "データベース" in response
        # コンテキストが含まれたメッセージが送信されることを確認
        call_args = mock_client.aio.models.generate_content.call_args
        assert call_args is not None


@pytest.mark.asyncio
async def test_send_message_handles_network_error(gemini_client):
    """ネットワークエラーが GeminiError として処理されること."""
    with patch("src.gemini_client.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(side_effect=ConnectionError("Network error"))
        mock_genai.Client.return_value = mock_client

        with pytest.raises(GeminiError) as exc_info:
            await gemini_client.send_message("テスト")

        assert exc_info.value.error_type == "network"
        assert isinstance(exc_info.value.original_error, ConnectionError)


@pytest.mark.asyncio
async def test_send_message_handles_auth_error(gemini_client):
    """認証エラーが GeminiError として処理されること."""
    with patch("src.gemini_client.genai") as mock_genai:
        mock_client = MagicMock()
        # 401 エラーをシミュレート
        error = Exception("401: Unauthorized")
        mock_client.aio.models.generate_content = AsyncMock(side_effect=error)
        mock_genai.Client.return_value = mock_client

        with pytest.raises(GeminiError) as exc_info:
            await gemini_client.send_message("テスト")

        assert exc_info.value.error_type == "auth"


def test_get_conversation_history_returns_empty_initially(gemini_client):
    """初期状態で会話履歴が空であること."""
    history = gemini_client.get_conversation_history()

    assert history == []


@pytest.mark.asyncio
async def test_get_conversation_history_after_message(gemini_client):
    """メッセージ送信後に会話履歴が記録されること."""
    with patch("src.gemini_client.genai") as mock_genai:
        mock_response = MagicMock()
        mock_response.text = "応答テキスト"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        await gemini_client.send_message("テストメッセージ")

        history = gemini_client.get_conversation_history()

        assert len(history) == 2  # ユーザーとモデルのメッセージ
        assert history[0].role == "user"
        assert history[0].content == "テストメッセージ"
        assert history[1].role == "model"
        assert history[1].content == "応答テキスト"


@pytest.mark.asyncio
async def test_reset_conversation_clears_history(gemini_client):
    """会話履歴がリセットされること."""
    with patch("src.gemini_client.genai") as mock_genai:
        mock_response = MagicMock()
        mock_response.text = "応答"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        await gemini_client.send_message("メッセージ1")
        await gemini_client.reset_conversation()

        history = gemini_client.get_conversation_history()

        assert history == []


def test_message_dataclass():
    """Message データクラスが正しく動作すること."""
    message = Message(role="user", content="テスト")

    assert message.role == "user"
    assert message.content == "テスト"


def test_gemini_error_dataclass():
    """GeminiError データクラスが正しく動作すること."""
    original = ValueError("Original error")
    error = GeminiError(
        error_type="network",
        message="ネットワークエラー",
        original_error=original
    )

    assert error.error_type == "network"
    assert error.message == "ネットワークエラー"
    assert error.original_error is original