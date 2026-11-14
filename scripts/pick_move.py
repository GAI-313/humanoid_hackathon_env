#!/usr/bin/env python3
"""担当A: ロボット制御モジュール (scripts/pick_move.py)

Unitree R1 / G1 の高レベル制御スクリプト:
- 移動制御 (R1LocoClient): 区画A/Bへの移動、スタート地点への復帰、安全停止
- 腕プリセット動作 (R1ArmActionClient): 区画の指し示し (ID 31)、完了手振り (ID 25)、初期姿勢復帰 (ID 99)
- 音声合成 (AudioClient): 状態変化の英語アナウンス (speaker_id=1)
- 可視化ツール連携: C 担当のダッシュボード (http://<host>:8000/events) へのイベント通知

実行モード:
- ドライラン (DDS 通信なし): python scripts/pick_move.py --dry-run --zone A
- モック環境 (PC 単体):      python scripts/pick_move.py --domain 1 --zone A
- 実機環境 (当日):          python scripts/pick_move.py --domain 0 -i Ethernet --zone A
- 対話型デバッグモード:       python scripts/pick_move.py --dry-run --interactive
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

# scripts/ ディレクトリを sys.path に追加して r1_clients を参照可能にする
sys.path.append(str(Path(__file__).parent))


class EventReporter:
    """可視化ツール (C 担当) へのイベント送信を担当するクラス。

    送信先サーバーが起動していなくても処理をブロック・停止させず、安全にスキップします。
    """

    def __init__(self, endpoint_url: str = "http://127.0.0.1:8000/events", enabled: bool = True):
        self.endpoint_url = endpoint_url
        self.enabled = enabled

    def send(self, event_type: str, box_id: str, zone: str, detail: str = "") -> dict:
        """イベント JSON を生成して送信する。

        形式:
        {
          "ts": "2026-11-15T10:30:00",
          "robot": "R1",
          "event": "scanned | moving | arrived | error",
          "box_id": "B001",
          "zone": "A",
          "detail": "任意メッセージ"
        }
        """
        payload = {
            "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "robot": "R1",
            "event": event_type,
            "box_id": box_id,
            "zone": zone,
            "detail": detail,
        }

        print(f"[Event] ({event_type.upper()}) Box:{box_id} -> Zone:{zone} | {detail}")

        if not self.enabled:
            return payload

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.endpoint_url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            # タイムアウト 0.5 秒で非同期的・安全に送信
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                pass
        except (urllib.error.URLError, TimeoutError, OSError):
            # ダッシュボードサーバーが未起動の場合は何もしない（開発を妨げない）
            pass

        return payload


class PickRobotController:
    """R1 ロボットのピッキング・分類移動および腕動作を管理するコントローラー。"""

    def __init__(
        self,
        interface: str | None = None,
        domain: int = 1,
        dry_run: bool = False,
        event_url: str = "http://127.0.0.1:8000/events",
    ):
        self.interface = interface
        self.domain = domain
        self.dry_run = dry_run
        self.reporter = EventReporter(endpoint_url=event_url, enabled=not dry_run)

        self.loco = None
        self.arm = None
        self.audio = None

        if not self.dry_run:
            self._init_sdk()

    def _init_sdk(self) -> None:
        """Unitree SDK2 チャンネルおよび各サービスクライアントを初期化する。"""
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient
        from r1_clients import R1ArmActionClient, R1LocoClient

        try:
            Path("/tmp").mkdir(exist_ok=True)
        except OSError:
            pass

        print(f"[Init] Initializing ChannelFactory (domain={self.domain}, iface={self.interface})...")
        ChannelFactoryInitialize(self.domain, self.interface)

        print("[Init] Connecting to R1 Loco, Arm, and Audio services...")
        self.loco = R1LocoClient()
        self.loco.SetTimeout(5.0)
        self.loco.Init()

        self.arm = R1ArmActionClient()
        self.arm.SetTimeout(5.0)
        self.arm.Init()

        self.audio = AudioClient()
        self.audio.SetTimeout(5.0)
        self.audio.Init()

        # DDS エンドポイントのディスカバリ完了を少し待機
        time.sleep(1.0)
        print("[Init] All services ready.")

    # ------------------------------------------------------------- 音声 (TTS)
    def speak(self, text: str) -> None:
        """英語音声 (speaker_id=1) で発話する。"""
        print(f"[TTS] >> \"{text}\"")
        if self.dry_run or self.audio is None:
            return
        try:
            self.audio.TtsMaker(text, 1)
        except Exception as e:
            print(f"[TTS Warning] {e}")

    # ------------------------------------------------------------- 移動制御
    def move_velocity(self, vx: float, vy: float, vyaw: float) -> None:
        """速度指令を送信する（有効時間 約1秒）。"""
        if self.dry_run or self.loco is None:
            return
        self.loco.Move(vx, vy, vyaw)

    def stop(self) -> None:
        """安全停止指令を送信する。"""
        print("[Motion] StopMove called.")
        if self.dry_run or self.loco is None:
            return
        self.loco.StopMove()

    def walk(self, vx: float, vy: float, vyaw: float, duration: float) -> None:
        """指定秒数の間、速度コマンドを 0.2 秒周期で再送して安全に移動させる。"""
        print(f"[Motion] Walk vx={vx:+.2f} vy={vy:+.2f} vyaw={vyaw:+.2f} for {duration:.1f}s")
        if self.dry_run:
            time.sleep(min(duration, 1.0) if duration > 0 else 0)  # テスト短縮用
            return

        t_end = time.time() + duration
        while time.time() < t_end:
            self.move_velocity(vx, vy, vyaw)
            time.sleep(0.2)
        self.stop()

    # ------------------------------------------------------------- 腕動作
    def execute_arm_action(self, action_id: int, action_name: str, duration: float = 2.0) -> None:
        """腕プリセット動作を実行する。動作中は歩行しないこと。"""
        print(f"[Arm] Execute action ID {action_id}: {action_name}")
        if self.dry_run or self.arm is None:
            time.sleep(0.5)
            return

        try:
            ret = self.arm.ExecuteAction(action_id)
            if ret != 0:
                print(f"[Arm Warning] ExecuteAction returned code {ret}")
            time.sleep(duration)
        except Exception as e:
            print(f"[Arm Error] {e}")

    def point_zone(self) -> None:
        """右腕を前に伸ばして区画を指し示す (ID 31: extend_right_arm_forward)。"""
        self.execute_arm_action(31, "extend_right_arm_forward (Pointing zone)", duration=1.5)

    def wave_hand(self) -> None:
        """完了表現として胸の前で手を振る (ID 25: wave_under_head)。"""
        self.execute_arm_action(25, "wave_under_head (Task Completed)", duration=2.5)

    def release_arm(self) -> None:
        """腕の保持を解除し、初期姿勢に戻す (ID 99: release_arm)。"""
        self.execute_arm_action(99, "release_arm (Return to home pose)", duration=1.0)

    # ------------------------------------------------------------- メインシーケンス
    def go_to(self, zone: str, box_id: str = "B001", return_home: bool = False) -> None:
        """目的地（区画A / B / C / HOME）へ移動し、腕で指し示して完了を報告する。

        Args:
            zone: 目標区画 ("A", "B", "C", "HOME")
            box_id: 箱ID (例: "B001")
            return_home: 完了後に初期位置（スタート地点）へ戻るかどうか
        """
        zone_norm = zone.strip().upper()
        if zone_norm.startswith("ZONE_"):
            zone_clean = zone_norm.replace("ZONE_", "")
        else:
            zone_clean = zone_norm

        print(f"\n=======================================================")
        print(f"[*] Mission Start: Moving Box '{box_id}' to Zone '{zone_clean}'")
        print(f"=======================================================")

        # 1. 移動開始イベント送信 & 発話
        self.reporter.send("moving", box_id, zone_clean, f"Starting move to Zone {zone_clean}")
        self.speak(f"Moving box {box_id} to zone {zone_clean}.")
        time.sleep(0.5)

        try:
            # 2. 区画ごとの移動軌道（速度は安全のため 0.25 m/s 程度に設定）
            if zone_clean == "A":
                # 区画 A: 直進
                print("[Mission] Route A: Move forward 2.5 meters (approx 8.0s)")
                self.walk(vx=0.25, vy=0.0, vyaw=0.0, duration=4.0)

            elif zone_clean == "B":
                # 区画 B: 直進 ➜ 右旋回 ➜ 前進
                print("[Mission] Route B: Forward -> Turn Right -> Forward")
                self.walk(vx=0.25, vy=0.0, vyaw=0.0, duration=3.0)
                self.walk(vx=0.0, vy=0.0, vyaw=-0.5, duration=2.0)
                self.walk(vx=0.25, vy=0.0, vyaw=0.0, duration=2.0)

            elif zone_clean == "C":
                # 区画 C: 直進 ➜ 左旋回 ➜ 前進
                print("[Mission] Route C: Forward -> Turn Left -> Forward")
                self.walk(vx=0.25, vy=0.0, vyaw=0.0, duration=3.0)
                self.walk(vx=0.0, vy=0.0, vyaw=0.5, duration=2.0)
                self.walk(vx=0.25, vy=0.0, vyaw=0.0, duration=2.0)

            elif zone_clean == "HOME":
                # スタート地点へ後退
                print("[Mission] Route HOME: Returning to base")
                self.walk(vx=-0.25, vy=0.0, vyaw=0.0, duration=3.0)

            else:
                # 未知の区画: エラーイベント送信
                self.reporter.send("error", box_id, zone_clean, f"Unknown target zone: {zone_clean}")
                self.speak("Error. Unknown destination zone.")
                return

            # 3. 到着
            self.stop()
            print(f"[Mission] Arrived at Zone {zone_clean}.")
            self.reporter.send("arrived", box_id, zone_clean, f"Arrived at Zone {zone_clean}")
            self.speak(f"Arrived at zone {zone_clean}. Sorting completed.")
            time.sleep(1.0)

            # 4. 腕アクション（区画の指し示し ➜ 解除 ➜ 手振り ➜ 姿勢解除）
            # ※ R1 仕様: 姿勢保持アクション(ID 31等)の後に別アクションを呼ぶと 7401 エラーになるため、
            # 連続動作の間には必ず release_arm(ID 99) を挟む。
            print("[Mission] Performing presentation arm gestures...")
            self.point_zone()
            time.sleep(1.0)
            self.release_arm()
            time.sleep(0.5)
            self.wave_hand()
            time.sleep(0.5)
            self.release_arm()

            # 5. オプション: スタート地点への帰還
            if return_home:
                print("[Mission] Returning to start position...")
                self.speak("Returning to start position.")
                # 簡易的な反転・復帰シーケンス（現場レイアウトに合わせて調整可能）
                self.walk(vx=0.0, vy=0.0, vyaw=1.0, duration=3.14)  # 180度旋回
                self.walk(vx=0.25, vy=0.0, vyaw=0.0, duration=4.0)
                self.walk(vx=0.0, vy=0.0, vyaw=1.0, duration=3.14)
                self.stop()

        finally:
            # 異常終了時でも必ず停止と腕解除を行う
            self.stop()
            self.release_arm()
            print(f"[*] Mission Finished safely.\n")


def interactive_loop(controller: PickRobotController) -> None:
    """現場やテストで即座に動作確認できる対話型コマンドループ。"""
    print("\n--- PickRobotController Interactive Mode ---")
    print("Commands:")
    print("  a      : Go to Zone A")
    print("  b      : Go to Zone B")
    print("  c      : Go to Zone C")
    print("  home   : Return to start")
    print("  point  : Test Pointing Arm (ID 31)")
    print("  wave   : Test Waving Arm (ID 25)")
    print("  release: Release Arm to Home Pose (ID 99)")
    print("  stop   : Emergency StopMove")
    print("  q      : Quit")
    print("--------------------------------------------\n")

    while True:
        try:
            cmd = input("Command [a/b/c/home/point/wave/release/stop/q] > ").strip().lower()
            if not cmd:
                continue
            if cmd == "q":
                break
            elif cmd == "a":
                controller.go_to("A", "BOX-DEBUG")
            elif cmd == "b":
                controller.go_to("B", "BOX-DEBUG")
            elif cmd == "c":
                controller.go_to("C", "BOX-DEBUG")
            elif cmd == "home":
                controller.go_to("HOME", "BOX-DEBUG")
            elif cmd == "point":
                controller.point_zone()
            elif cmd == "wave":
                controller.wave_hand()
            elif cmd == "release":
                controller.release_arm()
            elif cmd == "stop":
                controller.stop()
            else:
                print(f"Unknown command: {cmd}")
        except KeyboardInterrupt:
            print("\nInterrupted.")
            controller.stop()
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Unitree R1 Pick & Place / Sorting Controller (Role A)")
    parser.add_argument("-z", "--zone", type=str, default=None, help="Target zone (A, B, C, HOME)")
    parser.add_argument("-b", "--box", type=str, default="B001", help="Box ID (default: B001)")
    parser.add_argument("--return-home", action="store_true", help="Automatically return to start position")

    # 通信・環境設定
    parser.add_argument("-i", "--interface", default=None, help="Network interface (default: auto, use 'Ethernet' on robot)")
    parser.add_argument("-d", "--domain", type=int, default=1, help="DDS domain (0: real robot, 1: mock)")
    parser.add_argument("--dry-run", action="store_true", help="Run without DDS / robot connection (offline syntax/logic test)")
    parser.add_argument("--event-url", type=str, default="http://127.0.0.1:8000/events", help="Dashboard event endpoint URL")

    # デバッグ用モード
    parser.add_argument("--interactive", action="store_true", help="Start interactive CLI command mode")

    args = parser.parse_args()

    controller = PickRobotController(
        interface=args.interface,
        domain=args.domain,
        dry_run=args.dry_run,
        event_url=args.event_url,
    )

    if args.interactive:
        interactive_loop(controller)
    elif args.zone:
        controller.go_to(zone=args.zone, box_id=args.box, return_home=args.return_home)
    else:
        print("No zone specified. Running default demo with Zone A (dry-run mode if not connected)...")
        # zone が未指定の場合はデフォルトで Zone A をテスト
        controller.go_to(zone="A", box_id=args.box, return_home=args.return_home)


if __name__ == "__main__":
    main()
