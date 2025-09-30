"""ログ設定モジュール."""
import logging
import os
from typing import Optional


def setup_logging(log_level: Optional[str] = None, log_file: str = "app.log") -> None:
    """ログ設定を初期化する.

    Args:
        log_level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_file: ログファイル名
    """
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")

    # ログレベルの検証
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    # ログフォーマット
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # ルートロガーを取得
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # 既存のハンドラーをクリア（テスト環境で重要）
    root_logger.handlers.clear()

    # フォーマッターを作成
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # ファイルハンドラーを追加
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # ストリームハンドラーを追加
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # 外部ライブラリのログレベルを制御
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.WARNING)
    logging.getLogger("textual").setLevel(logging.WARNING)