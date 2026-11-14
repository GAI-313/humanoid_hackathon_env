#!/usr/bin/env python3
"""認識まわりの自己テスト。pytest 不要: python scripts/test_recognition.py"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
import threading
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import events  # noqa: E402
import recognize  # noqa: E402
from camera_source import open_source  # noqa: E402
from make_qr import encode_qr  # noqa: E402
from qr_reader import StableDecoder, decode_qr, parse_payload  # noqa: E402


def scene(text, canvas=1200, qr_px=320, angle=8.0):
    """灰色の大きなキャンバスに、縮小・軽く回転したQRを貼った画像を作る。"""
    qr = encode_qr(text, 600)
    qr = cv2.resize(qr, (qr_px, qr_px), interpolation=cv2.INTER_AREA)
    img = np.full((canvas, canvas, 3), 128, np.uint8)
    m = cv2.getRotationMatrix2D((qr_px / 2, qr_px / 2), angle, 1.0)
    rot = cv2.warpAffine(qr, m, (qr_px, qr_px), borderValue=(128, 128, 128))
    x = y = (canvas - qr_px) // 2
    img[y:y + qr_px, x:x + qr_px] = rot
    return img


def test_decode():
    text = '{"box_id":"B001","zone":"A"}'
    res = decode_qr(scene(text))
    assert res and res[0][0] == text, res
    assert res[0][1].shape == (4, 2)


def test_parse():
    assert parse_payload('{"box_id":"B001","zone":"a"}') == {"box_id": "B001", "zone": "A"}
    assert parse_payload("B001:b") == {"box_id": "B001", "zone": "B"}
    for bad in ["", "hello", "{", "[1]", '{"box_id":"B1"}', '{"box_id":1,"zone":"A"}', "B001:", None]:
        assert parse_payload(bad) is None, bad


def test_stable():
    t = [0.0]
    d = StableDecoder(3, 5.0, clock=lambda: t[0])
    assert d.update(["x"], now=0.0) == []
    assert d.update(["x"], now=0.1) == []
    assert d.update([], now=0.2) == []           # 途切れるとリセット
    assert d.update(["x"], now=0.3) == []
    assert d.update(["x"], now=0.4) == []
    assert d.update(["x"], now=0.5) == ["x"]     # 3連続で確定
    for k in range(10):                          # クールダウン中は返さない
        assert d.update(["x"], now=1.0 + k * 0.1) == []
    out = []                                     # クールダウン明けは再び確定
    for k in range(3):
        out += d.update(["x"], now=6.0 + k * 0.1)
    assert out == ["x"]


def test_make_event():
    ev = events.make_event("scanned", "B001", "A", "ok")
    for k in ("ts", "robot", "event", "box_id", "zone", "detail"):
        assert k in ev
    assert ev["robot"] == "R1" and ev["event"] == "scanned"
    assert "+" in ev["ts"] or "-" in ev["ts"][10:], ev["ts"]  # タイムゾーン付き
    assert len(ev["ts"]) == 25  # 秒精度 YYYY-MM-DDTHH:MM:SS+09:00
    # 送信失敗でも例外を出さず False
    with contextlib.redirect_stdout(io.StringIO()):
        assert events.post_event("http://127.0.0.1:9/events", ev, timeout=0.3) is False
        assert events.post_event(None, ev) is False


class _Handler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        _Handler.received.append(json.loads(self.rfile.read(n)))
        self.send_response(201)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


def _args(path, server=None, zones="A,B"):
    return argparse.Namespace(source="file", index=0, path=str(path), port=5001, interface=None,
                              domain=0, server=server, zones=zones, show=False,
                              save_dir=None, max_seconds=1.5)


def test_recognize_file_and_http():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    url = f"http://127.0.0.1:{server.server_port}/events"
    try:
        with tempfile.TemporaryDirectory() as td:
            ok_png, bad_zone_png, junk_png = (Path(td) / n for n in ("ok.png", "bz.png", "junk.png"))
            cv2.imwrite(str(ok_png), scene('{"box_id":"B001","zone":"A"}'))
            cv2.imwrite(str(bad_zone_png), scene("B009:C"))
            cv2.imwrite(str(junk_png), scene("hello world"))
            with contextlib.redirect_stdout(io.StringIO()):
                ev_ok = recognize.run(_args(ok_png, url))
                ev_bz = recognize.run(_args(bad_zone_png))
                ev_junk = recognize.run(_args(junk_png))
        assert [e["event"] for e in ev_ok] == ["scanned"], ev_ok
        assert ev_ok[0]["box_id"] == "B001" and ev_ok[0]["zone"] == "A"
        assert [e["event"] for e in ev_bz] == ["error"] and "C" in ev_bz[0]["detail"]
        assert [e["event"] for e in ev_junk] == ["error"] and "hello world" in ev_junk[0]["detail"]
        assert len(_Handler.received) == 1 and _Handler.received[0]["event"] == "scanned"
    finally:
        server.shutdown()


def test_file_source():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a.png"
        cv2.imwrite(str(p), np.zeros((10, 20, 3), np.uint8))
        s = open_source("file", path=str(p))
        assert s.read().shape == (10, 20, 3) and s.read() is not None
        s.close()


def main() -> int:
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"{len(tests) - failed}/{len(tests)} 件成功")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
