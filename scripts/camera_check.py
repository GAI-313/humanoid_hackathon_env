#!/usr/bin/env python3
"""カメラ取得元の診断: 数秒読んで解像度・実測fps・取得成功率を表示し、1枚保存する。

例:
  python scripts/camera_check.py --source webcam
  python scripts/camera_check.py --source udp --port 5002 --seconds 5
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

from camera_source import CameraError, add_source_args, source_from_args


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="カメラ取得元の診断(解像度・fps・成功率)")
    add_source_args(parser)
    parser.add_argument("--seconds", type=float, default=3.0, help="計測する秒数")
    parser.add_argument("--out", type=str, default="work/camera_check.jpg", help="保存先画像")
    args = parser.parse_args()

    try:
        source = source_from_args(args)
    except CameraError as e:
        print(f"[失敗] {e}", file=sys.stderr)
        return 1

    attempts = ok = 0
    last = None
    start = time.monotonic()
    try:
        while time.monotonic() - start < args.seconds:
            attempts += 1
            frame = source.read()
            if frame is None:
                time.sleep(0.01)
                continue
            ok += 1
            last = frame
    except KeyboardInterrupt:
        pass
    finally:
        source.close()
    elapsed = time.monotonic() - start

    print(f"取得元: {args.source}  計測: {elapsed:.1f}秒")
    print(f"取得成功率: {ok}/{attempts} ({100.0 * ok / max(attempts, 1):.0f}%)")
    if last is None:
        print("[失敗] フレームを1枚も取得できませんでした。", file=sys.stderr)
        return 1
    h, w = last.shape[:2]
    print(f"解像度: {w}x{h}  実測fps: {ok / elapsed:.1f}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), last)
    print(f"保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
