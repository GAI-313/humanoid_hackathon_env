import argparse
import time
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient


def walk(client: LocoClient, vx: float, vy: float, vyaw: float, duration: float) -> None:
    # 指定秒数の間、定期的に速度コマンドを送信して継続的に移動させる
    start_time = time.time()
    while time.time() - start_time < duration:
        # 速度指令を送信（デフォルトduration=1秒のため定期送信）
        client.Move(vx, vy, vyaw)
        # 次の送信まで待機
        time.sleep(0.2)


def main():
    # コマンドライン引数のパーサーを設定
    parser = argparse.ArgumentParser(description="Unitree G1 Walk Sample Script")
    # ネットワークインターフェース指定用引数（必須）
    parser.add_argument("-i", "--interface", required=True, help="Network interface name (e.g., en7, eth0)")
    args = parser.parse_args()

    # 指定されたネットワークインターフェースでDDSチャンネルを初期化
    ChannelFactoryInitialize(0, args.interface)

    # LocoClientインスタンスの生成
    loco_client = LocoClient()
    # 応答待ちタイムアウトを10秒に設定
    loco_client.SetTimeout(10.0)
    # クライアントの初期化（送受信チャンネルの生成）
    loco_client.Init()

    # エンドポイントのディスカバリ完了を少し待機
    time.sleep(1.0)

    # 1. X方向（前進）へ 0.4 m/s で 3秒間移動
    print("Move to forward.")
    walk(loco_client, 0.4, 0.0, 0.0, 3.0)

    # 2. Y方向（横移動）へ 0.4 m/s で 3秒間移動
    print("Move to left")
    walk(loco_client, 0.0, 0.4, 0.0, 3.0)

    # 3. Theta方向（旋回）へ 0.4 rad/s で 3秒間旋回
    print("Move to Clock wize.")
    walk(loco_client, 0.0, 0.0, 1.0, 3.0)

    # 4. 停止指令を送信
    print("Stop move...")
    loco_client.StopMove()


if __name__ == "__main__":
    main()
