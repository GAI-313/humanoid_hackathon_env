#!/usr/bin/env python3
"""担当A(移動と腕)向けの見本。ロボットは動かさず、何をすべきかを print するだけ。

■ (a) 同一プロセス方式(おすすめ): Recognizer を自分のプロセスに組み込む
    python scripts/control_example.py --source webcam
    python scripts/control_example.py --source videohub -i <iface> --arrive-size 0.25
  Recognizer を start し、pop_box() で箱を待ち、get_target(zone) を0.2秒ごとに読んで
  「左へ旋回 / 右へ旋回 / 前進 / 到着」を決める。実機では print の場所に LocoClient の呼び出しを書く。
  DDS の ChannelFactoryInitialize は自分のプロセスで1回だけ。Recognizer 自身は初期化しない。

■ (b) 別プロセス方式: 認識側から HTTP で指示を受ける
    # ターミナル1(受け側)
    python scripts/control_example.py --listen 8001
    # ターミナル2(認識側)
    python scripts/recognize.py --source webcam --command-url http://localhost:8001/command
  /command への POST(go_to / target の JSON)を受けて print する。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from camera_source import CameraError, add_source_args, source_from_args  # noqa: E402
from recognition_link import add_recognizer_args, recognizer_from_args  # noqa: E402


def decide(target, turn_offset, arrive_size):
    """区画マーカーの観測から動作を決める。target は get_target() の戻り値(または None)。"""
    if target is None:
        return "探索(区画マーカーが見えない)"
    if target["bearing"] == "left" and abs(target["offset"]) > turn_offset:
        return "左へ旋回"
    if target["bearing"] == "right" and abs(target["offset"]) > turn_offset:
        return "右へ旋回"
    if target["size_ratio"] >= arrive_size:
        return "到着"
    return "前進"


def run_local(args) -> int:
    source = source_from_args(args)  # videohub のときだけ DDS を1回初期化する
    rec = recognizer_from_args(args, source)
    rec.start()
    goal = None
    start = time.monotonic()
    try:
        while not (args.max_seconds and time.monotonic() - start >= args.max_seconds):
            box = rec.pop_box(timeout=0.2)
            if box:
                goal = box
                print(f"[箱] {box['box_id']} を区画 {box['zone']} へ運ぶ")
            if goal is None:
                continue
            tgt = rec.get_target(goal["zone"])
            action = decide(tgt, args.turn_offset, args.arrive_size)
            print(f"[区画 {goal['zone']}] {action}" + (f" offset={tgt['offset']:+.2f} size={tgt['size_ratio']:.2f}"
                                                      if tgt else ""))
            # ここで loco.Move(vx, vy, vyaw) など。旋回なら vyaw、前進なら vx を与える。
            #   (Move は約1秒で失効するので、このループで繰り返し送ること)
            if action == "到着":
                # ここで loco.StopMove() し、腕で箱を置く動作へ。
                print("  -> 停止して箱を置く")
                goal = None
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("中断しました。", file=sys.stderr)
    finally:
        rec.stop(close_source=True)
    return 0


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        ok = self.path == "/command"
        if ok:
            try:
                print(json.dumps(json.loads(raw), ensure_ascii=False), flush=True)
            except ValueError:
                ok = False
        self.send_response(200 if ok else 400)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


def run_listen(port) -> int:
    server = HTTPServer(("0.0.0.0", port), _Handler)
    print(f"待ち受け開始: http://0.0.0.0:{port}/command (Ctrl+C で終了)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="担当A向け見本(ロボットは動かさない)。詳細は docstring 参照")
    add_source_args(parser)
    add_recognizer_args(parser)
    parser.add_argument("--listen", type=int, default=None, metavar="PORT",
                        help="別プロセス方式: このポートで /command への POST を受けて print する")
    parser.add_argument("--arrive-size", type=float, default=0.25,
                        help="到着とみなす size_ratio の閾値")
    parser.add_argument("--turn-offset", type=float, default=0.15, help="旋回を始める |offset| の閾値")
    parser.add_argument("--max-seconds", type=float, default=None, help="指定秒数で自動終了(テスト用)")
    args = parser.parse_args()
    if args.listen is not None:
        return run_listen(args.listen)
    try:
        return run_local(args)
    except CameraError as e:
        print(f"[エラー] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
