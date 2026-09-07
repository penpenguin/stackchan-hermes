# StackChan 配布用フォント

元の `78/xiaozhi-fonts` に含まれる Font Awesome / Puhui / 結合済み Noto の字形を
配布用ビルドから除外し、以下の固定入力から生成した字形を使います。
文字コードとの対応を保つため `font_awesome_*` という C シンボル名は残りますが、
その字形は Material Icons です。製品内でのフォント名は StackChan Text / Icons / UI とします。

| 入力 | 固定版・著作権表示 | 適用条件 |
| --- | --- | --- |
| Noto Sans CJK JP Regular | Sans 2.004、© 2014–2021 Adobe | [OFL-1.1](../../LICENSES/texts/6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2.txt) |
| Noto Sans Regular | Google LLC、2015–2021 | [OFL-1.1](../../LICENSES/texts/0dab92d0544f7b233403f14b84a663bdbfa746982eda629e7f4f9ffe1b036feb.txt) |
| Noto Sans Thai Regular | Google Inc.、2016 | 同上 |
| Noto Sans Math Regular | Google LLC、2018 | 同上 |
| Material Icons Regular | Google, Inc.、2018 | [Apache-2.0](../../LICENSES/texts/58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd.txt) |
| Montserrat SemiBold | The Montserrat Project Authors、2011。固定 repository の OFL には The Montserrat.Git Project Authors、2024 の通知もある | [OFL-1.1](../../LICENSES/texts/8b7141c03fa4f8d44e6345d5d4931709290f0f67875e452e95ac1fd3a027802e.txt) |
| lv_font_conv の出力テンプレート | Copyright (c) 2018 authors | [MIT](../../LICENSES/texts/959add68a50f49e55cdb8c66c3c50112e3906a7a5210fb677e503f3ab281c018.txt) |

各入力の完全な copyright / license メタデータ、取得 URL、commit、SHA-256 と全文は
[フォント通知記録](../../LICENSES/firmware-fonts.json) に保存しています。
OFL フォントおよび変換した字形は OFL を保持し、プロジェクトの MIT へ変更しません。
Material Icons はサブセット化、文字コードの再割当て、ラスタライズを行いました。
これらの変更表示は生成した C ファイルにも記録します。元の TTF / OTF は未変更の入力です。

## 収録範囲

- [font-codepoints.json](font-codepoints.json): 元の文字範囲に JIS X 0208 を加えた
  9,561文字。制御文字・書式制御文字を除き、どの固定フォントから採ったかを記録する。
- [icons.json](icons.json): 互換文字コード135個と Material Icons の対応。
  Wi-Fi の4状態と電池の6状態はそれぞれ異なるアイコンにする。
- 内蔵文字フォント: 20px / 4bpp、ASCII・Latin-1。
- assets 用文字フォント: 20px / 4bpp、9,561文字。変換器のカーニングクラス数制限を
  避けるため、このファイルだけペアカーニングを無効化する。各文字の送り幅は保持する。
- UI 見出し: 固定版 Montserrat SemiBold から26px / 2bppで再生成する。

出力のハッシュは [outputs.json](outputs.json) にある。通常の Firmware ビルドは
生成済みのファイルを使い、フォントの取得や Node.js の実行を必要としない。

## 再生成

リポジトリのルートで実行する。変換ツールと入力は Git 管理外の `.local/` に配置する。
元の字形を取得したい場合の URL / hash は [input-lock.json](input-lock.json) を正とする。

```bash
git clone https://github.com/78/lv_font_conv.git .local/font-tools/lv_font_conv
git -C .local/font-tools/lv_font_conv checkout --detach db011302d4f448027cbf1af6d0d47a27d59d22c1
npm --prefix .local/font-tools/lv_font_conv ci --omit=dev --ignore-scripts --no-audit --no-fund
uv run --locked python firmware/tools/generate_release_fonts.py \
  --inputs .local/font-inputs --converter .local/font-tools/lv_font_conv --download
uv run --locked pytest -q bridge/tests/test_release_fonts.py
```

生成器は入力と変換器の固定版・dependency lock を照合してから実行する。再生成時に
`outputs.json` と [フォント通知記録](../../LICENSES/firmware-fonts.json) を揃える。
フォントや mapping を変更した場合は、Firmware を再ビルドし、配布物の検証も再実施する。
