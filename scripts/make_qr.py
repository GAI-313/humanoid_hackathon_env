#!/usr/bin/env python3
"""箱用のQR画像を作る。

例:
  python scripts/make_qr.py --box-id B001 --zone A
  python scripts/make_qr.py --box-id B001 B002 --zone A B      # 組にして複数作成
  python scripts/make_qr.py --zone-marker A B                  # 区画マーカー(中身は ZONE:A)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np


def encode_qr(text: str, size: int = 600, margin_ratio: float = 0.1):
    """text をQRにした BGR 画像(白余白付き、size x size)を返す。"""
    enc = cv2.QRCodeEncoder.create()
    qr = enc.encode(text)
    if qr is None or qr.size == 0:
        raise ValueError(f"QRを生成できません: {text!r}")
    if qr.ndim == 2:
        qr = cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR)
    inner = int(size * (1 - 2 * margin_ratio))
    qr = cv2.resize(qr, (inner, inner), interpolation=cv2.INTER_NEAREST)
    pad = (size - inner) // 2
    canvas = np.full((size, size, 3), 255, np.uint8)
    canvas[pad:pad + inner, pad:pad + inner] = qr
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description="box_id と zone からQR画像を作る")
    parser.add_argument("--box-id", nargs="+", default=[], help="箱ID(複数可)")
    parser.add_argument("--zone", nargs="+", default=[],
                        help="分類先(box-id と同数、または1つだけ指定して全箱に適用)")
    parser.add_argument("--zone-marker", nargs="+", default=[],
                        help="区画マーカーを作る zone(複数可。ZONE_A.png のように出力、中身は ZONE:A)")
    parser.add_argument("--size", type=int, default=600, help="画像の一辺(px)")
    parser.add_argument("--out-dir", type=str, default="work/qr", help="出力先フォルダ")
    args = parser.parse_args()

    if not args.box_id and not args.zone_marker:
        parser.error("--box-id と --zone、または --zone-marker を指定してください")
    if args.box_id and len(args.zone) not in (1, len(args.box_id)):
        parser.error("--zone は1つか --box-id と同数で指定してください")
    zones = args.zone * len(args.box_id) if len(args.zone) == 1 else args.zone
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for zone in args.zone_marker:
        text = f"ZONE:{zone.upper()}"
        path = out_dir / f"ZONE_{zone.upper()}.png"
        cv2.imwrite(str(path), encode_qr(text, args.size))
        print(f"{path}  {text}")
    for box, zone in zip(args.box_id, zones):
        text = json.dumps({"box_id": box, "zone": zone.upper()}, separators=(",", ":"))
        path = out_dir / f"{box}_{zone.upper()}.png"
        cv2.imwrite(str(path), encode_qr(text, args.size))
        print(f"{path}  {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
