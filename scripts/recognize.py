#!/usr/bin/env python3
"""認識メイン: カメラでQRを読み、分類先(zone)を判定してイベントを出す/POSTする。

例:
  python scripts/recognize.py --source webcam --show
  python scripts/recognize.py --source file --path work/qr/B001_A.png --max-seconds 3
  python scripts/recognize.py --source videohub -i eth0 --server http://localhost:8000/events
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

from camera_source import CameraError, add_source_args, source_from_args
from events import make_event, post_event
from qr_reader import StableDecoder, decode_qr, parse_payload


def build_event(text, zones, run_id=None):
    """確定したQRテキストから scanned / error のイベントを作る。"""
    parsed = parse_payload(text)
    if parsed is None:
        return make_event(
            "error", detail=f"QRを解釈できません: {text!r}", run_id=run_id,
            error={"code": "UNKNOWN_QR", "message": "形式不正"}, data={"qr_raw": text})
    if parsed["zone"] not in zones:
        return make_event(
            "error", parsed["box_id"], None,  # 仕様: 定義外の zone は null で送る
            detail=f"想定外のzone {parsed['zone']!r}: {text!r}", run_id=run_id,
            error={"code": "UNKNOWN_QR", "message": f"zone {parsed['zone']} は想定外"},
            data={"qr_raw": text})
    return make_event(
        "scanned", parsed["box_id"], parsed["zone"],
        detail=f"QR読取成功 {parsed['box_id']} -> {parsed['zone']}", run_id=run_id,
        data={"qr_raw": text})


def _draw(frame, results, last_label):
    for text, pts in results:
        cv2.polylines(frame, [pts.astype("int32").reshape(-1, 1, 2)], True, (0, 255, 0), 3)
        x, y = int(pts[0][0]), int(pts[0][1])
        cv2.putText(frame, text[:30], (x, max(y - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    if last_label:
        cv2.putText(frame, last_label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2)


def run(args, source=None):
    """メインループ。発行したイベントのリストを返す(テストで使う)。"""
    zones = {z.strip().upper() for z in args.zones.split(",") if z.strip()}
    own_source = source is None
    if own_source:
        source = source_from_args(args)
    save_dir = Path(args.save_dir) if args.save_dir else None
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)
    decoder = StableDecoder(confirm_frames=3, cooldown_sec=5.0)
    emitted = []
    run_id = datetime.now().strftime("%Y%m%d-%H%M")
    start = time.monotonic()
    last_ok = time.monotonic()
    last_warn = 0.0
    last_label = ""
    is_file = getattr(args, "source", "") == "file"
    try:
        while True:
            now = time.monotonic()
            if args.max_seconds and now - start >= args.max_seconds:
                break
            frame = source.read()
            if frame is None:
                if now - last_ok > 3.0 and now - last_warn > 3.0:
                    print(f"[警告] {now - last_ok:.0f}秒間フレームを取得できていません。"
                          "カメラ接続・取得元の設定を確認してください。", file=sys.stderr)
                    last_warn = now
                time.sleep(0.02)
                continue
            last_ok = now
            results = decode_qr(frame)
            for text in decoder.update([t for t, _ in results], now=now):
                ev = build_event(text, zones, run_id)
                post_event(args.server, ev, timeout=1.0)
                emitted.append(ev)
                last_label = f"{ev['event']}: {ev['box_id']} {ev['zone']}"
                if save_dir:
                    name = f"{datetime.now():%H%M%S}_{ev['event']}_{ev['box_id'] or 'unknown'}.jpg"
                    cv2.imwrite(str(save_dir / name), frame)
            if args.show:
                _draw(frame, results, last_label)
                cv2.imshow("recognize (q: quit)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            if is_file:
                time.sleep(0.03)
    except KeyboardInterrupt:
        print("中断しました。", file=sys.stderr)
    finally:
        if own_source:
            source.close()
        if args.show:
            cv2.destroyAllWindows()
    return emitted


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="箱のQRを読んで分類先(zone)を判定する")
    add_source_args(parser)
    parser.add_argument("--server", type=str, default=None,
                        help="イベント送信先(例 http://localhost:8000/events)。未指定なら出力のみ")
    parser.add_argument("--zones", type=str, default="A,B", help="想定する zone(カンマ区切り)")
    parser.add_argument("--show", action="store_true", help="ウィンドウ表示(q で終了)")
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
