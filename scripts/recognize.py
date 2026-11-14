#!/usr/bin/env python3
"""認識メイン: カメラで箱のQRと区画マーカーを読み、イベント/指示を出す(Recognizer を使う薄いCLI)。

例:
  python scripts/recognize.py --source webcam --show
  python scripts/recognize.py --source file --path work/qr/B001_A.png --max-seconds 3
  python scripts/recognize.py --source videohub -i eth0 --server http://localhost:8000/events
  python scripts/recognize.py --source webcam --command-url http://localhost:8001/command --marker-size-cm 10 --hfov-deg 90
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

from camera_source import CameraError, add_source_args, source_from_args
from recognition_link import add_recognizer_args, build_event, recognizer_from_args  # noqa: F401

GREEN, BLUE = (0, 255, 0), (255, 0, 0)  # BGR


def _draw(frame, dets, last_label):
    for d in dets:
        pts = d["points"]
        zone = d["kind"] == "zone"
        color = BLUE if zone else GREEN
        if zone and d["loc"]:
            label = f"ZONE {d['zone']} {d['loc']['bearing']} {d['loc']['offset']:.2f}"
        else:
            label = d["text"][:30]
        cv2.polylines(frame, [pts.astype("int32").reshape(-1, 1, 2)], True, color, 3)
        x, y = int(pts[0][0]), int(pts[0][1])
        cv2.putText(frame, label, (x, max(y - 8, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    if last_label:
        cv2.putText(frame, last_label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2)


def run(args, source=None):
    """メインループ。発行したイベントのリストを返す(テストで使う)。"""
    own_source = source is None
    if own_source:
        source = source_from_args(args)
    save_dir = Path(args.save_dir) if getattr(args, "save_dir", None) else None
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    def save(ev, frame):
        name = f"{datetime.now():%H%M%S}_{ev['event']}_{ev['box_id'] or 'unknown'}.jpg"
        cv2.imwrite(str(save_dir / name), frame)

    rec = recognizer_from_args(args, source, on_event=save if save_dir else None)
    start = time.monotonic()
    rec.start()
    try:
        while True:
            if args.max_seconds and time.monotonic() - start >= args.max_seconds:
                break
            if args.show:
                view = rec.latest_view()  # cv2.imshow はメインスレッドで行う
                if view is not None:
                    frame = view[0].copy()
                    evs = rec.events()
                    label = f"{evs[-1]['event']}: {evs[-1]['box_id']} {evs[-1]['zone']}" if evs else ""
                    _draw(frame, view[1], label)
                    cv2.imshow("recognize (q: quit)", frame)
                if cv2.waitKey(30) & 0xFF == ord("q"):
                    break
            else:
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("中断しました。", file=sys.stderr)
    finally:
        rec.stop(close_source=own_source)
        if args.show:
            cv2.destroyAllWindows()
    return rec.events()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="箱のQRと区画マーカーを読んで分類先(zone)を判定する")
    add_source_args(parser)
    add_recognizer_args(parser)
    parser.add_argument("--show", action="store_true",
                        help="ウィンドウ表示(q で終了)。箱QRは緑、区画マーカーは青")
    parser.add_argument("--save-dir", type=str, default=None, help="確定時のフレーム保存先")
    parser.add_argument("--max-seconds", type=float, default=None, help="指定秒数で自動終了(テスト用)")
    args = parser.parse_args()
    try:
        run(args)
    except CameraError as e:
        print(f"[エラー] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
