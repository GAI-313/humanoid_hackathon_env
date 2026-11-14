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
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commands  # noqa: E402
import events  # noqa: E402
import recognize  # noqa: E402
from camera_source import open_source  # noqa: E402
from make_qr import encode_qr  # noqa: E402
from qr_reader import StableDecoder, decode_qr, locate, parse_payload, parse_zone_marker  # noqa: E402
from recognition_link import Recognizer  # noqa: E402
import pick_move  # noqa: E402
import qr_survey  # noqa: E402


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


def test_parse_zone_marker():
    assert parse_zone_marker("ZONE:A") == "A"
    assert parse_zone_marker("zone: b") == "B"
    assert parse_zone_marker('{"zone_marker":"a"}') == "A"
    for bad in ["", "B001:A", "hello", "{", '{"zone":"A"}', '{"zone_marker":1}', None]:
        assert parse_zone_marker(bad) is None, bad
    assert parse_payload("ZONE:A") is None
    assert parse_payload('{"zone_marker":"A"}') is None


def test_locate():
    shape = (480, 640, 3)

    def sq(cx, side=64.0, cy=240.0):
        h = side / 2
        return np.array([[cx - h, cy - h], [cx + h, cy - h], [cx + h, cy + h], [cx - h, cy + h]])

    left, mid, right = (locate(sq(x), shape) for x in (100, 320, 540))
    assert left["bearing"] == "left" and left["offset"] < -0.5, left
    assert mid["bearing"] == "center" and abs(mid["offset"]) < 0.01, mid
    assert right["bearing"] == "right" and right["offset"] > 0.5, right
    assert abs(mid["size_ratio"] - 0.1) < 1e-6 and mid["distance_m"] is None
    # 一辺0.10m, 水平画角90度, size_ratio 0.1 -> 0.10 / (2*1*0.1) = 0.5m
    assert abs(locate(sq(320), shape, 0.10, 90.0)["distance_m"] - 0.5) < 0.01
    assert locate(sq(320), shape, 0.10, None)["distance_m"] is None
    assert locate(sq(320 + 0.15 * 320), shape)["bearing"] == "center"  # 境界 0.15 は center


def _two_qr_scene():
    """左に箱QR、右に区画マーカー(ZONE:A)を並べた画像。"""
    img = np.full((700, 1400, 3), 128, np.uint8)
    for text, x in (('{"box_id":"B001","zone":"A"}', 150), ("ZONE:A", 900)):
        qr = cv2.resize(encode_qr(text, 600), (350, 350), interpolation=cv2.INTER_AREA)
        img[175:525, x:x + 350] = qr
    return img


def _wait(cond, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


class _CmdHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        _CmdHandler.received.append(json.loads(self.rfile.read(n)))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


def test_recognizer_box_and_target():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "two.png"
        cv2.imwrite(str(p), _two_qr_scene())
        src = open_source("file", path=str(p))
        called = []
        rec = Recognizer(src, on_box=lambda b, z: called.append((b, z)))
        with contextlib.redirect_stdout(io.StringIO()):
            rec.start()
            try:
                assert _wait(lambda: called and rec.get_target("A")), (called, rec.stats())
                time.sleep(0.5)
            finally:
                rec.stop(close_source=True)
        assert called == [("B001", "A")], called
        tgt = rec.get_target("A", max_age=60)
        assert tgt["zone"] == "A" and tgt["bearing"] == "right" and tgt["offset"] > 0.3, tgt
        assert tgt["distance_m"] is None and tgt["age_sec"] >= 0
        assert rec.last_box()["box_id"] == "B001"
        assert rec.pop_box()["zone"] == "A" and rec.pop_box() is None
        assert rec.get_target("B") is None
        assert rec.stats()["frames"] > 0


def test_recognizer_command_url():
    server = HTTPServer(("127.0.0.1", 0), _CmdHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _CmdHandler.received.clear()
    url = f"http://127.0.0.1:{server.server_port}/command"
    try:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "two.png"
            cv2.imwrite(str(p), _two_qr_scene())
            src = open_source("file", path=str(p))
            rec = Recognizer(src, command_url=url, marker_size_m=0.1, hfov_deg=90, target_hz=20)
            with contextlib.redirect_stdout(io.StringIO()):
                rec.start()
                try:
                    kinds = lambda: {c["cmd"] for c in _CmdHandler.received}  # noqa: E731
                    assert _wait(lambda: kinds() >= {"go_to", "target"}), _CmdHandler.received
                finally:
                    rec.stop(close_source=True)
        goto = next(c for c in _CmdHandler.received if c["cmd"] == "go_to")
        tgt = next(c for c in _CmdHandler.received if c["cmd"] == "target")
        assert goto["box_id"] == "B001" and goto["zone"] == "A" and goto["v"] == 1
        assert tgt["zone"] == "A" and tgt["visible"] is True and tgt["bearing"] == "right"
        assert tgt["distance_m"] is not None and tgt["run_id"] == goto["run_id"]
        lost = commands.make_target("A", None, "r")
        assert lost["visible"] is False and lost["offset"] is None
    finally:
        server.shutdown()


def test_on_box_exception_keeps_thread_alive():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "two.png"
        cv2.imwrite(str(p), _two_qr_scene())
        src = open_source("file", path=str(p))
        called = []

        def boom(b, z):
            called.append(b)
            raise RuntimeError("テスト用の例外")

        rec = Recognizer(src, on_box=boom)
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rec.start()
            try:
                assert _wait(lambda: called)
                n = rec.stats()["frames"]
                assert _wait(lambda: rec.stats()["frames"] > n + 2)
                assert rec._thread.is_alive()
            finally:
                rec.stop(close_source=True)
        assert "テスト用の例外" in err.getvalue()


def test_post_command_failure():
    with contextlib.redirect_stderr(io.StringIO()):
        assert commands.post_command("http://127.0.0.1:9/command", {"a": 1}, timeout=0.3) is False
    assert commands.post_command(None, {}) is False


def test_survey_summarize():
    def det(text, size, off):
        return {"text": text, "size": size, "offset": off}

    recs = [
        {"ms": 10.0, "dets": [det("ZONE:A", 0.10, 0.2), det("B001:A", 0.30, -0.1)]},
        {"ms": 20.0, "dets": [det("ZONE:A", 0.20, 0.4)]},
        {"ms": 30.0, "dets": []},
        {"ms": 40.0, "dets": [det("ZONE:A", 0.30, 0.0), det("ZONE:A", 0.30, 0.0)]},  # 同一フレーム重複
    ]
    s = qr_survey.summarize(recs)
    assert s["frames"] == 4 and s["hit_frames"] == 3 and abs(s["hit_rate"] - 0.75) < 1e-9
    assert abs(s["decode_ms_mean"] - 25.0) < 1e-9 and s["decode_ms_max"] == 40.0
    z = next(t for t in s["texts"] if t["text"] == "ZONE:A")
    assert z["kind"] == "zone" and z["hits"] == 3 and abs(z["rate"] - 0.75) < 1e-9
    assert abs(z["size_mean"] - 0.2) < 1e-9 and z["size_min"] == 0.10 and z["size_max"] == 0.30
    assert abs(z["offset_mean"] - 0.2) < 1e-9
    b = next(t for t in s["texts"] if t["text"] == "B001:A")
    assert b["kind"] == "box" and b["hits"] == 1 and abs(b["rate"] - 0.25) < 1e-9
    empty = qr_survey.summarize([{"ms": 5.0, "dets": []}])
    assert empty["hit_frames"] == 0 and empty["texts"] == []
    rows = qr_survey.csv_rows(empty, {"fps": 1.0, "width": 1, "height": 1}, "x", "file", "t")
    assert len(rows) == 1 and rows[0]["text"] == ""


def _tgt(offset, size):
    return {"offset": offset, "size_ratio": size, "bearing": "x", "distance_m": None, "zone": "A"}


def test_zone_approach():
    A = pick_move.ZoneApproach
    d = A().step(_tgt(-0.5, 0.1), 0.0)  # 左のマーカー -> 左旋回(vyaw 正)
    assert d["state"] == "turn" and d["vyaw"] > 0 and d["vx"] == 0.0 and d["vy"] == 0.0, d
    d = A().step(_tgt(0.5, 0.1), 0.0)
    assert d["state"] == "turn" and d["vyaw"] < 0, d
    d = A().step(_tgt(0.0, 0.1), 0.0)
    assert d["state"] == "forward" and d["vx"] == 0.2 and abs(d["vyaw"]) < 1e-9, d
    d = A().step(_tgt(0.075, 0.1), 0.0)
    assert d["state"] == "forward" and d["vyaw"] < 0 and abs(d["vyaw"]) <= 0.15 + 1e-9, d
    d = A().step(_tgt(0.5, 0.3), 0.0)  # 大きければ offset に関わらず到着
    assert d["state"] == "arrived" and d["vx"] == 0.0 and d["vyaw"] == 0.0, d
    # 見失い
    a = A(lost_timeout=3.0)
    a.step(_tgt(0.0, 0.1), 0.0)
    assert a.step(None, 1.0)["state"] == "wait"
    d = a.step(None, 3.5)
    assert d["state"] == "failed" and d["vx"] == 0.0, d
    a = A(lost_timeout=3.0, search=True)
    a.step(_tgt(0.0, 0.1), 0.0)
    assert a.step(None, 1.0)["state"] == "wait"
    d = a.step(None, 3.5)
    assert d["state"] == "search" and abs(d["vyaw"] - 0.15) < 1e-9 and d["vx"] == 0.0, d
    # 最初から見えない場合は開始時刻が基準
    a = A(lost_timeout=3.0)
    assert a.step(None, 10.0)["state"] == "wait" and a.step(None, 14.0)["state"] == "failed"
    # move_timeout は常に failed(見えていても)
    a = A(move_timeout=30.0, search=True)
    a.step(_tgt(0.0, 0.1), 0.0)
    assert a.step(_tgt(0.0, 0.1), 31.0)["state"] == "failed"
    # 速度上限の丸め
    with contextlib.redirect_stderr(io.StringIO()) as err:
        a = A(vx_max=1.0, vyaw_max=2.0)
    assert a.vx_max == 0.3 and a.vyaw_max == 0.5 and "丸め" in err.getvalue()
    assert abs(a.step(_tgt(1.0, 0.1), 0.0)["vyaw"]) <= 0.5
    with contextlib.redirect_stderr(io.StringIO()):
        a = A(vx_max=-1.0)
    assert a.vx_max == 0.0


class _FakeLoco:
    def __init__(self, fail_move=False):
        self.calls = []
        self.fail_move = fail_move

    def Move(self, vx, vy, vyaw):
        if self.fail_move:
            raise RuntimeError("Move失敗(テスト)")
        self.calls.append(("Move", vx, vy, vyaw))
        return 0

    def StopMove(self):
        self.calls.append(("StopMove",))
        return 0

    def WaveHand(self):
        self.calls.append(("WaveHand",))
        return 0


def _pick_scene(marker_px, marker_x):
    img = np.full((700, 1400, 3), 128, np.uint8)
    for text, x, px, y in (('{"box_id":"B001","zone":"A"}', 100, 300, 200), ("ZONE:A", marker_x, marker_px, 100)):
        qr = cv2.resize(encode_qr(text, 600), (px, px), interpolation=cv2.INTER_AREA)
        img[y:y + px, x:x + px] = qr
    return img


def _pick_args(path, *extra):
    return pick_move.build_parser().parse_args(
        ["--source", "file", "--path", str(path), *extra])


def test_pick_move_dry_run_and_arrived():
    with tempfile.TemporaryDirectory() as td:
        small, big = Path(td) / "small.png", Path(td) / "big.png"
        cv2.imwrite(str(small), _pick_scene(180, 1000))   # 小さめ・右寄り
        cv2.imwrite(str(big), _pick_scene(600, 700))      # 大きい
        loco = _FakeLoco()
        with contextlib.redirect_stdout(io.StringIO()):
            evs = pick_move.run(_pick_args(small, "--max-seconds", "3.5"), loco=loco)
        assert any(c[0] == "Move" for c in loco.calls), loco.calls
        mv = next(c for c in loco.calls if c[0] == "Move")
        assert mv[3] < 0, mv  # 右寄り -> 右旋回
        assert loco.calls[-1] == ("StopMove",), loco.calls[-3:]
        assert [e["event"] for e in evs] == ["moving"], evs
        assert evs[0]["data"] == {"from": "start", "to": "A"} and evs[0]["source"] == "control"
        loco = _FakeLoco()
        with contextlib.redirect_stdout(io.StringIO()):
            evs = pick_move.run(_pick_args(big, "--max-seconds", "6", "--once", "--gesture", "wave"),
                                loco=loco)
        assert [e["event"] for e in evs] == ["moving", "arrived"], evs
        assert evs[1]["data"]["gesture"] == "wave" and "duration_ms" in evs[1]["data"]
        assert ("WaveHand",) in loco.calls and loco.calls[-1] == ("StopMove",)
        # 既定(loco 未指定)は dry-run: 実機の SDK を触らず終了できる
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            pick_move.run(_pick_args(big, "--once", "--max-seconds", "6"))
        assert "[dry-run] StopMove()" in out.getvalue()


def test_pick_move_stopmove_on_exception():
    with tempfile.TemporaryDirectory() as td:
        small = Path(td) / "small.png"
        cv2.imwrite(str(small), _pick_scene(180, 1000))
        loco = _FakeLoco(fail_move=True)
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                pick_move.run(_pick_args(small, "--max-seconds", "4"), loco=loco)
                raise AssertionError("例外が伝わるはず")
            except RuntimeError as e:
                assert "Move失敗" in str(e)
        assert loco.calls and loco.calls[-1] == ("StopMove",), loco.calls


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
