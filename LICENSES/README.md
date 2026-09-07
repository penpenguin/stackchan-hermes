# Third-party license evidence

確認日: 2026-09-07。第三者の著作権表示・許諾文・NOTICE を保存しています。
独自コードの MIT は、第三者コード・フォント・画像・モデルの条件を上書きしません。
Python wheel / sdist と、検証コマンドで作る CoreS3 Firmware ZIP にこの通知集を収録します。

## 一覧と保存形式

| ファイル | 対象 |
| --- | --- |
| [python.json](python.json) | `uv.lock` の第三者パッケージ104件。通常・STT・開発依存、OS 条件を含む |
| [firmware-managed.json](firmware-managed.json) | 固定 content hash と照合した managed components 60件と通知の補完根拠 |
| [firmware-git.json](firmware-git.json) | 固定 commit で取得する Git 依存6件 |
| [firmware-fonts.json](firmware-fonts.json) | 置換フォントの固定入力、著作権表示、適用条件、生成物のハッシュ |
| [firmware-sdk.json](firmware-sdk.json) | ESP-IDF v5.5.4、ツールチェーンのランタイム、コンパイルした SDK ソースの通知、実際に選択された archive |
| [firmware-supplemental.json](firmware-supplemental.json) | vendor / Twemoji の補足通知、素材のハッシュ、配布から除外した旧フォントの調査記録 |

`notices` の `original_path` は元の配布物中の名前、`text` はリポジトリルートからの
保存先、`sha256` は原文バイト列のハッシュです。同じ本文は `texts/<sha256>.txt` に
重複を除いて保存しています。`source` に公開取得元、補った本文にはその根拠を記録します。
全文・通知の保存ファイルは243件です。通知には未リンク・任意・開発依存のものも含みます。

Python の宣言は配布物の `METADATA` から取得し、本文がなければ固定版 upstream で
補完しました。ローカル distribution の記録は元アーカイブ全体のハッシュ再検証とは
区別します。Python wheel / sdist は第三者パッケージ本体や Firmware を同梱しません。

## 素材の帰属表示

### StackChan Text / Icons / UI

文字・アイコン・見出しは、取得元・版・SHA-256 を固定した入力から生成しました。
フォントのサブセット化、文字コードの再割当て、LVGL 用ラスタライズを行っています。
元のフォント名を改変フォントの商品名として使わず、StackChan Text / Icons / UI と呼びます。
完全な入力メタデータは [firmware-fonts.json](firmware-fonts.json) に保存しています。

| 元フォント | 著作権表示 | 生成した字形の条件 |
| --- | --- | --- |
| Noto Sans CJK JP Regular 2.004 | © 2014–2021 Adobe (http://www.adobe.com/) | [OFL-1.1](texts/6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2.txt) |
| Noto Sans Regular | Copyright 2015–2021 Google LLC. All Rights Reserved. | [OFL-1.1](texts/0dab92d0544f7b233403f14b84a663bdbfa746982eda629e7f4f9ffe1b036feb.txt) |
| Noto Sans Thai Regular | Copyright 2016 Google Inc. All Rights Reserved. | 同上 |
| Noto Sans Math Regular | Copyright 2018 Google LLC. All Rights Reserved. | 同上 |
| Material Icons Regular | Copyright 2018 Google, Inc. All Rights Reserved. | [Apache-2.0](texts/58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd.txt) |
| Montserrat SemiBold | Copyright 2011 The Montserrat Project Authors (https://github.com/JulietaUla/Montserrat)。固定 repository の通知: Copyright 2024 The Montserrat.Git Project Authors | [OFL-1.1](texts/8b7141c03fa4f8d44e6345d5d4931709290f0f67875e452e95ac1fd3a027802e.txt) |

OFL ファイルには The Noto Project Authors 等の repository 側の著作権表示も保持します。
変換器 `lv_font_conv` の C 出力テンプレートは Copyright (c) 2018 authors、
[MIT](texts/959add68a50f49e55cdb8c66c3c50112e3906a7a5210fb677e503f3ab281c018.txt) です。
この MIT は字形自体の OFL / Apache-2.0 と併存します。

旧 `78/xiaozhi-fonts@1.6.0` の Puhui / 結合済み Noto / Font Awesome 字形は、
コンパイル対象と assets の入力から除外しています。`font_awesome_*` の C シンボル名は
既存 UI との互換のため残りますが、中身は Material Icons から生成したものです。

### Twemoji

Graphics Author: Copyright 2020 Twitter, Inc and other contributors

Graphics Source: https://github.com/twitter/twemoji

Graphics License: [Creative Commons Attribution 4.0 International](texts/8ae9438818c26e4873b91d8c6ad620526c011e27e125677f13031eda903f007c.txt)

`78/xiaozhi-fonts@1.6.0` の生成スクリプトにある帰属表示を保持します。upstream が SVG を
画像・組み込み用データへ変換した素材です。CoreS3 の assets には `twemoji_64` の21枚を
そのまま収録し、実際のバイナリ内の画像と固定 component 内の画像の一致を検証します。
CC-BY-4.0 の全文は Twemoji v14.0.2 の `LICENSE-GRAPHICS` から保存しました。

### M5Stack の画像・効果音

固定した公式 snapshot の [MIT 通知](texts/69de21aa5e3dea7723e781bc773a701db5afce066421c7518db2092d743e4a3e.txt)、
Copyright 2026 M5Stack Technology CO LTD を保持します。画像・効果音のハッシュは
[補足記録](firmware-supplemental.json) にあります。独立した条件が見つかったフォントは
上記の通り別扱いとし、確認した入力から再生成しています。

## SDK・音声モデル・ランタイム

ESP-IDF 全体を Apache-2.0 一つにまとめず、SDK 内の個別通知と、コンパイルした
ソース先頭の著作権・ライセンス表示を保存しています。Xtensa libhal の MIT 全文、
newlib の個別通知、GCC / libstdc++ の GPL-3.0 と GCC Runtime Library Exception 3.1
も [SDK 記録](firmware-sdk.json) に含みます。今回の通常の GCC ビルドではランタイム例外に
基づいて独立したプログラムと結合します。開発ツールの実行ファイルは同梱しません。

WakeNet `wn9_histackchan_tts3` の3ファイルは、固定 `esp-sr@2.3.1` のモデルとバイト単位で
照合します。一部の Espressif ライブラリ・モデルは Espressif 製品での利用が条件です。
今回の Firmware ZIP は ESP32-S3 を使う M5Stack CoreS3 用です。この条件と通知を保持します。

配布範囲・補完根拠・再検証手順は [監査記録](../docs/license-audit.md) にまとめています。
