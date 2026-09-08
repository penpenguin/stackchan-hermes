# 配布物のライセンス確認記録

確認日: 2026-09-08。独自部分は [MIT](../LICENSE) です。
ソース、第三者パッケージ本体を含めない Python wheel / sdist、M5Stack CoreS3
（ESP32-S3）向け Firmware ZIP を対象に、発見したフォント・通知・最終構成の問題を
解消しました。配布時は `LICENSE`、`THIRD_PARTY_NOTICES.md`、`LICENSES/` を保持します。
実機への書き込みや表示・音声・サーボの実機動作確認は今回の検証に含みません。

## 確認した配布範囲

| 対象 | 実施したこと |
| --- | --- |
| Python の依存104件 | `uv.lock` の版と宣言を照合し、著作権表示・全文・NOTICE を保存。[一覧](license-inventory/python.md) |
| Python wheel / sdist | MIT メタデータと通知を同梱。第三者パッケージ本体、Firmware、ローカル環境を収録しない。sdist からの再ビルドも検証 |
| Firmware 依存 | managed components 60件の content hash、Git 依存6件の固定 commit / 既存パッチを照合。全件の通知を保存。[一覧](license-inventory/firmware.md) |
| フォント | 取得元・版・許諾の明らかな入力から文字9,561字・アイコン135個・見出しを生成。旧字形のコンパイルと収録を禁止 |
| SDK / ランタイム | ESP-IDF v5.5.4 の固定 commit、個別通知、従来監査の SDK ソース1,013件の先頭通知を保持し、ローカル CFW で選択された archive 119件を記録 |
| Firmware の実物 | app / bootloader の map、assets 38件、WakeNet モデル3ファイル、配布する5画像を検証。[構成・ハッシュ](license-inventory/cores3-release.json) |

2026-09-08 の更新では、従来クラウド・OTA の削除によりリンク archive が136件から119件へ、
assets が42件から38件へ減りました。新たな archive はなく、残る prebuilt archive の hash は
元の監査と一致します。元の通知・著作権表示は保守的に保持します。Xiaozhi の MIT パッチと
Wi-Fi 設定の MIT 派生ファイルは、入力・変更・出力を追跡できる形で配布物に収録します。
通信先と実機検証の範囲は [network-policy](network-policy.md) を参照してください。

## 解消した問題

### 字形の置換と再生成

元の `78/xiaozhi-fonts@1.6.0` には、入力の版や公開再配布の許諾を確認できない
Font Awesome / Puhui / 複数ファミリーを結合した Noto の字形がありました。
[ビルドの選択処理](../firmware/cmake/release_fonts.cmake) でそれらの C データを除外し、
assets 用 cbin も確認した入力から生成したものだけを使います。ヘルパーコードと
CC-BY-4.0 の Twemoji は保持します。依存自体の lock と content hash は変更しません。

文字は Noto Sans CJK JP・Sans・Thai・Math（OFL-1.1）、アイコンは Material Icons
（Apache-2.0）、見出しは固定版 Montserrat SemiBold（OFL-1.1）から生成しました。
入力 URL・commit・SHA-256、完全な著作権表示、生成結果を
[フォント記録](../LICENSES/firmware-fonts.json) に保存しています。
OFL の許諾・免責と名称に関する条件を保持し、生成物は StackChan Text / Icons / UI と呼びます。

既存の文字コード135個への対応を維持し、Wi-Fi の4状態と電池の6状態を区別します。
日本語の JIS X 0208 と従来の Latin / Thai 等の文字範囲を収録しています。字形と一部の
アイコンの見た目は変わります。assets 用文字フォントは変換器の制限に対応するため
ペアカーニングを無効にし、文字の送り幅を保持しました。
[生成仕様・再生成手順](../firmware/release-fonts/README.md) を参照してください。

### 3コンポーネントの通知補完

| 固定 component | 根拠と対応 |
| --- | --- |
| `78/esp-wifi-connect@3.1.2` | 固定版 manifest の MIT 宣言に、upstream が後日追加した MIT 全文・Copyright (c) 2024 Terrence を補完。取得 commit を明記し、固定版に元から LICENSE があったとは扱わない |
| `78/uart-uhci@0.2.1` | 固定版 manifest・README・公式 registry の Apache-2.0 宣言を確認。標準全文と元の宣言を保存。確認した package には別の NOTICE・著作権表示なし |
| `78/xiaozhi-fonts@1.6.0` | 固定版 manifest・公式 registry の MIT 宣言に基づき、残すヘルパーの許諾文・免責文と宣言を保存。提供されていない著作権者・年は創作しない。字形は別の条件で置換し、Twemoji の帰属も保持 |

取得根拠と原文は [managed 記録](../LICENSES/firmware-managed.json) にあります。
Wi-Fi の補完は [upstream の LICENSE 追加](https://github.com/78/esp-wifi-connect/commit/347682fa013b52f863052ad4b1a793ca3cabff17)、
UART とフォントの宣言はそれぞれ
[0.2.1 の README](https://components.espressif.com/components/78/uart-uhci/versions/0.2.1/readme)、
[1.6.0 の registry](https://components.espressif.com/components/78/xiaozhi-fonts/versions/1.6.0/readme)
で確認しました。単なる LICENSE ファイルの欠落と、許諾そのものの未確認を区別しています。

`espressif/dl_fft@0.3.1` は固定 repository の MIT と、ソースに表示された Apache-2.0 の
両方の全文・元の表示を保持しました。

### 実際にリンク・収録された内容

[SDK 記録](../LICENSES/firmware-sdk.json) に個別通知46件と archive 119件を保存しました。
ESP-IDF のルートライセンスだけでなく、Wi-Fi / Bluetooth / PHY、Xtensa libhal、
newlib、GCC / libstdc++ の条件を含みます。GCC / libstdc++ は GPL-3.0 と
GCC Runtime Library Exception 3.1 を保持します。通常の GCC による今回の結合は
ランタイム例外を使います。[GCC の公式説明](https://gcc.gnu.org/onlinedocs/libstdc++/manual/license.html)
にある対象条件を、独立したプロジェクトコードと開発ツール本体の再配布から区別しています。

assets パーティションを展開し、新しい文字フォント、Twemoji 21枚、M5Stack 素材14件、
index、WakeNet モデルを確認しました。モデルの3ファイルは固定 `esp-sr@2.3.1` の
`wn9_histackchan_tts3` と一致します。画像・効果音は固定 M5Stack snapshot の MIT 通知を、
Twemoji は Twitter / contributors の帰属と CC-BY-4.0 を保持します。

`esp-sr`、audio codec / effects、image effects、new JPEG、video 等には Espressif 製品での
利用条件があります。今回の ESP32-S3 向け配布ではその条件と全文を保持します。
他社チップ向けに条件を広げた配布を認めるものではありません。

## 配布物の作成と検証

ESP-IDF v5.5.4 を有効にし、リポジトリルートで実行します。依存は既存のセットアップ
手順どおりに固定版を取得します。ビルド専用ディレクトリを新規に作り、個人用 sdkconfig
を流用しない構成です。

```bash
./scripts/verify.sh
release_dir="$(mktemp -d /tmp/stackchan-release.XXXXXX)"
idf.py -C firmware -B "$release_dir/build" \
  -D SDKCONFIG="$release_dir/sdkconfig" \
  -D SDKCONFIG_DEFAULTS="$PWD/firmware/sdkconfig.defaults;$PWD/firmware/sdkconfig.hermes.defaults" build
python3 firmware/tools/verify_release.py "$release_dir/build" \
  --output .local/releases/stackchan-hermes-cores3.zip
```

検証器は、旧クラウド送信ソース・ELF シンボル・設定文字列の混入、Wi-Fi パッチの出力、
旧字形の混入、生成物・通知の hash、依存の固定版、SDK、実際に選択された
archive、assets とモデルのバイト列、配布画像の一覧を照合します。ZIP には app、
bootloader、partition table、初期 OTA データ、assets の5画像と通知を収録します。
端末の NVS や backup は収録しません。`release-manifest.json` に offset・サイズ・SHA-256
と実物の構成を記録します。Xiaozhi / Wi-Fi の変更パッチと hash の記録も同梱します。通常の `verify-firmware.sh` でも同じ検証器が走ります。

Python 配布物は `uv build` で作ります。最低対応 Hatchling 1.27.0 でも実物を作り、
MIT メタデータ・通知のバイト列、sdist の収録範囲と wheel への再ビルドを確認します。
ソースリポジトリの配布では Git 管理対象と今回の生成フォント・通知を含め、
Git 管理外の取得済み依存・ローカル設定を追加しないでください。

## 2026-09-08 のローカル CFW 検証記録

- `./scripts/verify.sh`: 成功。Host の pytest 707件、coverage 87.91%、C++ 28件、
  新規構成の ESP-IDF ビルドと配布物検証が通過。整形・静的解析・型・Protocol・秘密情報・
  依存脆弱性・offline doctor の検査も成功。新規構成の app は3,368,592 bytes。
  以下の配布記録は別の検証済みビルドを指し、個々のバイナリ hash を区別する。
- CoreS3 の実ビルドと配布検証: 成功。app 3,368,576 bytes、assets 2,616,159 bytes。
- 配布構成: assets 38件、モデル3ファイル、archive 119件、画像5件。個別 hash は
  [実物の記録](license-inventory/cores3-release.json) に保存。
- 旧クラウド・MQTT 送信実装のソース選択と ELF シンボル、旧設定文字列の除外を確認。
  managed cache は変更せず、Wi-Fi 派生ファイルの入力・出力 hash を照合。
- C++ 28テストにより、ローカル自動検出・外部広告拒否・明示外部 URL・未接続と接続失敗、
  ローカル省電力・復帰位置・効果音タスク、画像転送の宛先とリダイレクト非追従を確認。
- 公開するバイナリ・archive・パッチ・ソースの SHA-256 による秘密情報誤検出193件は、
  値と保存行を個別照合して baseline に追加。検出ルールと除外範囲は維持。
- 実機 flash、画面・音声・撮影・省電力の実機操作、パケットキャプチャ: 未実施。

### 初回設定・ローカル操作の追加修正

初回 Wi-Fi 設定後の ESP-NOW は Wi-Fi Manager の初期化済みドライバを再利用し、
設定用 AP・通常接続・接続タイマーを停止して指定チャンネルへ切り替えます。
BLE の適用済み操作と宛先の一致する ESP-NOW 操作でアイドル時間を更新します。
不正・未完成の操作や他端末宛てのパケットは活動として扱いません。

追加修正後の `./scripts/verify.sh` は Host 709件、C++ 30件、新規 ESP-IDF ビルド、
配布物検証まで成功しました。新規構成の app は3,367,424 bytes、配布構成は引き続き
assets 38件・モデル3ファイル・archive 119件・画像5件です。
前項の初回ビルド記録と区別し、各 ZIP の正確な画像情報は `release-manifest.json` を参照します。
実機への書き込み・初回設定操作・無線操作中の省電力確認は未実施です。

## 2026-09-07 の初回配布監査記録

- 置換フォント、配布検証器、関連する既存契約のテスト: 68件成功。
- CoreS3 の実ビルド: 成功。app 3,808,848 bytes、assets 2,899,513 bytes。
- 実ビルドの配布検証: assets 42件、モデル3ファイル、archive 136件、画像5件で成功。
- `./scripts/verify.sh`: 成功。Host の pytest 618件、coverage 87.66%、Firmware CTest
  26件、ESP-IDF の新規構成ビルドと配布検証が成功。整形・静的解析・型・Protocol・秘密情報・
  依存脆弱性チェックも通過。既存 upstream の非推奨 API 等の警告は残る。
- Python wheel / sdist: 通知252ファイルの宣言・収録バイト列と sdist からの再ビルドを確認。
- JSON の lock・全文243ファイルの SHA-256、文書の相対リンク、`git diff --check`: 成功。
- 秘密情報の誤検出は公開 checksum / commit と既存 vendor 通知のパスを個別確認して
  baseline に登録。検出ルール・除外範囲と、元の44件の記録は維持。
- 実機 flash・新しい字形の実機表示・音声やサーボの実機動作確認: 未実施。

## 配布方式を変更するとき

Python の通知一覧は通常・任意 `stt-local`・開発依存と OS marker の分岐を含みますが、
すべての OS の wheel や今後取得するモデルを監査したものではありません。
現在の Python 配布物は依存を `Requires-Dist` で宣言し、利用者が取得します。

container / インストーラー / Python 実行環境一式は今回作成していません。
将来これらを配布する場合は、実際に含める zeroconf / libsndfile / FFmpeg 等の
LGPL の対応ソース・差し替え要件、MPL 対象ファイルのソース提供、OS ライブラリ・
外部 STT/TTS・追加モデルの条件を、その配布方式で確認します。
依存の版、フォント、対象チップ、配布方式を変えたら本記録と全文を更新して再検証します。
