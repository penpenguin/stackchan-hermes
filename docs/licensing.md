# ライセンスと配布の整理

確認日: 2026-09-07。

## 現在の状態

2026-09-07 に、独自コードと文書へ [MIT License](../LICENSE) を採用しました。
著作権者の表示は `Copyright (c) 2026 stackchan-hermes contributors` です。
MIT の著作権表示と許諾文を保持する条件で、利用・改変・再配布・販売を認めます。

取り込んだ第三者のコードには、それぞれの元のライセンスが適用されます。
[firmware/LICENSE](../firmware/LICENSE) は公式 M5Stack snapshot の MIT 通知を保存したものです。
Bridge / Simulator / MCP、独自に作成した Firmware の追加実装、文書に MIT を適用します。
第三者コード由来の変更・派生ファイルや第三者由来の素材は、元の条件を保持します。
素材に許諾の表示が見つからない場合も、独自部分の MIT で補えるわけではありません。

| 対象 | 現状 | 根拠 |
| --- | --- | --- |
| 独自コード・文書の配布許諾 | MIT を採用済み | [LICENSE](../LICENSE) |
| 取り込んだ Firmware の来歴 | 固定 commit と通知を保存済み | [UPSTREAM.md](../firmware/UPSTREAM.md)、[第三者通知](../THIRD_PARTY_NOTICES.md#firmware-に取り込んだコード取得型依存) |
| Python の通常の直接依存17件 | 導入版と lock の一致、ライセンス宣言を確認済み | [Python の直接依存](../THIRD_PARTY_NOTICES.md#python-の直接依存) |
| Python の推移・任意・開発依存104件 | 版・宣言・通知を収集済み。native binary の全件判定とは区別 | [Python 一覧](license-inventory/python.md) |
| Python wheel / sdist | MIT メタデータと通知集の同梱、収録範囲を確認 | [監査記録](license-audit.md) |
| Firmware の依存66件 | managed 60件と Git 6件の固定版・通知を確認。旧字形を置換し、CoreS3 の実ビルドと配布 ZIP を検証 | [Firmware 一覧](license-inventory/firmware.md) |

MCP SDK 本体は MIT ですが、MCP server ごとに実装と依存物の条件を確認します。
このプロジェクトで作った `stackchan-mcp` の公開条件は、上記の独自部分に含まれます。

## ライセンス別に確認すること

以下は配布準備の要点です。実際の対象ファイルと配布形態に適用される全文を確認します。

| ライセンス | 主な対象 | 配布準備の要点 |
| --- | --- | --- |
| MIT | 公式 Firmware、FTServo、MCP SDK など | 著作権表示と許諾文を保持する。商用利用・改変・再配布を許可する条件で、ソース公開を要求する条項はない。[原文](https://opensource.org/license/mit) |
| BSD-3-Clause | BMI270 SensorAPI、httpx、soundfile の Python 部分など | 著作権表示・条件・免責を保持し、バイナリ配布では同梱文書等に掲載する。著作権者・貢献者名による無断の推奨表示をしない。[原文](https://opensource.org/license/bsd-3-clause) |
| Apache-2.0 | ESP-IDF の該当部分、esp-ml307 など | 全文を同梱し、変更したファイルに変更表示を付け、該当する著作権表示・NOTICE を保持する。特許許諾とその終了条件もある。[原文](https://www.apache.org/licenses/LICENSE-2.0) |
| LGPL-2.1-or-later 等 | zeroconf、libsndfile、構成によって FFmpeg | ライセンス・利用通知、該当ライブラリの対応ソースの提供、利用者による変更版への差し替え・再リンクなど、配布形態に合う方法を確認する。リンク方式によって要件が変わる。[LGPL 2.1 原文](https://raw.githubusercontent.com/python-zeroconf/python-zeroconf/0.150.0/COPYING) |
| MIT-CMU / 複数ライセンス | Pillow、NumPy、prometheus-client など | パッケージの短い分類だけで判断せず、同梱コードと native library の通知を含めて確認する。[確認記録](../THIRD_PARTY_NOTICES.md#python-の直接依存) |

`zeroconf` は通常の依存に含まれます。また、soundfile の Python 部分は BSD でも、
同梱・ロードする libsndfile は LGPL です。FFmpeg の条件はビルド構成で変わります。
実行環境を丸ごと container やインストーラーに入れる場合も、含めた依存物を確認対象にします。

参照元 `kisaragi-mochi/stackchan-mcp` の旧 SCServo には GPL-3.0 の記録がありますが、
既存調査ではそのコードは取り込んでいません。現在取り込み済みの `FTServo_Arduino` は
MIT です。これだけで全依存物に GPL 部分がないと判断することはできません。
[参照元と用途の記録](../THIRD_PARTY_NOTICES.md#参照実装外部の-hermes) を確認してください。

## MIT の採用理由

改造・再利用と商用利用を広く許可する方針で MIT を選びました。改良版のソース公開を
義務づける条項はなく、第三者による非公開製品への組み込みも許容する選択です。
[MIT 原文](https://opensource.org/license/mit) を参照してください。

ルートの `LICENSE`、README、`pyproject.toml` の公開メタデータを MIT に揃えています。
第三者の著作権表示・全文・NOTICE は保持し、独自部分の MIT で第三者の条件を上書きしません。

## ライブラリを変更していない場合

未変更でも、再配布するときには元のライセンス条件が適用されます。MIT の著作権表示・
許諾文の保持、Apache-2.0 の全文と該当する NOTICE の同梱などは、変更の有無とは別の条件です。
[MIT 原文](https://opensource.org/license/mit)、
[Apache-2.0 第4条](https://www.apache.org/licenses/LICENSE-2.0) を参照してください。

| 利用・配布の形 | 確認すること |
| --- | --- |
| 自分の環境へ依存物を導入して実行 | 実行と第三者への再配布を区別する。LGPL 2.1 はライブラリを使うプログラムの実行自体を制限しない |
| 独自ソースを配布し、利用者が依存物を取得 | 配布する独自部分には MIT の通知を付ける。同梱した第三者コードや派生部分には元の条件も適用する |
| container / インストーラー / wheel に依存物も同梱 | 未変更の依存物でもライセンス全文・著作権表示・NOTICE 等を確認する。LGPL は対応ソースの提供や変更版への差し替え等、配布方法に応じた条件を確認する |
| Firmware binary を配布 | バイナリへ組み込まれる SDK・ライブラリ・モデル・素材と、それぞれの配布条件を確認する |

LGPL の実行と再配布の違い、ソース提供・リンクに関する条件は
[LGPL 2.1 第0・4・6条](https://raw.githubusercontent.com/python-zeroconf/python-zeroconf/0.150.0/COPYING)
にあります。MIT を採用したことだけで、依存物を含む配布物全体の条件が満たされるわけではありません。

このリポジトリの Firmware には、[esp-ml307 の派生実装](../firmware/components/stackchan_bridge_client/web_socket.cpp)
と [xiaozhi-esp32 へのパッチ](../firmware/patches/xiaozhi-esp32.patch) があります。
依存物がすべて未変更という状態ではありません。esp-ml307 のファイルには Apache-2.0
由来と変更内容の表示があり、元の全文も保存しています。[第三者通知](../THIRD_PARTY_NOTICES.md)
と [固定版・パッチの記録](../firmware/upstream-lock.json) を保持して配布条件を確認します。

## 配布確認の結果

ソース、第三者パッケージ本体を含めない Python wheel / sdist、M5Stack CoreS3
（ESP32-S3）向け Firmware ZIP の配布準備を整えました。

- 独自部分へ MIT を採用し、第三者の通知を [LICENSES](../LICENSES/README.md) に保存。
- Python lock の第三者104件の版・宣言・通知と、wheel / sdist の収録範囲を確認。
- Firmware managed components 60件、Git 依存6件の通知を保存し、不足していた3件を補完。
- 旧 Font Awesome / Puhui / 結合済み Noto の字形を除外し、固定版の
  Noto・Material Icons・Montserrat から再生成。OFL / Apache-2.0 を保持。
- Twemoji の帰属と CC-BY-4.0、SDK・ランタイム・音声モデルの通知を同梱。
- 実ビルドのリンク内容、assets とモデル、配布する5画像を検証するコマンドを追加。

Firmware に含まれる一部のライブラリ・モデルは Espressif 製品での利用が条件です。
今回の ZIP は CoreS3 用として配布し、通知集を一緒に渡します。
作成手順・根拠・検証記録は [配布物のライセンス確認記録](license-audit.md) にあります。
実機動作確認はこのライセンス確認とは別です。

今後 container やインストーラーに Python 依存環境を同梱する場合は、含める実物について
LGPL / MPL 等の対応ソース・差し替え要件を満たす形で設計します。
