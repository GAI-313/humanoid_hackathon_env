"""ダミーイベントを receiver へ POST する（実機なしの開発・保険デモ用）。

使い方:
  pixi run python dashboard/send_dummy.py            # 区画A に1箱
  pixi run python dashboard/send_dummy.py --zone B
  pixi run python dashboard/send_dummy.py --error    # 想定外QR（誤出荷）
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import datetime

from common import RECEIVER_URL


def build(run_id: str, box_id: str | None, event: str, zone: str | None,
          source: str, detail: str, **extra) -> dict:
    body = {
        "v": 1,
        "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "robot": "R1",
        "run_id": run_id,
        "box_id": box_id,
        "event": event,
        "zone": zone,
        "source": source,
        "detail": detail,
    }
    body.update(extra)
    return body


def post(body: dict, url: str = RECEIVER_URL) -> dict:
    req = urllib.request.Request(
        f"{url}/events",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=3) as res:
        return json.loads(res.read())


def send_box(box_id: str, zone: str, run_id: str = "dummy", wait: float = 1.0,
             url: str = RECEIVER_URL) -> None:
    post(build(run_id, box_id, "scanned", zone, "dashboard", "QR読取成功 (dummy)",
               data={"attempts": 1, "read_ms": 800}), url)
    time.sleep(wait)
    post(build(run_id, box_id, "moving", zone, "dashboard", f"区画{zone}へ移動",
               data={"from": "start", "to": zone}), url)
    time.sleep(wait * 2)
    post(build(run_id, box_id, "arrived", zone, "dashboard", "腕で指し示し完了 (dummy)",
               data={"gesture": "point"}), url)


def send_error(box_id: str = "X999", run_id: str = "dummy", url: str = RECEIVER_URL) -> None:
    post(build(run_id, box_id, "error", None, "dashboard", "想定外QR: 区画定義なし",
               error={"code": "UNKNOWN_QR", "message": "zone が定義外"},
               data={"qr_raw": box_id}), url)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", default="A", choices=["A", "B"])
    ap.add_argument("--box", default=None, help="箱ID（省略時は時刻から自動）")
    ap.add_argument("--error", action="store_true", help="想定外QR（誤出荷）を送る")
    ap.add_argument("--url", default=RECEIVER_URL)
    args = ap.parse_args()
    if args.error:
        send_error(url=args.url)
    else:
        send_box(args.box or f"B{int(time.time()) % 1000:03d}", args.zone, url=args.url)
    print("sent")
