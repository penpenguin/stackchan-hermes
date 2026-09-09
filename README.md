# StackChan Hermes Bridge

M5Stack 公式 StackChan（CoreS3）を HermesAgent の「目・耳・口・身体」として使うための、
Firmware・Python Bridge・Device Simulator・MCP server をまとめた専用リポジトリです。

Host 側には、認証付き Device Gateway、Control API、Opus/VAD/STT/Hermes/TTS の音声ターン、
撮影と vision、12 個の stdio MCP tool、Simulator/Mock Hermes、health/metrics/doctor、
再接続・fault injection、運用例を実装しています。Firmware は固定済みの公式 vendor snapshot に、
独立した Bridge client、公式 HAL adapter、NVS/USB provisioning、mDNS、音声、カメラ、表示を
統合しています。

CFW は従来クラウド機能と OTA を削除し、ローカル機能と設定済み Bridge を使います。
更新は USB、Wi-Fi 設定は本体のローカルホットスポットで行います。
送信先・旧設定の扱い・検証範囲は [通信方針](docs/network-policy.md) を参照してください。

## セットアップ

以下は Bridge・Hermes・音声サービスを同じ Mac または Linux / WSL2 ホストで動かし、
StackChan を同じ LAN から接続する構成です。コマンドは特記がない限り、
このリポジトリのルートで実行します。

| 接続先 | 既定のアドレス | 用途 |
| --- | --- | --- |
| Device Gateway | `0.0.0.0:8765` | StackChan からの WebSocket 接続・画像アップロード |
| Control API | `127.0.0.1:8766` | ローカル管理、MCP、health、metrics |
| Hermes API | `127.0.0.1:8642` | 会話・画像理解 |

### 1. ホストの依存を用意する

Python 3.12、[uv](https://docs.astral.sh/uv/) 0.9.2 以上、Git、Opus 対応の ffmpeg、
libopus、libsndfile を用意してください。Python パッケージはプロジェクトの `.venv` に
インストールします。OS パッケージの導入は利用する OS に合わせて行ってください。

```bash
uv sync --locked
./scripts/bootstrap-check.sh --json
```

`bootstrap-check` は不足依存を報告します。実機や本物の Hermes を準備する前に、
Simulator・Mock Hermes・Mock STT/TTS だけで音声の往復と再接続を確認できます。
この E2E には `.env` や実サービスの API key は不要です。

```bash
./scripts/run-simulator-e2e.sh
```

### 2. Hermes の公開 API を起動する

HermesAgent は別途インストールし、利用する LLM provider/model を設定してください。
[Hermes 公式 API Server 手順](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server)
に従い、Hermes 側の `~/.hermes/.env` に次を設定します。既存ファイルには必要な項目を追記・更新します。

```dotenv
API_SERVER_ENABLED=true
API_SERVER_HOST=127.0.0.1
API_SERVER_PORT=8642
```

同じファイルの `API_SERVER_KEY` には、自分で生成した十分に長いランダムなキーを設定します。
その後、Hermes を導入した環境の別ターミナルで起動します。

```bash
hermes gateway
```

Bridge は `/health`、`/v1/capabilities`、`/v1/responses` を使います。
Responses API・SSE・session key に対応する Hermes が必要で、画像理解には画像対応モデルも必要です。
Hermes を別ホストで動かす場合は、SSH 転送などで Bridge から loopback 接続できるようにし、
次の `hermes.base_url` に転送先のローカル URL を設定してください。

### 3. Bridge の設定と認証を用意する

初回のみ、雛形からローカル設定を作成します。既存の設定がある場合はそのファイルを編集してください。

```bash
cp config.example.toml config.toml
cp .env.example .env
chmod 600 .env config.toml
uv run --locked stackchan-bridge token create --device-id stackchan-001
```

生成コマンドは `token` と `token_hash` を表示します。`token` は実機に設定する値です。
この手順ではまず 1 台を接続するため、同じ `token` を `.env` の `STACKCHAN_DEVICE_TOKEN` に設定します。

| `.env` の項目 | 設定する値 |
| --- | --- |
| `STACKCHAN_CONFIG` | `config.toml`（雛形のまま） |
| `HERMES_API_KEY` | Hermes 側の `API_SERVER_KEY` と同じ値 |
| `STACKCHAN_DEVICE_TOKEN` | 生成したデバイス用の `token`。Hermes のキーとは別の値 |
| `STACKCHAN_STT_API_KEY` / `STACKCHAN_TTS_API_KEY` | HTTP 音声サービスが認証を要求する場合のみ設定 |

`.env` と `config.toml` は Git の追跡対象外です。秘密値を記入したファイルやトークン出力を
commit しないでください。`config.toml` 内の既存セクションを次のように編集します。
同じセクションを末尾に重複して追加しないでください。

```toml
[hermes]
base_url = "http://127.0.0.1:8642"

[security]
allowed_devices = ["stackchan-001"]
device_token_env = "STACKCHAN_DEVICE_TOKEN"
```

`hermes.base_url` には `/v1` を付けません。`allowed_devices` の ID は、後で実機に設定する ID と
一致させます。複数台の場合はデバイスごとにトークンを生成し、
`[security.device_token_hashes]` に `デバイスID = "token_hash の値"` を登録します。
環境変数の単一トークンは、ハッシュ未登録の許可デバイスが 1 台の場合だけ使えます。

### 4. 日本語の音声認識・音声合成を設定する

雛形の STT/TTS は両方 `mock` です。Mock STT は固定テキスト、Mock TTS はテスト音を返すため、
実際の日本語会話にはアダプターの変更が必要です。ここではローカルの faster-whisper と
別途起動した [VOICEVOX Engine](https://github.com/VOICEVOX/voicevox_engine) を使います。
Engine の導入・起動方法はリンク先の公式手順を参照してください。

```bash
uv sync --locked --extra stt-local
```

`config.toml` の既存 `[stt]` / `[tts]` セクションの該当項目を変更します。
VOICEVOX Engine は、この例では同じホストの `127.0.0.1:50021` で起動してください。

```toml
[stt]
adapter = "faster-whisper"
language = "ja"
model_name = "small"
device = "cpu"
compute_type = "int8"

[tts]
adapter = "voicevox"
endpoint = "http://127.0.0.1:50021"
speaker = 1
```

faster-whisper は初回利用時にモデルを取得するため、ダウンロード用の通信と空き容量が必要です。
`doctor` の `stt_model_cache: missing` はその事前通知で、診断自体はモデルをダウンロードしません。
既存の HTTP サービスを使う場合は `adapter = "http"` と `endpoint` を設定します。
汎用 TTS は `{"text": "…"}` を POST し、`audio/wav` を受け取る形式です。

Irodori を使う場合は、別途起動した
[Irodori-TTS-Server](https://github.com/Aratako/Irodori-TTS-Server#api) に接続するよう、
既存の `[tts]` セクションを次の設定へ変更します。`sample` はサーバーに登録済みの
voice ID に置き換えてください。Irodori の導入・起動・音声登録はサーバー側で行います。

```toml
[tts]
adapter = "openai"
endpoint = "http://127.0.0.1:8088/v1/audio/speech"
model = "irodori-tts"
voice = "sample"
speed = 1.0
timeout_seconds = 120
api_key_env = "STACKCHAN_TTS_API_KEY" # pragma: allowlist secret

# Optional: shared by every utterance.
[tts.irodori]
caption = "明るく親しみやすい声。穏やかに話す。"
seed = 1234
```

`endpoint` は `/v1/audio/speech` を含む完全な URL を指定します。HTTPS または
loopback HTTP が利用でき、Bridge はパスを自動追加しません。`model` と `voice` は必須、
`speed` は `0.25`〜`4.0`（既定値 `1.0`）です。初回のモデル読み込みなどに時間がかかる場合は、
`timeout_seconds` を最大 `300` 秒まで調整できます。

Irodori 側で認証を有効にしている場合は、同じキーを `.env` の `STACKCHAN_TTS_API_KEY` に
設定します。キー未設定時は認証ヘッダーを送りません。Bridge は標準項目を JSON で送り、
`response_format = "wav"` を指定して受け取った音声を既存の再生形式に変換します。
`[tts.irodori]` は任意です。`caption` は文字列、`seed` は整数で、片方だけでも指定できます。
指定した項目だけを JSON の `irodori.caption` / `irodori.seed` として送り、両方を省略すると
`irodori` 自体を送りません。`seed = 0` も有効です。設定は全発話・分割された各セグメントに
共通で適用され、会話内容に応じた自動変更は行いません。caption の効果はサーバー側のモデルの
対応状況に依存します。その他の Irodori 固有項目と SSE は、このアダプターの対象外です。
環境変数で上書きする場合は `STACKCHAN_TTS__IRODORI__CAPTION` と
`STACKCHAN_TTS__IRODORI__SEED`（例: `0`）を使います。

### 5. `.env` を読み込んで Bridge を起動する

Bridge 自身は `.env` を暗黙には読み込みません。以下では **`uv run --env-file .env`** で、
起動するプロセスに環境変数を渡します。すでに shell に同名の環境変数がある場合はそちらが優先されます。

```bash
uv run --locked --extra stt-local --env-file .env stackchan-bridge serve --config config.toml
```

このコマンドは起動したままにします。別ターミナルでもリポジトリのルートに移動し、
同じ `.env` を明示して診断します。faster-whisper を使わない構成では `--extra stt-local` は不要です。

```bash
uv run --locked --extra stt-local --env-file .env stackchan-bridge doctor --config config.toml --json
uv run --locked --extra stt-local --env-file .env stackchan-bridge devices --config config.toml --json
curl -fsS http://127.0.0.1:8766/health/ready
```

未接続の実機や未取得のバックアップは `doctor` の診断に表示されます。
実機未接続だけでは Bridge の readiness は失敗しません。Hermes に接続できない場合は
ready にならないため、接続先・API key・capabilities を確認してください。

### 6. Firmware を準備して StackChan を接続する

実機には M5Stack StackChan / CoreS3（K151）と ESP-IDF v5.5.4 を使用します。
[ESP-IDF の導入・有効化](docs/operations.md#esp-idf-activation-and-reproducible-prerequisite) と
[Firmware の手順](firmware/README.md) を確認し、Firmware 用ターミナルで依存を取得・検証します。
`/absolute/path/to/esp-idf` は自分の ESP-IDF 配置先に置き換えてください。

```bash
. /absolute/path/to/esp-idf/export.sh
cd firmware
python3 ./fetch_repos.py
idf.py reconfigure
cd ..
./scripts/verify-firmware.sh
```

検証スクリプトが作るビルドは一時ファイルです。書き込み用のバイナリを残す方法、
factory flash のバックアップ、flash・restore コマンドは
[バックアップ・ビルド・書き込み手順](docs/operations.md#firmware-backup-build-flash-and-restore)
にまとめています。**検証済みの 16 MiB factory backup と一意なシリアルポートが揃うまで flash しません。**
書き込み前に [実機の安全条件](docs/hardware-setup.md#stop-before-flash-checklist) を満たしてください。

カスタム Firmware の起動後、端末の Wi-Fi 設定でホストと同じ LAN へ接続します。
USB シリアルの REPL で、ホストの LAN IP・デバイス ID・生成したトークンを登録してください。
次の `192.0.2.10` は例示用なので、実際のホストの LAN IP に置き換えます。

```text
stackchan-hermes set-device-id stackchan-001
stackchan-hermes set-url ws://192.0.2.10:8765/v1/device/ws
stackchan-hermes set-token <生成したデバイストークン>
stackchan-hermes set-touch enabled
```

`set-token` 入力時はシリアル端末のログ保存を無効にしてください。設定は NVS に保存され、
反映には再起動が必要です。実機から見た `127.0.0.1` は Bridge のホストではありません。
ホストへの LAN 内 TCP 8765 接続を許可し、Control API の 8766 は loopback のままにします。
WSL2 の USB 接続・限定 firewall 設定は [運用手順](docs/operations.md#wsl2-usb-prerequisite-manual-windows-action)
を参照してください。

`devices` に `stackchan-001` が現れたら、頭部にタッチして短い日本語を話し、応答音声を確認します。
通常の Firmware 構成では首の動作はロックされています。

### 7. Hermes に StackChan MCP を登録する

[設定例](examples/hermes-config.yaml) のプロジェクトパスを実際の絶対パスに置き換え、
Hermes の既存 `config.yaml` の `mcp_servers` に `stackchan` を追加します。
設定全体を上書きせず、Hermes が `uv` を起動できることも確認してください。

Hermes が stdio 経由で `stackchan-mcp` を起動するため、通常は MCP を別ターミナルで
手動起動する必要はありません。設定反映のため Hermes を再起動し、StackChan の状態取得などで
ツール接続を確認します。MCP の `STACKCHAN_CONTROL_URL` は `http://127.0.0.1:8766` です。
この stdio MCP は Control API に接続するため、Bridge 用 `.env` の読み込みは不要です。
Hermes が別ホストにある場合は、そこで Bridge のコードと実行環境を用意し、Control API も
SSH 転送などで Hermes 側の loopback から到達できるようにします。

待機中のスタックチャンには `stackchan_speak(device_id, text)` で任意の文章を発話させられます。
最大1,000文字を省略せず分割して読み上げ、音声・話速には Bridge の TTS 設定を使います。
録音・応答生成・発話中は `TURN_BUSY` になります。スタックチャン自身の通常会話が
Hermes の返答を待っている間も使用中なので、通知や別のチャットからの呼びかけに使います。

1. `stackchan_speak(device_id="stackchan-001", text="作業が完了しました。")` を呼びます。
2. すぐ返る `turn_id` を使い、`stackchan_get_speech_status(device_id, turn_id)` で結果を確認します。
3. 停止する場合は `stackchan_cancel_speech(device_id, turn_id)` を呼びます。

`ACCEPTED` は受付完了です。実行結果は `COMPLETED`・`CANCELLED`・`FAILED` で確認し、
失敗時には `error_code` を参照します。結果は終了から10分、最大128件のメモリ履歴です。
詳しい API と完了判定は [発話の運用手順](docs/operations.md#direct-speech-from-mcp) を参照してください。

### 常駐運用と開発時の検証

常駐化には [macOS launchd](examples/launchd/README.md) または
[Linux systemd](examples/systemd/README.md) の設定例を使えます。
サービス側では専用の `bridge.env` を読み込むため、ターミナルの環境変数だけに依存させず、
配置先・実行パス・ログディレクトリを設定してください。

開発時の host gate は `./scripts/verify-host.sh`、Firmware を含む最終 gate は
`./scripts/verify.sh` です。host gate の一部も取得済みの Firmware Git 依存を参照するため、
初回は上記の `firmware/fetch_repos.py` を実行してください。Firmware gate には ESP-IDF と
取得済み managed components が必要で、不足時はエラーを返します。

## Repository boundaries

- `bridge/`: device gateway、turn coordination、audio、Hermes client、Control API、MCP。
- `simulator/`: 実機なしで device protocol を再現するクライアント。
- `protocol/`: FW と Bridge が共有する Protocol v1 schema と example。
- `firmware/`: pinned 公式 baseline、Bridge/FW contract、独自 component と公式 HAL 統合。
- `docs/`: 要求、設計、ADR、安全、運用、検証証拠。
- `scripts/`: bootstrap と再現可能な verification entrypoint。

## ライセンス

このプロジェクトの独自コードと文書は [MIT License](LICENSE) で公開します。
取り込んだ公式 Firmware、第三者コード、依存ライブラリ、第三者由来の素材には、
それぞれの元のライセンスが適用されます。元の著作権表示・通知を保持してください。

[ライセンスと配布の整理](docs/licensing.md) に MIT の適用範囲と配布条件を、
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) に第三者コードの来歴と確認済みの
依存ライセンスをまとめています。[通知集](LICENSES/README.md) は Python wheel / sdist にも
同梱します。CoreS3（ESP32-S3）向け Firmware は確認済みのフォントを使い、SDK・モデルを
含む実ビルドの照合と通知の同梱を行います。[配布物の作成・確認記録](docs/license-audit.md)
に対象範囲と手順をまとめています。

## Important constraints

- Bridge は Hermes の公開 `POST /v1/responses` と公開 capability endpoint だけを使います。
- Control API は loopback、device WebSocket/capture upload だけを LAN へ bind します。
- 音声は WebSocket binary frame、画像は認証付き HTTP upload で運びます。
- API key を FW に置かず、音声や常時画像を JSON/Base64 にしません。
- factory backup と一意な serial port が揃うまで実機 flash しません。通常の release 構成は `head=false` と
  `CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y` を維持し、サーボの位置・速度・トルクON出力を
  最下層でも遮断します。解除 build、flash、物理動作はそれぞれ事前検証と明示承認を要します。
- debug 音声保存は既定無効です。有効時は 0600 WAV と TTL purge を使い、明示警告します。

完成条件は [`Goal.md`](Goal.md)、進捗は [`docs/progress.md`](docs/progress.md)、
実機の検証記録は [`docs/hardware-test-report.md`](docs/hardware-test-report.md)、
自動検証の記録は [`docs/verification-report.md`](docs/verification-report.md)、
要求と実装の対応は [`docs/traceability.md`](docs/traceability.md) を参照してください。
依存一覧は [`docs/dependencies.md`](docs/dependencies.md)、詳しい運用・復旧方法は
[`docs/operations.md`](docs/operations.md) にまとめています。
