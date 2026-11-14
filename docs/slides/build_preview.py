"""docs/slides/project/ のスライドを1枚の HTML にまとめ、ブラウザで確認できるようにする。

使い方:
    pixi run slides-preview          # docs/slides/preview.html を生成
    → preview.html をブラウザで開く（スライドの下に話す内容のメモを表示）

/_blob/<id> の画像参照は assets/<id>.png に置き換える。
"""
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE / "project"

BASE_CSS = """
* { margin: 0; box-sizing: border-box; }
body { background: #222; font: 32px/1.2 sans-serif; padding: 24px; counter-reset: page; }
.wrap { width: 960px; margin: 0 auto 48px; }
.frame { width: 960px; height: 540px; overflow: hidden; position: relative; }
.frame > section { width: 1920px; height: 1080px; overflow: hidden; position: relative;
  transform: scale(0.5); transform-origin: 0 0; }
section aside { display: none; }
h2 { font-size: 64px; } h3 { font-size: 44px; }
x-shape, x-icon { display: block; }
x-shape[kind^="arrow-right"] { clip-path: polygon(0 30%, 60% 30%, 60% 0, 100% 50%, 60% 100%, 60% 70%, 0 70%); }
.meta { color: #ccc; font-size: 14px; margin: 8px 0 4px; }
.notes { color: #eee; font-size: 15px; line-height: 1.6; background: #333; padding: 12px 16px; border-radius: 6px; white-space: pre-wrap; }
"""


def main() -> None:
    deck = json.loads((PROJECT / "deck.json").read_text(encoding="utf-8"))
    fonts = "".join(
        f'<link rel="stylesheet" href="{html.escape(f["href"])}">'
        for f in deck.get("faces", {}).values() if "href" in f
    )
    deck_css = (PROJECT / "deck.css").read_text(encoding="utf-8")

    parts = []
    for i, sid in enumerate(deck["order"], 1):
        src = (PROJECT / "slides" / f"{sid}.html").read_text(encoding="utf-8")
        src = re.sub(r'/_blob/([0-9a-f]{32})', r'assets/\1.png', src)
        m = re.search(r"<aside>(.*?)</aside>", src, re.S)
        notes = m.group(1).strip() if m else ""
        parts.append(
            f'<div class="wrap"><div class="frame">{src}</div>'
            f'<p class="meta">{i}. {sid}</p><div class="notes">{notes}</div></div>'
        )

    out = HERE / "preview.html"
    out.write_text(
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(deck['title'])}</title>{fonts}"
        f"<style>{BASE_CSS}</style><style>{deck_css}</style></head><body>"
        + "".join(parts) + "</body></html>",
        encoding="utf-8",
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
