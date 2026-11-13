#!/usr/bin/env python3
"""サンプル: 挨拶して、手を振り、少し前に歩いて止まる。

  モックで確認:  pixi run python scripts/mock_robot.py          （ターミナル1）
                 pixi run python scripts/my_script.py --domain 1 （ターミナル2）
  実機で実行:    pixi run python scripts/my_script.py -i <インターフェース名>

実機で動かす前に: コントローラーでロボットを Running Mode（LED 白）にしておく。
停止担当者を置き、周囲 2 m 以上を空ける。初回はスタンドに吊った状態で試す。
"""
import argparse
import time
from pathlib import Path

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

from r1_clients import FSM_RUN, R1LocoClient


def check(name: str, code) -> bool:
    """RPC の戻り値を表示する。0 が成功。"""
    ok = code == 0
    print(f"  {name}: {'OK' if ok else f'失敗 (code={code})'}")
    return ok


def walk(loco: R1LocoClient, vx: float, vy: float, vyaw: float, duration: float) -> None:
    """Move は 1 秒で失効するので、0.2 秒ごとに送り直して歩き続ける。"""
    start = time.time()
    while time.time() - start < duration:
        code = loco.Move(vx, vy, vyaw)
        if code != 0:
            print(f"  Move 失敗 (code={code})。歩行を中断する")
            return
        time.sleep(0.2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Unitree R1 greeting sample")
    parser.add_argument("-i", "--interface", default=None, help="ロボットにつないだネットワークインターフェース名")
    parser.add_argument("-d", "--domain", type=int, default=0, help="DDS ドメイン（0=実機, 1=モック）")
    parser.add_argument("--speed", type=float, default=0.2, help="前進速度 m/s")
    parser.add_argument("--seconds", type=float, default=2.0, help="前進する秒数")
    args = parser.parse_args()

    # -i 指定時に SDK が /tmp/cdds.LOG を書くため、出力先を用意する
    Path("/tmp").mkdir(exist_ok=True)
    ChannelFactoryInitialize(args.domain, args.interface)

    audio = AudioClient()
    audio.SetTimeout(10.0)
    audio.Init()

    loco = R1LocoClient()
    loco.SetTimeout(10.0)
    loco.Init()

    # DDS のディスカバリ完了を待つ
    time.sleep(1.0)

    # 1. 現在のモードを確認する。Running Mode でなければ歩行と手振りは行わない
    code, fsm_id = loco.GetFsmId()
    if code != 0:
        print(f"ロボットに接続できない (code={code})。配線・IP・インターフェース名・ドメインを確認する")
        return
    can_move = fsm_id == FSM_RUN
    print(f"現在のモード ID: {fsm_id}" + ("" if can_move else "（Running Mode ではないので、発話と LED のみ実行する）"))

    try:
        # 2. LED を緑にして挨拶する（speaker_id=1: 英語。日本語は非対応）
        print("挨拶")
        check("LedControl", audio.LedControl(0, 255, 0))
        check("TtsMaker", audio.TtsMaker("Hello! Nice to meet you.", 1))
        time.sleep(3.0)

        if can_move:
            # 3. 手を振る
            print("手を振る")
            check("WaveHand", loco.WaveHand())
            time.sleep(5.0)

            # 4. 少し前に歩く
            print(f"前進 {args.speed} m/s × {args.seconds} 秒")
            walk(loco, args.speed, 0.0, 0.0, args.seconds)
    finally:
        # 5. 例外や Ctrl+C でも必ず止め、LED を消す
        print("停止")
        check("StopMove", loco.StopMove())
        time.sleep(0.3)  # LedControl は 200 ms 以上の間隔を空ける
        check("LedControl", audio.LedControl(0, 0, 0))


if __name__ == "__main__":
    main()
