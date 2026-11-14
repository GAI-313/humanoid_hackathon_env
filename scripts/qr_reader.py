#!/usr/bin/env python3
"""QR 検出・デコード、ペイロード解釈、連続フレームでの確定判定。"""
from __future__ import annotations

import json
import re
import time

import cv2
import numpy as np


def _normalize(ret):
    """detectAndDecodeMulti の戻り値の版差を吸収して (texts, points) にする。"""
    if ret is None:
        return [], None
    if len(ret) == 4:
        ok, texts, points, _ = ret
        if not ok:
            return [], None
    elif len(ret) == 3:
        texts, points, _ = ret
    else:
        return [], None
    if points is None or texts is None:
        return [], None
    return list(texts), points


def _try(detector, img):
    try:
        texts, points = _normalize(detector.detectAndDecodeMulti(img))
    except cv2.error:
        return []
    out = []
    for i, t in enumerate(texts):
        if t:  # 空文字=検出できたが読めなかった
            out.append((t, np.asarray(points[i], dtype=np.float32).reshape(-1, 2)))
    return out


def _detectors():
    dets = []
    if hasattr(cv2, "QRCodeDetectorAruco"):
        try:
            dets.append(cv2.QRCodeDetectorAruco())
        except Exception:
            pass
    dets.append(cv2.QRCodeDetector())
    return dets


def decode_qr(frame):
    """frame(BGR) から QR を読む。戻り値は [(text, points(4x2, 元画像座標)), ...]。
    0件なら グレースケール+2倍拡大、さらに適応的二値化で再試行する。"""
    if frame is None:
        return []
    dets = _detectors()
    for det in dets:
        r = _try(det, frame)
        if r:
            return r
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    big = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    for det in dets:
        r = _try(det, big)
        if r:
            return [(t, p / 2.0) for t, p in r]
    binary = cv2.adaptiveThreshold(big, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 31, 10)
    for det in dets:
        r = _try(det, binary)
        if r:
            return [(t, p / 2.0) for t, p in r]
    return []


_SIMPLE = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*:\s*([A-Za-z0-9_\-]+)\s*$")


def parse_payload(text):
    """{"box_id":"B001","zone":"A"} または B001:A を解釈する。不可なら None。"""
    if not isinstance(text, str):
        return None
    s = text.strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except ValueError:
            return None
        if not isinstance(obj, dict):
            return None
        box, zone = obj.get("box_id"), obj.get("zone")
    else:
        m = _SIMPLE.match(s)
        if not m:
            return None
        box, zone = m.group(1), m.group(2)
    if not isinstance(box, str) or not isinstance(zone, str):
        return None
    box, zone = box.strip(), zone.strip().upper()
    if not box or not zone:
        return None
    return {"box_id": box, "zone": zone}


class StableDecoder:
    """同じテキストが confirm_frames 回連続したら確定。確定後 cooldown_sec は同じテキストを返さない。"""

    def __init__(self, confirm_frames: int = 3, cooldown_sec: float = 5.0, clock=time.monotonic):
        self.confirm_frames = confirm_frames
        self.cooldown_sec = cooldown_sec
        self._clock = clock
        self._counts = {}
        self._last = {}

    def update(self, texts, now=None):
        """1フレーム分のテキスト一覧を渡し、新たに確定したテキストのリストを返す。"""
        now = self._clock() if now is None else now
        seen = set(texts)
        # 見えなかったテキストは連続が途切れる
        self._counts = {t: self._counts.get(t, 0) + 1 for t in seen}
        confirmed = []
        for t in sorted(seen):
            if self._counts[t] < self.confirm_frames:
                continue
            last = self._last.get(t)
            if last is not None and now - last < self.cooldown_sec:
                continue
            self._last[t] = now
            self._counts[t] = 0
            confirmed.append(t)
        return confirmed
