import argparse
import time
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient


def main():
    # コマンドライン引数のパーサーを設定
    parser = argparse.ArgumentParser(description="Unitree G1 TTS Sample Script")
    # ネットワークインターフェース指定用引数（必須）
    parser.add_argument("-i", "--interface", required=True, help="Network interface name (e.g., en7, eth0)")
    args = parser.parse_args()

    # 指定されたネットワークインターフェースでDDSチャンネルを初期化
    ChannelFactoryInitialize(0, args.interface)

    # AudioClientインスタンスの生成
    audio_client = AudioClient()
    # 応答待ちタイムアウトを10秒に設定
    audio_client.SetTimeout(10.0)
    # クライアントの初期化（送受信チャンネルの生成）
    audio_client.Init()

    # エンドポイントのディスカバリ完了を少し待機
    time.sleep(1.0)

    # 発話テキストの定義
    text = "Hello, Unitree robot is ready!"
    print(f"Sending TTS request: {text}")

    # 音声合成・再生APIの呼び出し（speaker_id=1: 英語音声）
    ret = audio_client.TtsMaker(text, 1)

    # 結果の判定とログ出力
    if ret == 0:
        print("TTS playback completed successfully.")
    else:
        print(f"Failed to play TTS, error code: {ret}")


if __name__ == "__main__":
    main()
