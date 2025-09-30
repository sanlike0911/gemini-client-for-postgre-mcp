"""メインエントリーポイント."""
import asyncio
import logging
import sys

from dotenv import load_dotenv

from src.application import Application
from src.config import ConfigurationManager, ConfigValidationError
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)


async def main() -> int:
    """アプリケーションのメインエントリーポイント.

    Returns:
        終了コード（0: 正常終了、1: エラー終了）
    """
    # .env ファイルを読み込み
    load_dotenv()

    # ログ設定を初期化（デフォルトレベル）
    setup_logging(log_level="INFO")

    try:
        # 設定を読み込み
        config = ConfigurationManager.load_config()

        # ログレベルを再設定
        setup_logging(log_level=config.log_level)

        logger.info("Gemini MCP Chat アプリケーションを起動します")

        # アプリケーションを初期化
        app = Application(config=config)

        # アプリケーションを起動
        await app.start()

        # MCP 接続状態を表示
        if app.is_mcp_connected():
            print("✓ MCP サーバーに接続されました")
        else:
            print("✗ MCP サーバーは未接続です")

        print("\nGemini Chat へようこそ！")
        print("メッセージを入力してください（終了: Ctrl+C）\n")

        # チャットループ
        while True:
            try:
                # ユーザー入力を取得
                user_input = input("You: ")

                if not user_input.strip():
                    continue

                # メッセージを処理
                print("Assistant: ", end="", flush=True)
                response = await app.handle_user_message(user_input)
                print(response)
                print()

            except KeyboardInterrupt:
                print("\n\nチャットを終了します...")
                break

        # アプリケーションを終了
        await app.shutdown()

        logger.info("アプリケーションを正常終了しました")
        return 0

    except ConfigValidationError as e:
        print(f"設定エラー: {e.field} - {e.message}", file=sys.stderr)
        logger.error(f"設定エラー: {e.field} - {e.message}")
        return 1

    except Exception as e:
        print(f"予期しないエラー: {e}", file=sys.stderr)
        logger.error(f"予期しないエラー: {e}", exc_info=True)
        return 1


def run():
    """同期エントリーポイント."""
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    run()