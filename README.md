# Gemini MCP Chat Application

Gemini API と MCP (Model Context Protocol) サーバーを統合したシンプルなターミナルチャットアプリケーションです。

## 機能

- ✨ Google Gemini AI との対話
- 🔌 MCP サーバーとの統合（オプショナル）
- 💬 シンプルなコマンドラインインターフェース
- 🔐 環境変数ベースの設定管理
- 📝 包括的なロギング
- 🧪 完全なテストカバレッジ

## 必要要件

- Python 3.10 以上
- Gemini API キー

## インストール

1. リポジトリをクローン:
```bash
git clone <repository-url>
cd gemini-client-for-postgre-mcp
```

2. 仮想環境を作成して有効化:
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

3. 依存関係をインストール:
```bash
pip install -r requirements.txt
```

4. 環境変数を設定:
```bash
# .env.example をコピーして .env を作成
cp .env.example .env

# .env ファイルを編集して Gemini API キーを設定
# GEMINI_API_KEY=your_actual_api_key_here
```

## 設定

`.env` ファイルで以下の設定が可能です:

### 必須設定

- `GEMINI_API_KEY`: Google Gemini API キー

### オプション設定

- `GEMINI_MODEL`: 使用する Gemini モデル（デフォルト: `models/gemini-1.5-flash`）
- `LOG_LEVEL`: ログレベル（デフォルト: `INFO`）

### MCP サーバー設定（オプショナル）

MCP サーバーを使用する場合:

- `MCP_SERVER_COMMAND`: MCP サーバー起動コマンド（例: `python`）
- `MCP_SERVER_ARGS`: コマンドライン引数（カンマ区切り、例: `server.py,--port,8080`）
- `MCP_TRANSPORT`: トランスポート方式（デフォルト: `stdio`）

## 使用方法

アプリケーションを起動:

```bash
python -m src.main
```

または:

```bash
python src/main.py
```

### チャット操作

1. アプリケーションが起動すると、MCP 接続状態が表示されます
2. `You:` プロンプトでメッセージを入力
3. Gemini からの応答が `Assistant:` として表示されます
4. 終了するには `Ctrl+C` を押します

### 使用例

```
✓ MCP サーバーに接続されました

Gemini Chat へようこそ！
メッセージを入力してください（終了: Ctrl+C）

You: こんにちは
Assistant: こんにちは！何かお手伝いできることはありますか？

You: Pythonについて教えてください
Assistant: Python は...
```

## 開発

### テスト実行

全テストを実行:
```bash
pytest tests/ -v
```

特定のテストファイルを実行:
```bash
pytest tests/test_config.py -v
```

カバレッジレポート付きで実行:
```bash
pytest tests/ --cov=src --cov-report=html
```

### プロジェクト構造

```
gemini-client-for-postgre-mcp/
├── src/
│   ├── __init__.py
│   ├── main.py              # エントリーポイント
│   ├── application.py       # アプリケーション層
│   ├── config.py            # 設定管理
│   ├── error_handler.py     # エラーハンドリング
│   ├── gemini_client.py     # Gemini API クライアント
│   ├── mcp_client.py        # MCP クライアント
│   └── logging_config.py    # ログ設定
├── tests/
│   ├── __init__.py
│   ├── test_application.py
│   ├── test_config.py
│   ├── test_error_handler.py
│   ├── test_gemini_client.py
│   ├── test_logging_config.py
│   ├── test_main.py
│   └── test_mcp_client.py
├── .env.example             # 環境変数テンプレート
├── .gitignore
├── requirements.txt
└── README.md
```

## アーキテクチャ

このアプリケーションは以下のコンポーネントで構成されています:

1. **Application Layer**: アプリケーションのライフサイクルとコンポーネント統合を管理
2. **Configuration Manager**: 環境変数からの設定読み込みと検証
3. **Gemini Client**: Google Gemini API との通信
4. **MCP Client**: MCP サーバーとの接続とコンテキスト取得（オプショナル）
5. **Error Handler**: 統一されたエラーハンドリングとログ記録

## ライセンス

MIT License

## トラブルシューティング

### Gemini API キーエラー

```
設定エラー: GEMINI_API_KEY - 必須設定項目が見つかりません
```

→ `.env` ファイルに `GEMINI_API_KEY` が正しく設定されているか確認してください。

### MCP 接続エラー

```
✗ MCP サーバーは未接続です
```

→ MCP サーバーが起動しているか、設定が正しいか確認してください。MCP はオプショナルなので、接続失敗してもアプリケーションは動作します。

### インポートエラー

```
ModuleNotFoundError: No module named 'google.genai'
```

→ 依存関係が正しくインストールされているか確認してください:
```bash
pip install -r requirements.txt
```