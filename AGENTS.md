# AGENTS.md

会話は原則日本語。コミットメッセージとコード内コメントは英語でも構いません。

## Python / uv

- Python 3.12 を使用し、リポジトリのルートで実行します。グローバル pip は使用しません。
- 依存導入: `uv sync --locked`。
- 実行: `uv run --locked <command>`。`.env` が必要な場合は `--env-file .env` を明示します。
- faster-whisper 使用時は `uv sync` / `uv run` に `--extra stt-local` を付けます。
- 依存変更は `uv add` / `uv remove` を使い、`pyproject.toml` と `uv.lock` を揃えます。

## 検証

- Host コード変更: 関連する pytest を追加・更新し、`./scripts/verify-host.sh` を実行します。
- Firmware 変更: `./scripts/verify.sh` を実行します。
- 文書のみの変更: 内容・リンク・`git diff --check` を確認します。文言固定のテストは追加しません。
- 依存・ESP-IDF・実機の不足などで検証できない場合は、未実行項目と理由を報告します。

## プロジェクト固有の制約

- Hermes 連携は公開 HTTP API のみ。Dashboard `/api/ws`、非公開 Python API、直接 import は使いません。
- API key、device token、Wi-Fi 情報、音声、画像、実機 backup を commit しません。
- factory flash の検証済み backup と一意な serial port が揃うまで flash しません。
- サーボ範囲は FW と Bridge の両方で検証し、物理安全は FW が最終強制します。
- OS package、shell profile、ユーザーの Hermes 設定を無断で変更しません。
- upstream や参照実装からコードをコピーする前に、対象ファイルのライセンスを確認します。

セットアップは [README](README.md)、運用は [operations](docs/operations.md)、実機作業は [hardware-setup](docs/hardware-setup.md) を参照してください。
