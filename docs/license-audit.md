# 配布物のライセンス確認記録

確認日: 2026-09-07。独自部分は [MIT](../LICENSE) です。
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
| SDK / ランタイム | ESP-IDF v5.5.4 の固定 commit、個別通知、コンパイルした SDK ソース1,013件の先頭通知、実際に選択された archive 136件を記録 |
| Firmware の実物 | app / bootloader の map、assets 42件、WakeNet モデル3ファイル、配布する5画像を検証。[構成・ハッシュ](license-inventory/cores3-release.json) |

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

[SDK 記録](../LICENSES/firmware-sdk.json) に個別通知46件と archive 136件を保存しました。
ESP-IDF のルートライセンスだけでなく、Wi-Fi / Bluetooth / PHY、Xtensa libhal、
newlib、GCC / libstdc++ の条件を含みます。GCC / libstdc++ は GPL-3.0 と
GCC Runtime Library Exception 3.1 を保持します。通常の GCC による今回の結合は
ランタイム例外を使います。[GCC の公式説明](https://gcc.gnu.org/onlinedocs/libstdc++/manual/license.html)
にある対象条件を、独立したプロジェクトコードと開発ツール本体の再配布から区別しています。

assets パーティションを展開し、新しい文字フォント、Twemoji 21枚、M5Stack 素材18件、
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

検証器は、旧字形の混入、生成物・通知の hash、依存の固定版、SDK、実際に選択された
archive、assets とモデルのバイト列、配布画像の一覧を照合します。ZIP には app、
bootloader、partition table、初期 OTA データ、assets の5画像と通知を収録します。
端末の NVS や backup は収録しません。`release-manifest.json` に offset・サイズ・SHA-256
と実物の構成を記録します。通常の `verify-firmware.sh` でも同じ検証器が走ります。

Python 配布物は `uv build` で作ります。最低対応 Hatchling 1.27.0 でも実物を作り、
MIT メタデータ・通知のバイト列、sdist の収録範囲と wheel への再ビルドを確認します。
ソースリポジトリの配布では Git 管理対象と今回の生成フォント・通知を含め、
Git 管理外の取得済み依存・ローカル設定を追加しないでください。

## 検証記録

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
