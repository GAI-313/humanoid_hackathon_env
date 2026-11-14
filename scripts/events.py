#!/usr/bin/env python3
"""ダッシュボード receiver へ送るイベントの生成と POST。仕様: docs/log_schema.md"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime

EVENT_TYPES = ("scanned", "moving", "arrived", "error")


def make_event(event, box_id=None, zone=None, detail="", *, run_id=None,
               source="recognition", error=None, data=None) -> dict:
    """イベント本文を作る。ts はタイムゾーン付き(receiver が必須とする)。
    v / run_id / source / error / data は receiver のスキーマ(extra=forbid)に合わせた追加項目。"""
    ev = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "robot": "R1",
        "event": event,
        "box_id": box_id,
        "zone": zone,
        "detail": detail,
        "v": 1,
        "run_id": run_id or datetime.now().strftime("%Y%m%d-%H%M"),
        "source": source,
    }
    if error is not None:
        ev["error"] = error
    if data is not None:
        ev["data"] = data
    return ev


def post_event(url, ev, timeout: float = 1.0) -> bool:
    """JSON を POST する。失敗しても例外は出さず False。標準出力には常に1行 JSON を出す。"""
    body = json.dumps(ev, ensure_ascii=False)
    print(body, flush=True)
    if not url:
        return False
    try:
        req = urllib.request.Request(
            url, data=body.encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return 200 <= res.status < 300
    except Exception as e:  # 送信失敗で認識ループを止めない。ただし黙殺せず知らせる
        reason = e.read().decode("utf-8", "replace")[:300] if hasattr(e, "read") else ""
        print(f"[警告] イベント送信に失敗: {url} {e} {reason}", file=sys.stderr, flush=True)
        return False
