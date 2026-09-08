# CFW の通信先とローカル運用

CFW は表情表示、BLE、ESP-NOW、ダンス、Wi-Fi 設定、音声再生、カメラ撮影、
Hermes Bridge 連携を提供します。従来の AI.Agent、EzData、アカウント連携、App Center、
クラウド Avatar・通話、画像認識サーバーへのアップロード、OTA 更新は削除しました。
ファームウェアと assets の更新には USB を使います。

## 接続先

| 通信 | 許可する宛先・動作 |
| --- | --- |
| Bridge の明示設定 | USB 設定の `bridge.url`、`bridge.fallback_url`、ビルド時の `CONFIG_STACKCHAN_HERMES_DEFAULT_BRIDGE_URL`。外部ホストも指定可能。既定値は空 |
| mDNS 自動検出 | protocol v1・認証必須の広告のうち RFC1918 プライベート IPv4 と IPv4 リンクローカル。外部・loopback・multicast・prefix 境界と、受信インターフェースの subnet network/broadcast は拒否 |
| 音声・画像・端末情報 | 選択済み Bridge のみ。画像の HTTP(S) URL は WebSocket URL と同じホスト・ポートから導出。応答本文や `Location` で宛先を変更しない |
| PC 側の会話・STT・TTS | 設定済み Hermes 公開 HTTP API、STT、TTS。各リクエストでリダイレクト非追従を強制。VOICEVOX の query と synthesis、Hermes の readiness も対象 |
| 通常のネットワーク処理 | DNS、DHCP、時刻同期、ローカル Wi-Fi 設定、BLE、ESP-NOW |
| 取得 | 依存・モデルなどの取得。音声・画像・端末固有情報を取得要求へ付加しない |

選択順は明示 URL → mDNS → 明示フォールバック URL → ビルド時 URL です。
mDNS に候補がなければ明示フォールバックを使い、それもなければ未接続のまま再検出します。
明示 URL が不正な場合は設定エラーにします。接続失敗から従来クラウドへ切り替える経路は
ありません。Bridge プロトコル v1 と USB コマンドは維持します。

## 初回設定と再起動

本体の初回案内、または SETUP → Wi-Fi → Change Wi-Fi を開きます。
表示されたホットスポットへ接続し、表示されたローカル URL をブラウザーで開いて Wi-Fi を
設定します。公式クラウド登録やスマートフォンアプリは不要です。画面の Done で戻れます。
初回画面の Skip、Done、画面のキャンセルで設定用 AP を停止します。保存済み Wi-Fi があれば STA 接続へ
戻し、接続待ちや接続済みの状態は保持します。終了後は接続タイムアウトでも AP を再開せず、
Wi-Fi 設定画面を明示的に開き直すと再び設定できます。
Bridge は [既存の USB 手順](../README.md#6-firmware-を準備して-stackchan-を接続する) で設定します。
Wi-Fi や Bridge が未設定・未接続でもランチャーとローカルアプリを利用できます。

省電力と Idle Movement は SETUP → Device に移しました。省電力は充電状態と本体タッチ・
音声処理に加え、BLE から適用した表情・首・RGB 操作と、自端末宛てまたは broadcast の
ESP-NOW 操作を活動として扱います。不正 JSON、操作を含まないデータ、短い ESP-NOW
パケット、他端末宛てのパケットではアイドル時間を更新しません。従来 AI アプリや
ネットワーク接続は必要ありません。
Idle Movement の画面と USB 設定は `motion.idle_level` を共通で使用します。
このキーが未保存の場合は旧 `xiaozhi.idle_lv` を引き継ぎ、画面からの保存時には両方を更新します。
シャッター音・通知音は HAL が所有する音声サービスとメインループのローカル処理で再生します。

保存済み Wi-Fi・Bridge 設定は保持します。旧 `xiaozhi` namespace から読むのは
`idle_sec`、`ext_pwr`、`idle_lv` の端末設定だけです。`boot_ai`、OTA URL、クラウド接続設定は
読みません。新しい初回案内の完了状態は `device.setup_done` に保存します。
再起動時のランチャー選択位置は `warm_boot.app_name` に保存し、インストールされたアプリ名と
照合します。旧 `app_index` や未知の名前からアプリを起動・選択することはありません。

ESPNOW.REMOTE は Wi-Fi Manager の初期化済みドライバを再利用します。起動時に通常の
Wi-Fi 接続・設定用 AP・再接続タイマーを停止し、選択した ESP-NOW チャンネルを使います。
この間 Bridge は未接続になり、アプリ終了時の再起動で通常の Wi-Fi 接続へ戻ります。
保存済み Wi-Fi・Bridge 設定は保持されます。

USB 更新時の既存 partition layout と `ota_data_initial.bin` は互換性のため保持します。
起動イメージに旧版からの移行時の `PENDING_VERIFY` が残っている場合は、ローカルの初期化が
成功してからアプリの操作を受け付ける前に一度だけ確定します。この処理は端末内の起動状態を
更新するだけで、Wi-Fi・Bridge 接続を必要としません。確定失敗はログへ記録し、保留状態を維持します。
ネットワーク OTA 更新機能は含まれません。実機操作の条件は
[hardware-setup](hardware-setup.md) を参照してください。

## 検証の範囲

`./scripts/verify.sh` は C++、Host の回帰テストと ESP-IDF ビルド、配布物検証を実行します。
配布物検証では compile commands、ELF シンボルと旧設定文字列を検査します。
Xiaozhi の変更は [固定パッチ](../firmware/patches/xiaozhi-esp32.patch) と
[lock](../firmware/upstream-lock.json) に記録します。Wi-Fi 設定画面の OTA 項目除去は
[パッチ](../firmware/patches/esp-wifi-connect.patch) と
[入力・出力ハッシュ](../firmware/patches/esp-wifi-connect.json) で検証し、managed cache を
変更せずビルドディレクトリへ適用します。共通ネットワーク部品の MQTT・汎用 UDP・
携帯モデムもコンパイル対象から除外し、Bridge 用 HTTP/TCP/TLS/WebSocket だけを選択します。
SDK の DNS・DHCP・SNTP 用ネットワーク処理は保持します。

偽の通信先によるテストでは、画像・音声・認証情報の送信先と HTTP 301/302/303/307/308 の
非追従を確認します。これはソース・ビルドとホスト上の検証です。この変更で実機への書き込み、
画面操作・音声・撮影・省電力の実機確認、パケットキャプチャによる送信先観測は行っていません。
