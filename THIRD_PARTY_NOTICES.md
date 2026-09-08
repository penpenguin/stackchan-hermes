# Third-party notices

確認日: 2026-09-08。独自コードと文書には [MIT License](LICENSE) を適用します。
以下の第三者コード・依存物・参照実装には、それぞれの元のライセンスが適用されます。
この一覧は来歴と確認状況の記録であり、各ライセンス全文の代わりや、配布物全体の
監査完了を示すものではありません。対象別の配布条件と確認結果は
[ライセンスと配布の整理](docs/licensing.md) と [監査記録](docs/license-audit.md) を参照してください。
回収した著作権表示・ライセンス全文・NOTICE は [LICENSES](LICENSES/README.md) に同梱しています。

公式 StackChan Firmware は、ライセンス確認後に固定 commit から vendor snapshot として
取り込みました。取得型の Git/ESP-IDF dependencies は Git 管理外ですが、ref・content hash・
reviewed patch を lock し、build 前に検証します。参照だけの実装からコードはコピーして
いません。将来別のコードや asset を取り込む場合は、対象 commit/file、著作権表示、
ライセンス全文、変更内容を追記します。

## Firmware に取り込んだコード・取得型依存

| Project | Pinned reference | License finding | Current use |
| --- | --- | --- | --- |
| `m5stack/StackChan` | `1b5765599fba8aaad1811d9a79358ccc7051f5f3` | [MIT](firmware/LICENSE), Copyright 2026 M5Stack Technology CO LTD | Reviewed Firmware vendor snapshot and board/HAL baseline; project changes are isolated and tracked |
| `FTServo_Arduino` | 上記 snapshot 内 | [MIT](firmware/main/hal/drivers/FTServo_Arduino/LICENSE), Copyright 2024 ftservo | 取り込み済みのサーボドライバー。参照実装の旧 GPL SCServo とは別の対象 |
| Bosch BMI270 SensorAPI | 上記 snapshot 内 | [BSD-3-Clause](firmware/main/hal/drivers/bmi270/BMI270_SensorAPI/LICENSE), Copyright 2023 Bosch Sensortec GmbH | 取り込み済みのセンサードライバー |
| ESP-IDF | `v5.5.4` | [Apache-2.0 とコンポーネント固有の条件](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/COPYRIGHT.html) | 必須 SDK。SDK 内の全ファイルに同一ライセンスが適用されるわけではない |
| `espressif/mdns` | `1.11.3` in `firmware/dependencies.lock` | Apache-2.0（既存調査記録） | Official managed component used by Firmware Bridge discovery; fetched source is not tracked |
| `78/esp-ml307` | `3.6.5` / `ab4de7c28c8b8f809eba2f56f38090d57fce984d` in `firmware/dependencies.lock` | [Apache-2.0 の保存済み全文](firmware/components/stackchan_bridge_client/third_party/esp-ml307-LICENSE) | `web_socket.cc` とネットワーク factory を build 時に変更表示付きの派生ファイルで置換。HTTP/TCP/TLS/WebSocket を残し、MQTT・汎用 UDP・携帯モデムを除外 |

取得型 Git 依存6件の commit・ライセンス記録は
[upstream-lock.json](firmware/upstream-lock.json)、その概要は
[Firmware 依存一覧](docs/dependencies.md#firmware-source-dependencies) にあります。
managed components 60件と ESP-IDF の版は [dependencies.lock](firmware/dependencies.lock)
に固定されています。60件の実ファイルを lock の content hash と照合し、全件の通知を
保存しました。Git 依存6件の固定 commit の全文も保存しています。
[全件一覧](docs/license-inventory/firmware.md) と [監査記録](docs/license-audit.md) を参照してください。
不足していた3件の通知を補い、許諾未確認の旧字形を固定版 Noto / Material Icons へ置換しました。
Montserrat も固定入力から再生成し、[フォント固有の条件・帰属](LICENSES/README.md#素材の帰属表示)
を保持します。実際の CoreS3 ビルドの SDK・モデル・archive・assets も確認しています。

2026-09-08 のローカル CFW 化では、Xiaozhi の MIT 共有処理から旧クラウド依存を除去し、
[固定パッチ](firmware/patches/xiaozhi-esp32.patch) と [Git 記録](LICENSES/firmware-git.json)
を更新しました。`78/esp-wifi-connect@3.1.2` の MIT 設定コード・画面から OTA 設定を除去する
[パッチ](firmware/patches/esp-wifi-connect.patch) と入力・出力 hash も記録しています。
既存の MIT 補完根拠は [managed 記録](LICENSES/firmware-managed.json) に保持します。
旧アプリ素材4件と不要なリンク archive 17件を除外し、新たな依存・ライセンスは追加していません。

## 参照実装・外部の Hermes

ここでの「参照のみ」は既存の取り込み記録に基づきます。新しくコードを取り込むときは、
対象 commit とファイルの条件を確認します。

| Project | Pinned reference | License finding | Current use |
| --- | --- | --- | --- |
| `m5stack/StackChan-BSP` | `621602709d8206edfbf032539dddc6506363836a` | MIT | Official BSP reference; not imported |
| `kisaragi-mochi/stackchan-mcp` | `558cf404dcd215993d5af9a4495fd34339b6c314` | Repository/gateway MIT; its optional legacy SCServo files are GPL-3.0 | Behavioral and failure-mode reference only |
| `circlemouth/Hermes-StackChan` | `66f03b734fb7434283a79f5409761993751a7676` | Firmware has MIT license, but no top-level license was found for the complete repository/`ai-server` | Behavioral reference only; do not copy code until clarified |
| `NousResearch/hermes-agent` | `4e7eb39947f132f961923f9e3f600bc8e63066dd` | [MIT](https://raw.githubusercontent.com/NousResearch/hermes-agent/4e7eb39947f132f961923f9e3f600bc8e63066dd/LICENSE) | 公開 API で接続する別プロセス。Bridge へのコード取り込みなし |

固定版の調査経緯は [upstream baseline](docs/upstream-baseline.md#license-findings) を参照してください。

## Python の直接依存

[pyproject.toml](pyproject.toml) の通常の直接依存17件について、導入済み distribution の
`METADATA` の `License-Expression` / `License` と、[uv.lock](uv.lock) の版を照合しました。
全17件の導入版が lock と一致しています。下表はパッケージの宣言であり、推移依存や
wheel 内のネイティブライブラリを含む完全なライセンス判定ではありません。
`AND` は複数条件の併存を表すため、単一の MIT / BSD 表記にまとめません。

| Package | Locked / installed | 宣言されたライセンス | 補足 |
| --- | --- | --- | --- |
| fastapi | 0.141.1 | MIT | |
| httpx | 0.28.1 | BSD-3-Clause | |
| ifaddr | 0.2.0 | MIT | |
| mcp | 2.1.1 | MIT | [固定版の LICENSE](https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/v2.1.1/LICENSE) |
| numpy | 2.5.2 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 配布する wheel 内の数値計算ライブラリ等も個別確認 |
| opuslib-next | 1.3.1 | BSD-3-Clause | libopus の ctypes binding。libopus 本体の条件も適用 |
| pillow | 12.3.0 | MIT-CMU | 通常の MIT と区別する。導入物の LICENSE には AOM / Brotli などの通知も含まれる |
| platformdirs | 4.11.5 | MIT | |
| prometheus-client | 0.26.0 | Apache-2.0 AND BSD-2-Clause | NOTICE に同梱 decorator 4.0.10 の BSD 通知あり |
| pydantic | 2.13.4 | MIT | |
| pydantic-settings | 2.15.0 | MIT | |
| python-multipart | 0.0.32 | Apache-2.0 | |
| soundfile | 0.14.0 | BSD-3-Clause | Python 部分の宣言。libsndfile 本体は LGPL |
| typer | 0.27.1 | MIT | |
| uvicorn | 0.52.4 | BSD-3-Clause | `standard` extra の推移依存は別途確認 |
| websockets | 17.1 | BSD-3-Clause | |
| zeroconf | 0.150.0 | LGPL-2.1-or-later | [固定版の COPYING](https://raw.githubusercontent.com/python-zeroconf/python-zeroconf/0.150.0/COPYING)。通常の直接依存に含まれる |

MCP の推移依存 `mcp-types==2.1.1` も、導入物の `METADATA` で MIT と確認しました。
推移・任意・開発依存を含む lock の第三者104件は [全件一覧](docs/license-inventory/python.md)
と [通知集](LICENSES/README.md) に記録しました。lock 外の build ツール一式や、
全プラットフォームの native binary の配布条件を確認したものではありません。

任意の `stt-local` extra の `faster-whisper==1.2.1` は、
[固定タグの LICENSE](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/v1.2.1/LICENSE)
で MIT と確認しました。この確認環境には未導入です。追加で取得する Python / native 依存や
音声認識モデルの条件は、このパッケージ本体のライセンスと別に確認します。

### 宣言の再確認

通常の依存を導入済みのリポジトリルートで、次のように個別の宣言を読み取れます。
このコマンドは依存を同期せず、パッケージ本体も import しません。出力した版を `uv.lock`
と照合してください。`License-File` の対象は distribution の `.dist-info/` または
その `licenses/` 以下などにあり、配布物から著作権表示・全文・NOTICE を回収します。

```bash
uv run --locked --no-sync python - <<'PY'
from importlib.metadata import distribution

for name in ("mcp", "numpy", "prometheus-client", "soundfile", "zeroconf"):
    package = distribution(name)
    metadata = package.metadata
    print(name, package.version)
    print(metadata.get("License-Expression") or metadata.get("License"))
    print(metadata.get_all("License-File", []))
PY
```

## ネイティブライブラリ・外部サービス・素材

| 対象 | 確認した条件・記録 | 配布時の確認対象 |
| --- | --- | --- |
| libopus | 既存調査では BSD-3-Clause と Xiph notice。システムライブラリを利用し、リポジトリにバイナリを同梱していない | 配布環境での実際の版と通知 |
| libsndfile | [LGPL。公式説明は 2.1 / 3 の選択に言及](https://libsndfile.github.io/libsndfile/#licensing) | soundfile の binary wheel に含まれることがある。この環境でも `_soundfile_data/COPYING` を確認。実際に同梱する版のライセンス・ソース提供方法 |
| FFmpeg | [基本は LGPL-2.1 以降。GPL 部分を有効にすると FFmpeg 全体に GPL が適用](https://ffmpeg.org/legal.html) | 実際のバイナリの build configuration、外部 codec、対応ソース。配布するバイナリの条件は未確定 |
| VOICEVOX / Irodori 等の外部 STT/TTS | HTTP 接続先として設定。今回の一覧ではサービス本体・モデル・音声の規約は未監査 | 実際に採用・同梱するエンジン、モデル、声、生成物の利用・表示条件 |
| Firmware の UI・フォント・効果音等 | [素材の帰属表示・全文](LICENSES/README.md#素材の帰属表示) を保存。旧字形を再配布可能な固定入力からの生成物へ置換 | [実ビルドと配布物の確認結果](docs/license-audit.md) |

公開する source archive、Python distribution、container、Firmware binary ごとに、含まれる
依存物と通知を確認します。Python wheel / sdist の通知集は同梱確認済みです。
CoreS3 Firmware ZIP も、実物の照合と通知集の同梱を行います。作成手順と、将来依存実行環境を
同梱する場合の確認範囲は [監査記録](docs/license-audit.md) にあります。

Camera reliability derivatives of `78/esp-ml307` 3.6.5 (Apache-2.0) and
`espressif/esp_video` 1.3.1 (ESPRESSIF MIT; use on Espressif products) are recorded in
[the camera manifest](firmware/patches/camera-derivatives.json) and
[the managed-component inventory](LICENSES/firmware-managed.json). Original and derivative
hashes are checked during configuration and against release compilation inputs. The managed
component cache remains unchanged; retained license texts are listed in the inventory.
