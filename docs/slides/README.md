# 発表スライド（ピックR1！ チーム紹介）

claude.ai の Slides アーティファクトで作った発表スライドの原本です。

- 公開先（オーナーのみ閲覧可。共有は画面の Share から）: https://claude.ai/artifact/2eZNGgjMDeG7PHYxrVKZcr
- 元にしたアイデアシート: [`../idea_summary.md`](../idea_summary.md)

## 構成

```
docs/slides/
├── project/              ← アーティファクトと同じ構成（このフォルダを丸ごと公開する）
│   ├── deck.json         スライドの並び順・タイトル・フォント
│   ├── deck.css          全スライド共通のデザイン
│   └── slides/<id>.html  1枚 = 1ファイル。最後の <aside> が話す内容のメモ
├── assets/<id>.png       スライド内の画像（HTML では /_blob/<id> として参照）
├── build_preview.py      ローカル確認用 HTML の生成
└── preview.html          生成物（git 管理外）
```

並び順は `project/deck.json` の `order` で決まります（現在: 表紙 → 実機デモ → 課題 → 解決策 → 仕組み → 将来展開）。

## ローカルで確認する

```bash
pixi run slides-preview   # docs/slides/preview.html を生成してブラウザで開く
```

アイコン（`<x-icon>`）は描画されません。また、矢印などの図形は簡易表示になります。正確な見た目は公開先で確認してください。

## 編集と反映

1. `project/` 以下のファイルを編集してコミットします。
2. Claude Code に「docs/slides をスライドのアーティファクトに反映して」と頼みます。`root` を `docs/slides` にして公開すると、`project/...` のパスがそのまま使われます。
3. 公開先の画面で直接直した場合は、先に「アーティファクトから docs/slides に取り込んで」と頼み、差分を確認してからコミットします。

### 画像を追加・差し替えるとき

画像はアーティファクトにアップロードすると ID（`/_blob/<id>`）が振られます。アップロード後に、同じ ID で `assets/<id>.png` を保存してください。
