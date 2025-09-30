"""ログ設定のテスト."""
import logging
import os
import tempfile
from pathlib import Path

import pytest

from src.logging_config import setup_logging


@pytest.fixture(autouse=True)
def reset_logging():
    """各テスト前後でロガーをリセットする."""
    # テスト前: ハンドラーをクリア
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.WARNING)

    yield

    # テスト後: ハンドラーをクリア
    logger.handlers.clear()


def test_setup_logging_with_default_level(tmp_path):
    """デフォルトのログレベルでログ設定が初期化されること."""
    log_file = tmp_path / "test.log"
    setup_logging(log_file=str(log_file))

    logger = logging.getLogger(__name__)
    assert logger.level == logging.NOTSET  # ルートロガーのレベルを継承
    assert logging.root.level == logging.INFO


def test_setup_logging_with_custom_level(tmp_path):
    """カスタムログレベルでログ設定が初期化されること."""
    log_file = tmp_path / "test.log"
    setup_logging(log_level="DEBUG", log_file=str(log_file))

    assert logging.root.level == logging.DEBUG


def test_setup_logging_with_invalid_level(tmp_path):
    """無効なログレベルの場合、INFO レベルにフォールバックすること."""
    log_file = tmp_path / "test.log"
    setup_logging(log_level="INVALID", log_file=str(log_file))

    assert logging.root.level == logging.INFO


def test_setup_logging_creates_log_file(tmp_path):
    """ログファイルが作成されること."""
    log_file = tmp_path / "test.log"
    setup_logging(log_file=str(log_file))

    logger = logging.getLogger(__name__)
    logger.info("Test message")

    # ハンドラーをフラッシュ
    for handler in logger.handlers:
        handler.flush()
    for handler in logging.root.handlers:
        handler.flush()

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Test message" in content


def test_setup_logging_from_env_variable(tmp_path, monkeypatch):
    """環境変数 LOG_LEVEL からログレベルを読み込むこと."""
    log_file = tmp_path / "test.log"
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    setup_logging(log_file=str(log_file))

    assert logging.root.level == logging.WARNING