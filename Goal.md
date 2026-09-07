# StackChan × HermesAgent 実装指示書

## `/goal` 用・FW／Bridge／OpenAI Responses API／MCP統合

## 事前設定

この開発では、Hermesの`/goal`が複数ターンにわたって設計、実装、検証、修正を継続する必要がある。

`~/.hermes/config.yaml`の設定例：

```yaml
goals:
  max_turns: 60
```

以下のコードブロック全体を、プロジェクトを作成するワークスペースでHermesのCLIまたはTUIへ貼り付けること。

---

````text
/goal M5Stack公式StackChan（CoreS3搭載モデル）をHermesAgentの「目・耳・口・身体」として利用する、独立して保守可能なプロジェクト `stackchan-hermes-bridge` を設計、実装、検証、文書化せよ。

このプロジェクトでは、StackChanファームウェアを物理I/O端末、Mac mini等で動くBridgeを音声・画像・ターン制御の中継層、HermesAgentをLLM・Memory・Skills・MCP・ツール判断の主体とする。

BridgeとHermesAgentの接続には、Hermesが公開するOpenAI互換APIを使用する。第一選択は `POST /v1/responses` とし、SSEストリーミング、名前付きconversation、`X-Hermes-Session-Key`、inline image inputを利用する。Hermes Dashboardの `/api/ws`、Hermesの非公開Python内部API、Hermesソースコードの直接import、HermesをGit submoduleとして埋め込む構成は禁止する。

既存プロジェクトは完成コードとして丸ごと流用するのではなく、ハードウェア制御、通信方式、音声処理、実機固有の障害、MCPツール設計、再接続設計を調査するための参照実装として扱う。

参照対象は最低限、次の4リポジトリとする。

- `m5stack/StackChan`
- `kisaragi-mochi/stackchan-mcp`
- `circlemouth/Hermes-StackChan`
- `NousResearch/hermes-agent`

必要に応じて公式ESP-IDF、M5Stack CoreS3 BSP、xiaozhi-esp32、MCP公式SDKの一次資料も参照する。

最初から実装を始めず、作業環境、既存ファイル、Git状態、AGENTS.md、利用可能なツール、接続中ハードウェア、Hermes API capabilitiesを調査したうえで、要求、アーキテクチャ、プロトコル、実装計画、検証方法をファイルとして確定させること。ただし、計画だけを作って終了してはならない。計画確定後は、実装、テスト、修正、実機検証へ継続して進むこと。

────────────────────────────────────
1. 最上位の完成状態
────────────────────────────────────

次の一連の動作が成立していることを完成状態とする。

1. StackChanを起動すると、Wi-Fi経由でBridgeを発見または設定済みURLへ接続する。
2. BridgeはStackChanを認証し、デバイス情報とcapabilitiesを取得する。
3. StackChanの画面タップまたは物理操作によって音声入力を開始できる。
4. StackChanのマイク音声がOpusでBridgeへストリーミングされる。
5. Bridgeが音声をPCMへ復号し、VADによって発話終了を判定する。
6. BridgeがSTTを実行し、日本語テキストを得る。
7. BridgeがHermesの公開OpenAI Responses APIへテキストを送信する。
8. HermesがMemory、Skills、MCP、その他許可されたツールを利用して応答する。
9. BridgeがHermesのSSE応答を受信し、発話可能な文単位へ分割する。
10. BridgeがTTSを実行し、音声をOpusへ変換してStackChanへ送る。
11. StackChanが音声を再生し、発話中の口、顔、首、LEDを自然に制御する。
12. HermesからMCPツールとしてStackChanの首、表情、LED、画面、音量、カメラを制御できる。
13. StackChanのカメラ画像をHermesのResponses APIへ `input_image` として渡し、画像について日本語で応答できる。
14. Bridge停止、Hermes停止、Wi-Fi一時切断後に、安全かつ自動的に復旧できる。
15. 実機がなくてもDevice SimulatorとMock Hermes Serverで主要経路を再現できる。
16. 実装、要求、テスト、既知制約、実機結果のトレーサビリティが文書化されている。

────────────────────────────────────
2. 実装原則
────────────────────────────────────

次の原則を守ること。

- StackChan FWは薄い物理I/O端末とする。
- LLM、Memory、Skills、MCP判断、STT、TTS、画像理解をESP32へ載せない。
- FWとBridgeの間はStackChan専用プロトコルとする。
- BridgeとHermesの間だけをOpenAI互換形式とする。
- 物理安全制約はFWが最終的に強制する。
- BridgeやHermesから不正値が送られても、サーボ、音量、LED、画面、メモリを危険な状態にしない。
- 自律的な瞬き、待機中の小さな首振り、発話中の口パクはFWで行う。
- 意味のある意図的な動作だけをHermesのMCPツールで指示する。
- 音声本体をJSONやBase64へ入れない。
- JPEGを常時送信しない。
- APIキーやHermes認証情報をFWへ格納しない。
- Hermesの内部実装へ依存しない。
- LAN外公開を初期スコープに含めない。
- 既存コミュニティコードをコピーする場合は、コピー前にライセンスと帰属条件を確認する。
- コードをコピーしない場合でも、参照した設計や挙動は`THIRD_PARTY_NOTICES.md`へ記録する。
- 変更理由、採用しなかった案、実機上の制約をADRとして残す。
- テストが通ったという主張だけで完了とせず、実際のコマンド出力を最終報告へ含める。
- ユーザーの既存変更を破壊しない。
- `git reset --hard`、force push、既存未コミット変更の削除、無関係な大規模整形を行わない。
- グローバル`pip install`を行わない。Python依存管理には`uv`を使用する。
- Homebrew、apt、シェルプロファイル、OS設定を勝手に変更しない。必要な外部依存は検出し、インストールコマンドを提示する。
- `.env`、トークン、Wi-Fi認証情報、APIキー、音声、写真をGitへコミットしない。

────────────────────────────────────
3. 採用アーキテクチャ
────────────────────────────────────

全体構成は次とする。

StackChan Firmware
- M5Stack CoreS3ハードウェア制御
- Wi-Fi接続
- Bridge接続
- マイク取得
- Opusエンコード
- Opusデコード
- スピーカー再生
- カメラ撮影
- タッチ・ボタンイベント
- サーボ制御
- LED制御
- 顔・画面制御
- 安全制約
- ローカル自律モーション
- 再接続

Bridge
- Device WebSocket Gateway
- デバイス認証
- プロトコル状態管理
- PCM／Opus変換
- VAD
- STT
- Hermes Responses APIクライアント
- SSEイベント処理
- TTS
- 日本語文分割
- ターン制御
- キャンセル処理
- カメラ画像一時保存
- Hermes向け画像入力
- ローカルControl API
- MCPサーバー
- ログ、メトリクス、health check

HermesAgent
- LLM
- Memory
- Skills
- MCP
- Web検索や外部ツール
- 長期的な人物・会話コンテキスト
- ツール呼び出し判断
- 最終応答生成

通信経路は次とする。

StackChan FW
  ⇅ WebSocket + JSON + raw Opus packets
Bridge Device Gateway
  ⇅ HTTP + SSE
Hermes `/v1/responses`

Hermes
  ⇅ stdio MCP
StackChan MCP Server
  ⇅ loopback Control API
Bridge Device Gateway
  ⇅ WebSocket command
StackChan FW

カメラは次の経路とする。

Hermesまたはユーザー操作
  → Bridge
  → FWへcamera.capture
  → FWがJPEG撮影
  → BridgeのCapture Upload APIへPOST
  → Bridgeが保存・検証
  → Hermes Responses APIへinput_image
  → 画像認識結果を音声応答

────────────────────────────────────
4. 技術スタック
────────────────────────────────────

Bridgeは原則として次を使用する。

- Python 3.12
- uv
- FastAPI
- Uvicorn
- Pydantic v2
- httpx
- MCP公式Python SDK
- pytest
- pytest-asyncio
- pytest-cov
- ruff
- mypy
- opuslibまたは、保守されていてストリーミング可能なlibopusバインディング
- numpy
- soundfileまたはwave
- faster-whisperを任意のSTTアダプターとして利用可能にする
- ffmpegはフォーマット変換のフォールバックに限定する

FWは次を基本とする。

- M5Stack公式StackChan FWをupstream baselineとする
- ESP-IDF
- 公式リポジトリが要求するESP-IDFバージョンを調査して固定する
- 公式CoreS3 BSP、カメラ、オーディオ、LCD、タッチ、サーボ、LED実装を再利用する
- 自作部分は独立したcomponentまたは専用app／boardへ閉じ込める
- コミュニティフォーク全体をベースにしない
- Arduino／PlatformIOへ変更しない
- ESP-IDF組み込みのJSON実装またはupstreamが既に使用しているJSON実装を使う
- 音声と画像の大容量バッファはPSRAMへ配置する
- 固定長、上限付き、またはリングバッファを使用する
- 無制限な動的メモリ確保をストリームループへ入れない

STTとTTSはインターフェースで分離する。

STTアダプター：
- Mock STT
- faster-whisper
- 任意のOpenAI互換transcription endpoint
- 任意のローカルHTTP STT endpoint

TTSアダプター：
- Mock TTS
- UTF-8テキストを受けてWAVを返す汎用HTTP TTS
- VOICEVOX adapter
- Piper系HTTP adapter
- 任意のOpenAI互換speech endpoint

最初のE2EテストではMock STT／TTSを使用する。実音声テストでは、環境に既に存在するローカルSTT／TTSを優先する。

────────────────────────────────────
5. リポジトリ構成
────────────────────────────────────

専用リポジトリでない場合は、ワークスペース直下へ`stackchan-hermes-bridge/`を作る。

最低限、次の構造にする。

stackchan-hermes-bridge/
├── AGENTS.md
├── README.md
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env.example
├── config.example.toml
├── docs/
│   ├── requirements.md
│   ├── architecture.md
│   ├── protocol-v1.md
│   ├── state-machines.md
│   ├── security.md
│   ├── operations.md
│   ├── hardware-setup.md
│   ├── hardware-test-report.md
│   ├── verification-report.md
│   ├── traceability.md
│   ├── upstream-baseline.md
│   ├── progress.md
│   └── adr/
│       ├── ADR-0001-system-boundaries.md
│       ├── ADR-0002-device-protocol.md
│       ├── ADR-0003-hermes-responses-api.md
│       ├── ADR-0004-audio-pipeline.md
│       └── ADR-0005-camera-flow.md
├── protocol/
│   ├── control.schema.json
│   ├── event.schema.json
│   ├── hello.schema.json
│   ├── command.schema.json
│   └── examples/
├── bridge/
│   ├── src/
│   │   └── stackchan_bridge/
│   │       ├── __init__.py
│   │       ├── cli.py
│   │       ├── config.py
│   │       ├── application.py
│   │       ├── device_gateway/
│   │       ├── protocol/
│   │       ├── audio/
│   │       ├── stt/
│   │       ├── tts/
│   │       ├── hermes/
│   │       ├── turns/
│   │       ├── captures/
│   │       ├── control/
│   │       ├── mcp_server/
│   │       ├── observability/
│   │       └── security/
│   └── tests/
├── simulator/
│   ├── src/
│   │   └── stackchan_simulator/
│   ├── fixtures/
│   │   ├── audio/
│   │   └── images/
│   └── tests/
├── firmware/
│   ├── UPSTREAM.md
│   ├── sdkconfig.defaults
│   ├── main/
│   ├── components/
│   │   └── stackchan_bridge_client/
│   └── tests/
├── examples/
│   ├── hermes-config.yaml
│   ├── launchd/
│   └── systemd/
├── scripts/
│   ├── bootstrap-check.sh
│   ├── generate-device-token.py
│   ├── backup-firmware.sh
│   ├── validate-protocol.py
│   ├── verify-host.sh
│   ├── verify-firmware.sh
│   ├── verify.sh
│   ├── run-simulator-e2e.sh
│   ├── hardware-smoke-test.py
│   └── create-debug-report.sh
└── .github/
    └── workflows/
        └── ci.yml

既存リポジトリの構成上、より自然な配置がある場合は変更してよい。ただし、Bridge、FW、Protocol、Simulator、Docs、Testsの境界は維持する。

────────────────────────────────────
6. 要求管理とトレーサビリティ
────────────────────────────────────

`docs/requirements.md`に、次の形式で要求を登録する。

- ID
- 名称
- 理由
- 入力
- 出力
- 正常系
- 異常系
- 受入条件
- 実装箇所
- テスト
- 状態

要求IDは次の体系とする。

- ARCH-xxx：アーキテクチャ
- PROTO-xxx：FW–Bridgeプロトコル
- FW-xxx：ファームウェア
- BR-xxx：Bridge
- AUDIO-xxx：音声
- HERMES-xxx：Hermes API
- MCP-xxx：MCP
- CAM-xxx：カメラ
- SEC-xxx：セキュリティ
- OBS-xxx：可観測性
- OPS-xxx：運用
- TEST-xxx：テスト
- DOC-xxx：文書

`docs/traceability.md`では、要求IDから次を追跡できるようにする。

要求
→ 設計
→ 実装ファイル
→ 単体テスト
→ 統合テスト
→ 実機テスト
→ 結果

要求を実装しただけでテストがないもの、テストはあるが要求が不明なものを残さない。

────────────────────────────────────
7. FW–Bridgeプロトコル v1
────────────────────────────────────

`docs/protocol-v1.md`を、コード実装前に確定する。

7.1 Transport

- WebSocketを使用する。
- デバイス接続endpointは`/v1/device/ws`とする。
- JSON制御メッセージはWebSocket text frameとする。
- 音声Opus packetはWebSocket binary frameとする。
- FW→Bridgeのbinary frameはマイク音声とする。
- Bridge→FWのbinary frameは再生音声とする。
- WebSocketの方向によって音声方向を判定できるため、v1のbinary payloadは原則raw Opus packetとする。
- 1デバイスにつき、入力ストリームと出力ストリームを各1本まで許可する。
- JSONのstart/endメッセージによってbinary frameの所属ストリームを決定する。
- WebSocketが順序を保証する前提で処理する。
- Opus packetサイズ、frame duration、sample rateには上限と検証を設ける。

7.2 共通JSON Envelope

全メッセージは最低限、次を持つ。

```json
{
  "v": 1,
  "type": "command",
  "message_id": "uuid",
  "sent_at_ms": 0,
  "payload": {}
}
````

必要に応じて次を追加する。

```json
{
  "request_id": "uuid",
  "turn_id": "uuid",
  "stream_id": "uuid",
  "device_id": "stackchan-001"
}
```

必須規則：

* `v`は整数。
* `type`は列挙値。
* `message_id`はUUID。
* `request_id`はcommandとresultの対応に使う。
* `turn_id`は一回のユーザー発話からTTS終了までを識別する。
* `stream_id`は音声入力または音声出力を識別する。
* 不明な必須フィールド、上限超過、不正な列挙値は明示的errorにする。
* 未知の追加フィールドは、互換性のため原則無視する。
* 例外なく上限を定義する。
* トークンや秘密情報をpayloadへ含めない。

7.3 認証とHandshake

WebSocket upgrade時に次を使用する。

```http
Authorization: Bearer <device-token>
X-StackChan-Device-Id: stackchan-001
```

接続後5秒以内にFWが`hello`を送信する。

例：

```json
{
  "v": 1,
  "type": "hello",
  "message_id": "uuid",
  "sent_at_ms": 0,
  "payload": {
    "device_id": "stackchan-001",
    "device_name": "StackChan",
    "firmware_version": "0.1.0",
    "hardware_model": "M5STACK-K151",
    "protocol_versions": [1],
    "capabilities": {
      "microphone": true,
      "speaker": true,
      "camera": true,
      "touch": true,
      "head": true,
      "display": true,
      "avatar": true,
      "led_count": 12
    },
    "audio": {
      "codec": "opus",
      "sample_rate": 16000,
      "channels": 1,
      "frame_ms": 60
    }
  }
}
```

Bridgeは`hello_ack`を返す。

```json
{
  "v": 1,
  "type": "hello_ack",
  "message_id": "uuid",
  "sent_at_ms": 0,
  "payload": {
    "connection_id": "uuid",
    "selected_protocol_version": 1,
    "heartbeat_interval_ms": 15000,
    "max_command_timeout_ms": 5000,
    "server_version": "0.1.0"
  }
}
```

要件：

* tokenは十分にランダムな値とする。
* Bridgeはtokenの平文をログへ出さない。
* tokenの比較はconstant-timeで行う。
* 不正token、無効device_id、無効versionを区別できるclose reasonとログを残す。
* device_idだけで認証してはならない。
* 同一device_idの二重接続時の規則を定義する。原則として新しい接続を優先し、古い接続を明示的に閉じる。
* 認証成功前にカメラ、音声、コマンドを受け付けない。

7.4 Heartbeat

* WebSocket ping／pongを使用する。
* Bridgeは一定期間pongがない接続を切断する。
* FWは指数バックオフで再接続する。
* 初期値は1秒、2秒、4秒、8秒、16秒、最大30秒とする。
* 正常接続が一定時間継続したらbackoffをリセットする。
* 意図的disconnectと通信障害を区別する。

7.5 音声入力

制御メッセージ：

```json
{
  "v": 1,
  "type": "audio.input.start",
  "message_id": "uuid",
  "turn_id": "uuid",
  "stream_id": "uuid",
  "sent_at_ms": 0,
  "payload": {
    "codec": "opus",
    "sample_rate": 16000,
    "channels": 1,
    "frame_ms": 60,
    "trigger": "touch"
  }
}
```

この後、FWはraw Opus packetをbinary frameとして送る。

終了：

```json
{
  "v": 1,
  "type": "audio.input.end",
  "message_id": "uuid",
  "turn_id": "uuid",
  "stream_id": "uuid",
  "sent_at_ms": 0,
  "payload": {
    "reason": "silence"
  }
}
```

終了理由：

* `silence`
* `max_duration`
* `user_cancel`
* `device_error`
* `disconnect`

制約：

* 最大録音時間は設定可能にし、初期値15秒。
* 無限録音を許さない。
* 音声packetに最大サイズを設ける。
* stream開始前のbinary frameは破棄し、protocol errorとして記録する。
* stream終了後の遅延packetは破棄する。
* 壊れたOpus packetでdecoder全体を永続的に破損させない。
* decoder再生成とエラー回数上限を設ける。

7.6 音声出力

開始：

```json
{
  "v": 1,
  "type": "audio.output.start",
  "message_id": "uuid",
  "turn_id": "uuid",
  "stream_id": "uuid",
  "sent_at_ms": 0,
  "payload": {
    "codec": "opus",
    "sample_rate": 16000,
    "channels": 1,
    "frame_ms": 60,
    "expected_duration_ms": 0
  }
}
```

Bridgeはその後raw Opus packetを送る。

終了：

```json
{
  "v": 1,
  "type": "audio.output.end",
  "message_id": "uuid",
  "turn_id": "uuid",
  "stream_id": "uuid",
  "sent_at_ms": 0,
  "payload": {
    "reason": "completed"
  }
}
```

終了理由：

* `completed`
* `cancelled`
* `barge_in`
* `tts_error`
* `device_error`
* `disconnect`

FWは受信した音声をリングバッファへ入れ、再生する。

* ネットワーク受信処理とスピーカー再生処理を分離する。
* バッファunderflowとoverflowを検出する。
* underflow時に暴走やノイズを発生させない。
* 再生開始時の先頭欠落を防ぐため、設定可能なsilent prerollを実装する。
* 初期値は500msとするが、実機計測で調整する。
* TTSゲインは設定可能にし、初期値0.65を候補とする。
* 発話キャンセル時は残存バッファを破棄する。

7.7 Command

例：

```json
{
  "v": 1,
  "type": "command",
  "message_id": "uuid",
  "request_id": "uuid",
  "sent_at_ms": 0,
  "payload": {
    "name": "head.set_angles",
    "args": {
      "yaw": 15,
      "pitch": 40,
      "speed": 30
    }
  }
}
```

結果：

```json
{
  "v": 1,
  "type": "command_result",
  "message_id": "uuid",
  "request_id": "uuid",
  "sent_at_ms": 0,
  "payload": {
    "ok": true,
    "result": {
      "yaw": 15,
      "pitch": 40
    }
  }
}
```

失敗：

```json
{
  "v": 1,
  "type": "command_result",
  "message_id": "uuid",
  "request_id": "uuid",
  "sent_at_ms": 0,
  "payload": {
    "ok": false,
    "error": {
      "code": "INVALID_ARGUMENT",
      "message": "pitch is outside the safe range"
    }
  }
}
```

最低限のcommand：

* `device.get_status`
* `device.get_info`
* `audio.set_volume`
* `display.set_brightness`
* `display.show_text`
* `avatar.set_expression`
* `avatar.set_blink`
* `head.get_angles`
* `head.set_angles`
* `head.home`
* `led.set`
* `led.set_all`
* `led.clear`
* `camera.capture`
* `speech.cancel`

BridgeとFWの両方で引数を検証する。

7.8 Event

最低限のevent：

* `touch.tap`
* `touch.long_press`
* `touch.stroke`
* `button.press`
* `wakeword.detected`
* `battery.changed`
* `wifi.changed`
* `audio.underrun`
* `audio.overflow`
* `camera.completed`
* `servo.error`
* `device.error`

イベントにはdevice_id、message_id、時刻、event subtype、必要な値を持たせる。

すべての物理イベントをHermesへ送らない。

* タップによる録音開始はBridgeまたはFWで処理する。
* 瞬きや軽い待機モーションはFWで処理する。
* 意味のある通知だけをHermesへ渡す。
* イベント頻度を制限し、タッチノイズやセンサーノイズでHermesを連続起動しない。

7.9 Protocol Error

エラーコードを列挙する。

* `UNSUPPORTED_VERSION`
* `UNAUTHORIZED`
* `UNKNOWN_DEVICE`
* `INVALID_MESSAGE`
* `INVALID_ARGUMENT`
* `INVALID_STATE`
* `COMMAND_TIMEOUT`
* `DEVICE_BUSY`
* `AUDIO_DECODE_ERROR`
* `AUDIO_ENCODE_ERROR`
* `CAPTURE_FAILED`
* `INTERNAL_ERROR`

エラーは、ユーザー向けメッセージと診断用詳細を分離する。

────────────────────────────────────
8. FW要件
────────────────────────────────────

FW-001 Upstream baseline

* 公式StackChanリポジトリの現在のdefault branch、tag、対応ESP-IDFを調査する。
* 使用するcommit SHAを`firmware/UPSTREAM.md`へ固定する。
* upstreamとの差分を最小化する。
* upstream変更を取り込む手順を文書化する。
* コミュニティフォークをupstreamにはしない。

FW-002 ハードウェア抽象化

既存の次の実装を再利用する。

* CoreS3初期化
* LCD
* Touch
* Camera
* Microphone
* Speaker
* Servo
* LED
* PMIC
* Battery
* Wi-Fi
* BLE provisioning
* Avatar

独自ロジックから直接GPIOを操作せず、既存BSPまたはdriver abstractionを経由する。

FW-003 設定

NVSへ次を保存する。

* `device.id`
* `device.name`
* `bridge.url`
* `bridge.fallback_url`
* `bridge.token`
* `bridge.discovery_enabled`
* `audio.volume`
* `display.brightness`
* `motion.idle_level`
* `touch.enabled`

接続先の優先順位：

1. NVSの`bridge.url`
2. mDNS `_stackchan-hermes._tcp.local`
3. Kconfig default
4. 明示的エラー表示

IP、token、Wi-Fi情報をソースへハードコードしない。

設定値を再ビルドなしで変更できる経路を用意する。

優先順位：

1. 既存Wi-Fi provisioning画面の拡張
2. 専用Bridge設定画面
3. USB serial provisioning utility

少なくとも一つは完成させる。

FW-004 状態機械

FW側の状態：

* `BOOTING`
* `CONNECTING_WIFI`
* `CONNECTING_BRIDGE`
* `IDLE`
* `LISTENING`
* `SPEAKING`
* `ERROR`
* `UPDATING`

禁止遷移と、各状態のentry／exit処理を`docs/state-machines.md`へ記載する。

例：

* `SPEAKING`開始時に再生バッファを初期化する。
* `SPEAKING`終了時に口と表情を戻す。
* 切断時にサーボを安全姿勢へ戻す。
* `ERROR`時に危険な身体コマンドを拒否する。
* 再接続後に音量、明るさ、頭角度、状態をBridgeと再同期する。

FW-005 自律表示

状態と見た目を対応させる。

* IDLE：通常表情、弱い待機LED
* LISTENING：聞き取り表情、前方を見る
* THINKING相当のBridge通知：考え中表情
* SPEAKING：口パク、小さな発話モーション
* ERROR：エラー表示、過度に大きな動作をしない

FWの瞬き、待機モーション、口パクはネットワーク遅延に依存しないようローカル処理する。

FW-006 サーボ安全

* yaw、pitchの安全範囲をboard configへ定義する。
* 公式仕様または実機制約を根拠として記録する。
* pitchは安全な推奨範囲を初期値とする。
* 速度と角速度に上限を設ける。
* 範囲外はclampではなく、原則エラーにする。自律モーション内部のみ安全clampを許可する。
* 起動直後に急激に原点へ動かさない。
* 電源状態、servo availabilityを確認する。
* 通信切断時に最後の不自然な姿勢を保持し続けない。
* 単体テスト用にservo command生成部分をハードウェア非依存化する。

FW-007 オーディオ

* 16kHz、mono、signed 16-bit PCMをBridgeとの論理標準とする。
* Opus codec parameterはhelloで通知する。
* 20ms、40ms、60ms packetの少なくとも使用中設定を正しく扱う。
* audio bufferをPSRAMへ配置する。
* マイク取得、Opus encode、WebSocket送信を別taskまたは明確な非同期境界にする。
* WebSocket受信、Opus decode、スピーカー再生を別taskまたは明確な非同期境界にする。
* queue長とdrop policyを定義する。
* watchdogを阻害するblocking処理を入れない。
* speaker出力がmicへ回り込むことを前提にする。
* v1の完成条件はpush-to-talkまたはtouch-to-talkとする。
* wake wordとbarge-inは基礎経路完成後に追加する。

FW-008 カメラ

* JPEG、320×240を基本とする。
* JPEG qualityは設定可能とする。
* capture中に複数要求を受けた場合のbusy応答を定義する。
* capture_idをBridge commandから受け取る。
* 撮影後、認証付きHTTP multipartでBridgeへuploadする。
* 画像全体を内部RAMへ複製しない。
* upload失敗時のretry回数を制限する。
* 無限retryしない。
* capture完了、失敗をeventで返す。
* 常時映像送信は実装しない。

FW-009 再接続

* Bridge停止後にFWを再起動せず接続復旧できる。
* Wi-Fi一時切断後に復旧できる。
* stale socketを残さない。
* 古いreceive taskが残ったまま新接続を作らない。
* 正常disconnectと異常disconnectを区別する。
* 再接続中もローカルUIを操作可能にする。
* backoff中にユーザーへ状態を表示する。

FW-010 Flash安全

実機へ最初にflashする前に、次を実施する。

* 接続serial portを一意に確認する。
* 16MB全flash backupを取得する。
* partition tableを個別取得する。
* backupのサイズを検証する。
* SHA-256を記録する。
* backupの復元コマンドを文書化する。
* 現在FW versionとboot logを保存する。
* NVSを消去するfull flashと、設定を保持するapp-only flashを区別する。
* serial portが複数あり一意に判断できない場合はflashしない。
* backup不成功の状態でflashしない。
* secure boot、flash encryption、partition変更、OTA方式変更は初期スコープ外とする。

────────────────────────────────────
9. Bridge要件
────────────────────────────────────

BR-001 CLI

次のCLIを用意する。

* `stackchan-bridge serve`
* `stackchan-bridge doctor`
* `stackchan-bridge devices`
* `stackchan-bridge token create`
* `stackchan-bridge captures list`
* `stackchan-bridge captures purge`
* `stackchan-mcp`
* `stackchan-simulator`

BR-002 Config

設定は次の優先順位で読む。

1. CLI arguments
2. environment variables
3. config TOML
4. safe defaults

`.env.example`と`config.example.toml`を作る。

最低限の設定：

* device bind host
* device WebSocket port
* control bind host
* control port
* Hermes base URL
* Hermes API key
* Hermes profile／path prefix
* STT adapter
* TTS adapter
* Opus settings
* VAD settings
* recording limits
* TTS segmentation limits
* capture directory
* capture TTL
* log level
* JSON log enable
* allowed devices
* device token hashes
* automatic LED／expression enable

起動時に設定を検証し、不正設定はfail fastとする。

BR-003 Device Registry

* device_idごとに接続状態を管理する。
* tokenは平文保存を避ける。
* token generation scriptを提供する。
* tokenは一度だけ表示する。
* token hashをconstant-time比較する。
* unknown deviceを拒否する。
* device capabilitiesを保持する。
* cameraなし、LEDなし等のcapability差を扱う。
* disconnected deviceへのcommandは型付きエラーを返す。

BR-004 Device Gateway

* `/v1/device/ws`
* `/v1/device/captures/{capture_id}`
* handshake timeout
* heartbeat
* message validation
* binary audio routing
* command pending map
* command timeout
* duplicate request handling
* reconnect時のcleanup
* capture upload validation

を実装する。

BR-005 Local Control API

loopbackへだけbindする。

候補endpoint：

* `GET /health/live`
* `GET /health/ready`
* `GET /v1/control/devices`
* `GET /v1/control/devices/{device_id}`
* `POST /v1/control/devices/{device_id}/commands`
* `POST /v1/control/devices/{device_id}/speech/cancel`
* `GET /v1/control/captures/{capture_id}`
* `DELETE /v1/control/captures/{capture_id}`

Control APIはLANへ公開しない。

MCP serverはこのControl APIまたは同一プロセス内interfaceを利用する。

BR-006 Application health

`live`はprocessが生存しているかを返す。

`ready`は最低限、次を確認する。

* config valid
* capture directory writable
* libopus available
* Hermes `/health` success
* Hermes `/v1/capabilities` success
* Responses API support
* STT adapter ready
* TTS adapter ready

デバイス未接続はBridge自体のreadiness failureにはしない。readiness payloadへ`connected_devices: 0`として表示する。

BR-007 mDNS

Bridgeは `_stackchan-hermes._tcp.local` を広告できるようにする。

広告情報：

* service name
* port
* protocol version
* auth required
* server version

mDNSが利用できない環境でも固定URLで動作する。

────────────────────────────────────
10. ターン制御
────────────────────────────────────

`TurnCoordinator`を独立モジュールにする。

1デバイスにつきactive turnは1つとする。

ターン状態：

* `IDLE`
* `CAPTURING`
* `TRANSCRIBING`
* `WAITING_HERMES`
* `SYNTHESIZING`
* `PLAYING`
* `CANCELLING`
* `FAILED`
* `COMPLETED`

ターン開始trigger：

* touch
* button
* wake word
* local Control API
* simulator

v1ではtouchまたはbuttonを必須とする。

ターンには次を持たせる。

* turn_id
* device_id
* started_at
* trigger
* input stream_id
* transcript
* Hermes conversation name
* Hermes response id
* output stream IDs
* cancellation token
* timing metrics
* failure reason

同時入力の扱い：

* IDLEなら開始する。
* CAPTURING中の再タップは録音終了またはcancelとする。
* TRANSCRIBING／WAITING_HERMES中の再タップは現在ターンをcancelする。
* PLAYING中の再タップはTTSをcancelし、新ターン開始を許可する。
* 同時に二つのHermes requestを同じdevice conversationへ送らない。

キャンセル時：

* STT taskをcancelする。
* Hermes SSE読み取りを停止する。
* 以降のdeltaを破棄する。
* TTS taskをcancelする。
* FWへ`speech.cancel`を送る。
* 再生queueを破棄する。
* stateをIDLEへ戻す。
* 古いturn_idの結果を新しいターンへ混入させない。

────────────────────────────────────
11. VADと音声入力
────────────────────────────────────

最初はBridge側RMS VADを実装する。

初期候補値：

* start speech：60ms以上
* end silence：650ms
* minimum speech：240ms
* preroll：360ms
* maximum recording：15000ms

すべてconfig化する。

RMS VADは次を持つ。

* noise floor
* start threshold
* end threshold
* hysteresis
* preroll ring buffer
* minimum speech duration
* maximum duration
* test用deterministic clock

テストfixtureとして次を用意する。

* 無音
* 短すぎる音
* 単一発話
* 発話中の短い無音
* 長い無音
* ノイズのみ
* TTS回り込み
* 最大時間到達

v1完成後、必要ならSilero VAD等をadapterとして追加する。ただし、RMS VADを削除しない。

音声データはデフォルトで保存しない。デバッグ保存は明示設定時のみとし、保存先、TTL、警告を設ける。

────────────────────────────────────
12. STT
────────────────────────────────────

共通interface：

* input：16kHz mono PCMまたはWAV
* output：text、language、confidence相当、duration、provider metadata
* cancellation対応
* timeout対応
* empty transcript対応

最低限のadapter：

1. Mock STT
2. faster-whisper
3. Generic HTTP STT

faster-whisper：

* model名をconfig化
* language初期値`ja`
* deviceとcompute_typeをconfig化
* 初回downloadをdoctorで検出する
* model download中にBridge全体をblockしない
* empty resultを正常な「聞き取れなかった」として扱う
* transcriptをログへ出すかはprivacy設定に従う

STT失敗時：

* Hermesへ空文字を送らない。
* StackChanへ短いエラー表示を出す。
* 必要ならローカル固定音声を再生する。
* stateをIDLEへ戻す。
* エラー種別をmetricsへ記録する。

────────────────────────────────────
13. Hermes OpenAI Responses API統合
────────────────────────────────────

HERMES-001 公開API限定

使用可能：

* `GET /health`
* `GET /v1/capabilities`
* `GET /v1/models`
* `GET /v1/skills`
* `GET /v1/toolsets`
* `POST /v1/responses`

禁止：

* Dashboard `/api/ws`
* Hermes Python module import
* SessionDB直接操作
* Hermes内部WebSocket RPC
* Hermesのソースコードへのpatch
* 非公開endpointへの依存

HERMES-002 起動時capability確認

Bridge起動時にBearer認証付きで次を確認する。

* `/health`
* `/v1/capabilities`

次を確認する。

* `responses_api`
* streaming
* session key header
* image inputに必要なsurface
* toolsets／skills discovery endpointの有無

必要機能がない場合、readyをfalseにし、必要なHermes versionまたは設定を明示する。

`/v1/chat/completions` fallbackは、明示設定された場合のみ許可する。内部`/api/ws`へfallbackしてはならない。

HERMES-003 Request

通常ターン：

```http
POST /v1/responses
Authorization: Bearer <API_SERVER_KEY>
X-Hermes-Session-Key: agent:stackchan:device:<device_id>
Content-Type: application/json
Accept: text/event-stream
```

body例：

```json
{
  "model": "hermes-agent",
  "conversation": "stackchan:<device_id>",
  "instructions": "これはStackChanを介した日本語の音声会話です。自然で簡潔に答えてください。原則2文以内とし、冗長な列挙を避けてください。必要な場合は利用可能なMCPやSkillsを使用してください。",
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "<transcript>"
        }
      ]
    }
  ],
  "store": true,
  "stream": true
}
```

model名はhardcodeせず、capabilitiesまたはconfigから取得する。Hermes profileのdefault modelを原則利用し、provider／model直接指定は任意設定とする。

conversation：

* `stackchan:<device_id>`
* deviceごとに分離する。
* conversation nameにtokenや個人情報を含めない。
* ユーザーによる会話reset手段を用意する。
* resetしても`X-Hermes-Session-Key`は維持し、長期Memory scopeと会話transcriptを区別する。

session key：

* `agent:<profile>:stackchan:<device_id>`
* 256文字以内
* control characterを含めない
* configでprefix変更可能

HERMES-004 SSE

最低限、次のeventを処理する。

* `response.created`
* `response.output_text.delta`
* `response.output_item.added`
* `response.output_item.done`
* `response.completed`
* error event
* connection close

Responses APIで返るfunction_callとfunction_call_outputはHermes側ですでに実行済みとして扱う。Bridgeが同じtoolを再実行してはならない。

tool開始を検出したらStackChanをthinking表示にできるようにする。

deltaはそのまま一文字ずつTTSへ渡さない。

HERMES-005 日本語音声向け分割

`SpeechSegmenter`を独立実装する。

区切り候補：

* `。`
* `！`
* `？`
* 改行
* 文字数上限
* 一定時間deltaが来ない
* response.completed

初期値候補：

* 最大2セグメント
* 1セグメント最大60～100日本語文字
* 全体最大120～180日本語文字
* 最初の完全な文が得られた時点でTTSを開始
* Markdown記号、URL、コードブロック、表を音声向けに整形
* 絵文字は意味を壊さない範囲で除去または読み替え
* MCP toolの内部ログは発話しない

設定可能にする。

HERMES-006 エラー

* 401：認証エラー
* 404：endpointまたはprofile path誤り
* 429：rate limit
* 5xx：Hermes／provider障害
* timeout
* malformed SSE
* connection reset

を区別する。

ユーザーへは短い日本語で通知する。

診断ログにはHTTP status、request_id、turn_idを残すが、API keyと会話全文を残さない。

────────────────────────────────────
14. TTS
────────────────────────────────────

共通interface：

* input：日本語text
* output：PCM／WAV、sample rate、duration
* cancellation
* timeout
* provider metadata

最低限のadapter：

1. Mock TTS
2. Generic HTTP WAV TTS
3. VOICEVOXまたはPiper系adapterのいずれか一つ

Bridge内部で次を正規化する。

* mono
* signed 16-bit PCM
* 16kHz
* DC offset
* gain
* leading silence
* trailing silence

TTS生成はセグメント単位とする。

順序保証：

* segment 1の再生中にsegment 2を生成できる。
* 再生順は必ず維持する。
* segment 2が先に完成してもsegment 1より先に送らない。
* cancel時は未送信segmentを破棄する。
* 古いturnのTTSを新しいturnへ送らない。

TTS失敗時：

* 既に生成済みsegmentまで再生するか、全体を中止するかを設定可能にする。
* デフォルトは中止。
* FWへaudio.output.end reason=`tts_error`を送る。
* stateをIDLEへ戻す。

────────────────────────────────────
15. MCP Server
────────────────────────────────────

MCP serverはBridge本体とは別entrypointのstdio serverとする。

標準出力へログを出さない。ログはstderrへ出す。

Hermesのconfig exampleを`examples/hermes-config.yaml`へ作るが、ユーザーの`~/.hermes/config.yaml`を無断変更しない。

最低限のtool：

15.1 `stackchan_get_status`

返却：

* device connected
* firmware version
* protocol version
* battery
* volume
* brightness
* Wi-Fi RSSI
* current state
* active turn
* head angles
* capabilities

15.2 `stackchan_take_photo`

引数：

* `device_id`
* `question` optional
* `quality` optional

返却：

* capture_id
* MIME type
* width
* height
* SHA-256
* local URLまたはresource
* MCP ImageContentが利用可能ならimage block
* expiry time

画像を返せないHermes／MCP構成では、loopback URLと明確なfallback情報を返す。

15.3 `stackchan_set_head_angles`

引数：

* yaw
* pitch
* speed optional

BridgeとFWの両方で範囲検証する。

15.4 `stackchan_home_head`

安全な中央姿勢へ戻す。

15.5 `stackchan_set_expression`

最低限：

* idle
* happy
* thinking
* sad
* surprised
* embarrassed

15.6 `stackchan_set_leds`

* 単色
* 全LED
* 配列
* clear

配列長とRGB範囲を検証する。

15.7 `stackchan_display_text`

* text
* duration
* priority

文字数とdurationに上限を設ける。

15.8 `stackchan_set_volume`

0～100。

15.9 `stackchan_cancel_speech`

現在の再生を停止する。

15.10 `stackchan_get_touch_state`

直近のtouch状態を返す。

初期MCPへ公開しないtool：

* device reboot
* firmware update
* NVS wipe
* power off
* token変更
* Wi-Fi変更

これらはControl APIの管理機能としても初期スコープ外とする。

MCP toolはdevice未接続時にprocess crashせず、`DEVICE_NOT_CONNECTED`を返す。

────────────────────────────────────
16. カメラと画像認識
────────────────────────────────────

CAM-001 Capture lifecycle

1. Bridgeがcapture_idを発行する。
2. BridgeがFWへcamera.capture commandを送る。
3. FWがJPEGを撮影する。
4. FWがcapture_id付きでuploadする。
5. BridgeがContent-Type、size、JPEG magic、上限、device ownershipを検証する。
6. SHA-256を計算する。
7. CaptureStoreへ保存する。
8. TTL経過後に削除する。

CAM-002 Capture security

* uploadにもdevice認証を要求する。
* capture_idを推測困難にする。
* 別deviceのcapture_idを使用できない。
* 最大画像サイズを設定する。
* MIME typeだけを信用しない。
* path traversalを防ぐ。
* 元ファイル名を保存pathに使用しない。
* EXIF等の追加metadataを必要に応じて除去する。
* デフォルトTTLは10分。
* 永続保存は明示設定時のみ。

CAM-003 Hermes vision

明示的な「見るターン」を実装する。

例：

* 特定の画面ボタン
* 長押し
* Control API
* Simulator

見るターンでは、JPEGをHermes requestへ添付する。

```json
{
  "role": "user",
  "content": [
    {
      "type": "input_text",
      "text": "この画像について説明してください"
    },
    {
      "type": "input_image",
      "image_url": "data:image/jpeg;base64,..."
    }
  ]
}
```

画像はHermesへ送る時点だけBase64 data URLへ変換してよい。FW–Bridge間ではBase64を使用しない。

さらにMCPの`stackchan_take_photo`経路も実装・検証する。

MCP ImageContentが現在のHermes経路で正しく処理されない場合、次のfallbackを用意する。

* CaptureStoreのloopback URL
* 明示的な「見るターン」によるResponses API input_image
* エラー内容と制約を文書化

画像経路をMCP ImageContentだけへ依存させない。

────────────────────────────────────
17. セキュリティ
────────────────────────────────────

SEC-001 Network boundary

* Hermes APIは127.0.0.1へbindする。
* Bridge Control APIは127.0.0.1へbindする。
* Device WebSocketとCapture APIだけをLAN interfaceへbindする。
* LAN外公開はしない。
* Firewall例を文書化する。
* CORSは不要なら無効。
* wildcard CORSを設定しない。

SEC-002 Secret

* Hermes API keyはBridgeだけが持つ。
* FWはdevice tokenだけを持つ。
* device tokenとHermes API keyを同じ値にしない。
* tokenをログへ出さない。
* tokenをURL queryへ入れない。
* `.env`をGit ignoreする。
* debug reportでsecretをredactする。

SEC-003 Transport

v1はLAN限定の`ws://`を許可するが、暗号化されないリスクを`docs/security.md`へ明記する。

WSS対応は次の条件で追加してよい。

* ESP-IDFのTLS実装を利用する。
* 証明書検証を無効化しない。
* 自己署名証明書を無条件acceptしない。
* 証明書更新手順を用意する。

WSSを初期完成条件にはしない。

SEC-004 Resource limits

* JSON最大サイズ
* WebSocket frame最大サイズ
* audio packet最大サイズ
* capture最大サイズ
* command timeout
* capture timeout
* STT timeout
* TTS timeout
* Hermes timeout
* device connection数
* request rate
* capture rate

を設定可能かつ初期値付きで定義する。

────────────────────────────────────
18. 可観測性
────────────────────────────────────

構造化ログに次を含める。

* timestamp
* level
* component
* device_id
* connection_id
* turn_id
* stream_id
* request_id
* event
* duration_ms
* error_code

ログへ含めないもの：

* API key
* device token
* Wi-Fi password
* raw audio
* image bytes
* 会話全文
* Base64画像

privacy debug modeでのみtranscriptを出せるようにする。

最低限のmetrics：

* connected_devices
* websocket_connect_total
* websocket_disconnect_total
* websocket_auth_failure_total
* active_turns
* audio_input_frames_total
* audio_output_frames_total
* audio_decode_error_total
* audio_underrun_total
* stt_duration_seconds
* hermes_time_to_first_delta_seconds
* hermes_total_duration_seconds
* tts_duration_seconds
* time_to_first_audio_seconds
* turn_total_duration_seconds
* capture_total
* capture_failure_total
* command_timeout_total

Prometheus endpointを実装するか、同等のmachine-readable metricsを提供する。

`stackchan-bridge doctor`では次を診断する。

* config
* write permission
* libopus
* ffmpeg
* STT
* TTS
* Hermes health
* Hermes capabilities
* MCP config example
* mDNS
* ports
* connected device
* capture storage
* firmware backup presence

────────────────────────────────────
19. Device Simulator
────────────────────────────────────

実機なしでBridgeを検証できるSimulatorを作る。

機能：

* WebSocket接続
* Bearer認証
* hello
* heartbeat
* command受信
* command_result
* fixture JPEG upload
* fixture WAVのOpus送信
* 受信TTS OpusのWAV保存
* touch event送信
* battery／Wi-Fi event
* reconnect
* disconnect fault
* malformed JSON
* malformed Opus
* delayed command
* command timeout
* duplicate message
* invalid token
* unsupported protocol version

CLI例：

```bash
uv run stackchan-simulator \
  --bridge ws://127.0.0.1:8765/v1/device/ws \
  --device-id sim-001 \
  --token-env STACKCHAN_SIM_TOKEN \
  --input-wav simulator/fixtures/audio/ja-short.wav \
  --output-wav /tmp/stackchan-output.wav
```

Mock Hermes Serverも用意する。

Mock Hermesは次を再現する。

* `/health`
* `/v1/capabilities`
* `/v1/responses`
* SSE text delta
* function_call progress
* response.completed
* 401
* 429
* 500
* malformed SSE
* delayed response
* disconnect

Mock STT、Mock TTS、Simulator、Mock Hermesを使ってCI上で一往復を完結させる。

────────────────────────────────────
20. テスト
────────────────────────────────────

20.1 Bridge unit tests

* config validation
* protocol models
* message limits
* token comparison
* handshake
* duplicate device
* command timeout
* command result routing
* reconnect cleanup
* VAD
* speech segmentation
* TTS ordering
* cancellation
* capture validation
* capture TTL
* Hermes SSE parser
* session key generation
* conversation naming
* error mapping
* log redaction

20.2 Protocol contract tests

JSON SchemaとPydantic modelが一致すること。

protocol exampleが全てschema validationを通ること。

不正exampleが期待通り失敗すること。

FW側の定数とBridge側の定数を可能な範囲で自動照合する。

20.3 Integration tests

* Simulator ↔ Bridge handshake
* audio input
* STT
* Mock Hermes
* TTS
* audio output
* command
* capture upload
* MCP control
* cancel
* reconnect

20.4 Fault tests

* Bridge途中停止
* Device途中切断
* Hermes timeout
* STT timeout
* TTS timeout
* 壊れたOpus
* JPEG偽装
* oversized payload
* wrong token
* duplicated request_id
* stale turn result
* cancellation race

20.5 Firmware tests

* `idf.py build`
* protocol parser
* command argument validation
* servo limit
* state transition
* reconnect backoff
* buffer limit
* settings precedence
* token redaction
* camera busy
* audio queue overflow policy

可能な部分はhost testとする。実機依存部分はUnity／pytest-embeddedまたはhardware smoke testへ分ける。

20.6 Coverage

Bridgeの主要純粋ロジックについて、line coverage 85%以上を目安とする。

coverage数値だけを目的に無意味なtestを作らない。

次は必ずtest対象とする。

* protocol
* state machine
* SSE parser
* VAD
* segmentation
* cancellation
* security validation
* capture validation

────────────────────────────────────
21. 実機受入シナリオ
────────────────────────────────────

実機が接続可能な場合、次を順番に実施し、`docs/hardware-test-report.md`へ記録する。

Windows Hyper-V firewall lifecycle

* WSL mirrored networkingで物理端末を検証するときは、明示承認後に
  `StackChanHermesBridge8765` を1件だけ作成する。対象はWSL VM creator、Inbound Allow、
  TCP 8765、`LocalSubnet`に限定し、既定受信動作は変更しない。
* 連続した実機検証中は各シナリオ後に削除しない。Bridge停止中は8765/8766にlistenerが
  ないことを確認し、同じ限定規則を次の実機シナリオで再利用する。
* この規則はGoal全体の作業用であり、Goal 全体の終了時に一度だけ削除する。明示的な
  中止指示で最終cleanupへ移る場合も同じ扱いとする。
* 最終cleanupでは、同名規則数が0件、WSL Hyper-V firewallの
  `DefaultInboundAction=Block`、8765/8766 listenerなし、USB detach済みを確認して記録する。

HW-01 Factory backup

* full flash backup成功
* 16MB確認
* SHA-256記録
* partition table backup
* restore command記録

HW-02 Boot

* custom FW boot
* boot loopなし
* display正常
* touch正常
* Wi-Fi接続
* Bridge接続

HW-03 Status

* device info取得
* battery取得
* volume取得
* firmware version取得

HW-04 Body

* head yaw
* head pitch
* home
* expression
* LED
* brightness
* volume

各動作を小さい範囲から試す。

HW-05 Reconnect

* Bridge停止
* FWが再接続表示
* Bridge再起動
* FW再起動なしで復旧

HW-06 Audio output

* Bridgeから固定日本語WAVを送信
* Opus再生
* 先頭音節欠落の有無
* 音割れ
* underflow
* 再生終了後state復帰

HW-07 Audio input

* touchで録音開始
* Opus受信
* WAV再構成
* 音量
* ノイズ
* 発話終了
* 最大時間停止

HW-08 STT

* 短い日本語3パターン
* 認識結果記録
* latency記録
* empty speech処理

HW-09 Hermes

* 「こんにちは」
* 「今日の日付を教えて」
* MCPまたはSkillを使う質問

Responses API一往復を確認する。

HW-10 Full voice turn

* touch
* speech
* STT
* Hermes
* TTS
* StackChan再生
* IDLE復帰

HW-11 Cancel

* TTS再生中にcancel
* 音声停止
* queue破棄
* 新しいターン開始

HW-12 Camera

* JPEG撮影
* upload
* CaptureStore
* Hermes input_image
* 画像説明
* TTL削除

HW-13 Failure

* Hermes停止
* TTS停止
* Wi-Fi一時切断
* wrong token
* camera failure

ユーザー向け表示と復旧を確認する。

各シナリオについて次を記録する。

* 実施日
* FW commit
* Bridge commit
* Hermes version
* hardware model
* command
* expected
* actual
* log抜粋
* result
* unresolved issue

────────────────────────────────────
22. 検証スクリプト
────────────────────────────────────

`scripts/verify-host.sh`は最低限、次を実行する。

```bash
#!/usr/bin/env bash
set -euo pipefail

uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy bridge/src simulator/src
uv run pytest -q --cov=stackchan_bridge --cov-report=term-missing
uv run python scripts/validate-protocol.py
uv run stackchan-bridge doctor --offline
```

`scripts/verify-firmware.sh`は最低限、次を実行する。

```bash
#!/usr/bin/env bash
set -euo pipefail

cd firmware
idf.py build
```

`scripts/verify.sh`は両方を呼ぶ。

ESP-IDFやlibopus等が存在しない場合に、黙ってskipしない。

* 不足依存を明示する。
* stop conditionに該当するか判断する。
* CI用に明示的skip optionを設ける場合でも、最終verificationではskipを許可しない。

────────────────────────────────────
23. CI
────────────────────────────────────

CIで最低限、次を実行する。

* uv lock check
* ruff format check
* ruff check
* mypy
* pytest
* protocol schema validation
* Simulator E2E
* secret scan
* dependency audit
* firmware build

Firmware buildは、公式ESP-IDF Docker imageまたは再現可能なsetupを使用する。

CIとローカルのverify scriptが異なる検証をしないようにする。

────────────────────────────────────
24. 運用
────────────────────────────────────

Mac miniを主要hostとして想定する。

次を作る。

* launchd plist example
* systemd unit example
* ログ保存先
* restart policy
* environment fileの保存方法
* token生成方法
* device追加方法
* Hermes profile設定例
* FW flash手順
* FW restore手順
* Bridge update手順
* capture purge手順
* debug report作成手順

serviceは異常終了時にrestartする。

restart loopを避けるため、backoffを設ける。

Bridge service起動前にHermes起動を必須にするか、Hermesが後から起動してもreadyへ復帰できるようにする。

後者を推奨する。

────────────────────────────────────
25. 実装フェーズ
────────────────────────────────────

各フェーズ完了時に、`docs/progress.md`を更新する。

Phase 0：調査と現状確認

* workspace
* Git
* AGENTS.md
* connected hardware
* serial devices
* Hermes health
* Hermes capabilities
* upstream repos
* licenses
* toolchain
* external dependencies

成果物：

* `docs/upstream-baseline.md`
* `docs/requirements.md`
* `docs/architecture.md`
* ADR初版
* 実装計画

Phase 1：Repository scaffold

* uv project
* package layout
* docs
* protocol schemas
* config
* logging
* tests
* CI skeleton

Phase 2：ProtocolとSimulator

* Pydantic models
* JSON Schema
* Device Simulator
* Mock Hermes
* handshake
* heartbeat
* command round trip
* capture fixture

この段階では実機不要。

Phase 3：Bridge Device Gateway

* WebSocket
* auth
* registry
* commands
* Control API
* capture upload
* health
* metrics

Phase 4：FW control vertical slice

* official baseline
* custom component
* config
* Bridge connect
* hello
* heartbeat
* status
* head
* LED
* expression
* reconnect

この時点で初めて実機flashを検討する。

Phase 5：TTS固定音声

* Bridge固定WAV
* Opus encode
* FW receive
* decode
* speaker
* state
* cancel
* preroll
* gain

Phase 6：MicとSTT

* FW mic
* Opus encode
* Bridge decode
* VAD
* Mock STT
* faster-whisperまたはHTTP STT

Phase 7：Hermes Responses API

* health
* capabilities
* auth
* named conversation
* session key
* SSE parser
* text delta
* tool progress
* error handling

Phase 8：TTS streaming voice loop

* segmentation
* TTS adapter
* sequential playback
* full voice turn
* cancellation

Phase 9：MCP

* stdio server
* Control API client
* status
* body control
* photo
* disconnected errors
* Hermes config example

Phase 10：Camera and vision

* capture
* upload
* validation
* TTL
* input_image
* vision response
* MCP fallback

Phase 11：Hardening

* fault injection
* race conditions
* reconnect
* timeouts
* resource limits
* security
* privacy
* debug report
* latency report

Phase 12：Packaging and documentation

* launchd
* systemd
* release artifacts
* firmware binary
* checksum
* setup guide
* operations guide
* verification report
* traceability completion

各Phaseで、テスト失敗を残したまま次Phaseへ進まない。ただし、ハードウェアがないことだけを理由にhost側実装を止めない。

────────────────────────────────────
26. 完了報告
────────────────────────────────────

最終応答には、少なくとも次を含める。

1. 完成したもの
2. アーキテクチャ
3. 主要ファイル
4. upstream baseline
5. Protocol version
6. Bridge起動コマンド
7. FW buildコマンド
8. FW flashコマンド
9. Hermes設定例
10. MCP設定例
11. `scripts/verify.sh`の実行結果
12. Firmware build結果
13. Simulator E2E結果
14. 実機テスト結果
15. latency計測
16. security上の残存制約
17. 未完了項目
18. stop conditionにより未実施となった項目
19. Git status
20. commit hash
21. `docs/verification-report.md`の要点

「すべて完了した」「テストは通った」とだけ記述してはならない。

最終応答には、次のような具体的証拠を含める。

* 実行したコマンド
* exit code
* pass数
* firmware size
* Simulator E2Eの結果
* hardware scenarioのPASS／FAIL
* 接続ログの要点
* 画像認識結果の例
* voice turnの各処理時間

────────────────────────────────────
27. スコープ外
────────────────────────────────────

初期完成条件には含めない。

* 常時カメラ監視
* 動画ストリーミング
* 顔認識による本人特定
* LAN外公開
* Cloudflare relay
* Tailscale Funnel
* 複数拠点
* Fleet management
* 独自OTAサーバー
* Secure Boot
* Flash Encryption
* Firmware差分配信
* 全二重常時会話
* 高度なAEC
* 複数人話者分離
* 自律移動
* OpenClaw対応
* Home Assistant統合
* 外部クラウドSTT／TTSの必須化
* FWへのLLM実装
* Bridge内独自Memory
* Hermesのforkまたはpatch

ただし、後から追加できる拡張点は設計へ記録する。

────────────────────────────────────
28. 停止条件
────────────────────────────────────

次の場合だけ、作業を停止してユーザー判断を求める。

* 接続されたStackChanのhardware modelが想定と異なり、GPIOやservo制約を安全に決定できない。
* serial deviceが複数あり、対象を一意に判断できない。
* factory flash backupが取得できない、サイズ不正、またはSHA-256検証に失敗した。
* 実機flashによりSecure Boot、Flash Encryption、partition破壊の可能性がある。
* 公式FWまたはコピー対象コードのライセンス条件が不明で、合法的な再利用判断ができない。
* Hermes `/v1/capabilities`がResponses API非対応で、現在のHermes更新または設定変更が必要。
* Hermes API key、device token、Wi-Fi情報など、ユーザーしか提供できない秘密情報が必要。
* 既存未コミット変更と衝突し、安全に分離できない。
* 実機故障、servo異常、過熱、異臭、異常音、バッテリー膨張など物理的危険を検出した。
* 作業対象外の外部リポジトリ変更、権限昇格、OS設定変更が不可避。
* 重要なアーキテクチャ判断が、要件上どちらも同等でユーザー選択なしに決定できない。

停止する場合でも、停止地点までに可能なhost-side実装、Simulator、tests、docsを完成させる。

停止報告には必ず次を含める。

* 何が不足しているか
* なぜ自動判断できないか
* どこまで完了したか
* 影響範囲
* 選択肢
* 推奨案
* 再開後の最初のコマンド
* 未実施の受入条件

軽微な命名、ファイル配置、内部実装方式、テストライブラリ等については質問せず、合理的なdefaultを選びADRへ記録する。

outcome: 公式StackChan FWを基盤とする安全なカスタムFW、Python製Bridge、公開OpenAI Responses APIによるHermes接続、StackChan MCP、Device Simulator、テスト、運用設定、復旧手順、要求トレーサビリティを備え、音声一往復、身体制御、カメラ画像認識、再接続が実機または明示されたhardware stop conditionまで完成している。

verification: `scripts/verify.sh`がskipなしでexit code 0となり、Bridge unit／integration／Simulator E2Eが成功し、`idf.py build`が成功し、接続可能な実機がある場合はHW-01からHW-13の結果が`docs/hardware-test-report.md`へ記録され、要求から実装・テストまでの対応が`docs/traceability.md`で確認でき、最終応答に具体的なコマンド出力と検証証拠が提示されている。

constraints: Hermes Dashboard `/api/ws`、Hermes内部Python API、Hermesソースへのpatch、FWへのLLM／Hermes API key格納、音声のBase64 JSON化、常時カメラ送信、無検証の実機flash、未コミット変更の破壊、秘密情報のcommit、物理安全範囲外のservo動作を禁止し、公式upstreamとの差分と第三者ライセンスを追跡可能に保つ。

boundaries: 作業対象は現在の専用リポジトリまたは新規`stackchan-hermes-bridge/`配下、StackChan FW、Bridge、Protocol、Simulator、MCP、tests、docs、CI、launchd／systemd例に限定し、ユーザーのHermes本体、OS設定、無関係なリポジトリ、LAN外インフラは変更しない。

stop when: factory firmwareの検証済みbackupなしにflashが必要な場合、hardware modelまたはserial portが一意でない場合、物理安全を保証できない場合、必要な秘密情報や外部権限が不足する場合、Hermesの公開capabilitiesが必要機能を提供しない場合、ライセンス上の再利用可否を判断できない場合、または既存ユーザー変更を破壊せず作業継続できない場合に限り停止し、host-sideで完了可能な作業を済ませたうえで具体的な再開手順を提示する。

````

## `/goal` 設定後の確認

設定直後に、Completion Contractが意図どおり認識されたか確認する。

```text
/goal show
````

`Outcome`、`Verification`、`Constraints`、`Boundaries`、`Stop when blocked`が表示されること。

## Quality Gateの追加

Hermesが最初の数ターンで`scripts/verify.sh`を作成した後、次を追加する。

```text
/goal gate add ./scripts/verify.sh
```

Firmware環境を別コマンドで検証する構成になった場合は、さらに追加する。

```text
/goal gate add ./scripts/verify-firmware.sh
```

Gate追加後は次で確認する。

```text
/goal gate list
```

実機検証はデバイス接続状態に左右されるため、通常のQuality Gateには含めず、`docs/hardware-test-report.md`と最終Completion Contractで判定する。
