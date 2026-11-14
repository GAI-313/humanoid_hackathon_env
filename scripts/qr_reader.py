#!/usr/bin/env python3
"""QR 検出・デコード、ペイロード解釈、連続フレームでの確定判定。"""
from __future__ import annotations

import json
import math
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


_ZONE_MARKER = re.compile(r"^\s*ZONE\s*:\s*([A-Za-z0-9_\-]+)\s*$", re.IGNORECASE)


def parse_zone_marker(text):
    """区画マーカー(`ZONE:A` または {"zone_marker":"A"})なら大文字化した zone を返す。違えば None。"""
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
        zone = obj.get("zone_marker")
        if not isinstance(zone, str) or not zone.strip():
            return None
        return zone.strip().upper()
    m = _ZONE_MARKER.match(s)
    return m.group(1).upper() if m else None


def parse_payload(text):
    """{"box_id":"B001","zone":"A"} または B001:A を解釈する。不可なら None。
    区画マーカー(ZONE:A など)は箱ではないので None。"""
    if not isinstance(text, str):
        return None
    if parse_zone_marker(text) is not None:
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


def locate(points, frame_shape, marker_size_m=None, hfov_deg=None):
    """QRの4隅(4x2, 画素)から画像内の位置を出す。
    offset: 画像中心からの水平ずれを -1.0〜+1.0 に正規化(右が正)。
    bearing: "left"/"center"/"right"(|offset|<=0.15 を center)。
    size_ratio: QRの辺の平均長 / 画像幅。
    distance_m: marker_size_m と hfov_deg が両方あるときだけ、ピンホール近似
      marker_size_m / (2*tan(hfov/2)*size_ratio) で推定。無ければ None。"""
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    width = float(frame_shape[1])
    cx = float(pts[:, 0].mean())
    offset = max(-1.0, min(1.0, (cx - width / 2.0) / (width / 2.0)))
    sides = [float(np.linalg.norm(pts[i] - pts[(i + 1) % len(pts)])) for i in range(len(pts))]
    size_ratio = (sum(sides) / len(sides)) / width
    if abs(offset) <= 0.15:
        bearing = "center"
    else:
        bearing = "right" if offset > 0 else "left"
    distance = None
    if marker_size_m and hfov_deg and size_ratio > 0 and 0 < hfov_deg < 180:
        distance = float(marker_size_m) / (2.0 * math.tan(math.radians(hfov_deg) / 2.0) * size_ratio)
    return {
        "offset": round(offset, 4),
        "bearing": bearing,
        "size_ratio": round(size_ratio, 4),
        "distance_m": None if distance is None else round(distance, 3),
    }


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
