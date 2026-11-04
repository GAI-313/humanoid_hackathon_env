#!/usr/bin/env python3
"""Unitree SDK2 Python を用いてロボットに任意のテキストを発話（TTS）させるサンプルスクリプト．"""

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

from pathlib import Path
from typing import Optional
import argparse
import platform
import sys


def ensure_cyclonedds_log_dir(network_interface: Optional[str]) -> None:
    """Windows 環境等でネットワークインターフェース指定時に CycloneDDS ログ出力先を確保する．

    Parameters
    ----------
    network_interface : Optional[str]
        指定されたネットワークインターフェース名．None の場合は自動検出設定が使われる．
    """
    if network_interface is not None and platform.system() == "Windows":
        log_dir = Path("/tmp")
        if not log_dir.exists():
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass


def create_audio_client(
    domain_id: int = 0,
    network_interface: Optional[str] = None,
    timeout: float = 10.0,
) -> AudioClient:
    """DDS チャネルおよび AudioClient を初期化して返す．

    Parameters
    ----------
    domain_id : int, default 0
        DDS ドメイン ID．
    network_interface : Optional[str], default None
        ロボットと接続しているネットワークインターフェース名（例: 'eth0', 'enp2s0', 'en0'）．
        None の場合は CycloneDDS の自動検出（autodetermine）を使用する．
    timeout : float, default 10.0
        RPC 呼び出しのタイムアウト秒数．

    Returns
    -------
    AudioClient
        初期化済みの AudioClient インスタンス．
    """
    ensure_cyclonedds_log_dir(network_interface)
    ChannelFactoryInitialize(domain_id, network_interface)

    client = AudioClient()
    client.SetTimeout(timeout)
    client.Init()
    return client


def speak_text(
    client: AudioClient,
    text: str,
    speaker_id: int = 0,
    volume: Optional[int] = None,
) -> int:
    """指定されたテキストをロボットに発話させる．

    Parameters
    ----------
    client : AudioClient
        初期化済みの AudioClient インスタンス．
    text : str
        発話させるテキスト．
    speaker_id : int, default 0
        話者 ID（デフォルト: 0）．
    volume : Optional[int], default None
        発話前に設定する音量（0〜100）．None の場合は現在の音量を維持する．

    Returns
    -------
    int
        RPC 呼び出しの終了コード（0 が成功）．
    """
    if volume is not None:
        clamped_volume = max(0, min(100, volume))
        vol_code = client.SetVolume(clamped_volume)
        if vol_code != 0:
            print(f"[Warn] Failed to set volume (code={vol_code})", file=sys.stderr)
        else:
            print(f"[Info] Volume set to {clamped_volume}")

    # g1_audio_client.AudioClient.TtsMaker 内の tts_index 更新バグ（0 += 0）を補完するため明示的に加算
    code = client.TtsMaker(text, speaker_id)
    client.tts_index += 1
    return code


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する．

    Returns
    -------
    argparse.Namespace
        解析されたコマンドライン引数．
    """
    parser = argparse.ArgumentParser(
        description="Unitree SDK2 Python を用いてロボットに任意のテキストを発話（TTS）させるサンプル．",
    )
    parser.add_argument(
        "text_pos",
        nargs="?",
        default=None,
        help="発話させるテキスト（位置引数，または -t / --text で指定可能）",
    )
    parser.add_argument(
        "-t",
        "--text",
        type=str,
        default=None,
        help="発話させるテキスト",
    )
    parser.add_argument(
        "-i",
        "--interface",
        type=str,
        default=None,
        help="ロボット接続用ネットワークインターフェース名（例: enp2s0, eth0, en0．省略時は自動検出）",
    )
    parser.add_argument(
        "-d",
        "--domain-id",
        type=int,
        default=0,
        help="DDS ドメイン ID（デフォルト: 0）",
    )
    parser.add_argument(
        "-s",
        "--speaker-id",
        type=int,
        default=0,
        help="話者 ID（デフォルト: 0）",
    )
    parser.add_argument(
        "-v",
        "--volume",
        type=int,
        default=None,
        help="発話前に設定するスピーカー音量（0〜100，省略時は変更しない）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="RPC 通信のタイムアウト秒数（デフォルト: 10.0）",
    )
    return parser.parse_args()


def main() -> int:
    """エントリーポイント関数．

    Returns
    -------
    int
        プロセスの終了ステータスコード．
    """
    args = parse_args()
    target_text = args.text if args.text is not None else args.text_pos

    print(
        f"[Info] Initializing DDS (domain_id={args.domain_id}, "
        f"interface={args.interface or 'auto'})..."
    )
    try:
        audio_client = create_audio_client(
            domain_id=args.domain_id,
            network_interface=args.interface,
            timeout=args.timeout,
        )
    except Exception as exc:
        print(f"[Error] Failed to initialize AudioClient: {exc}", file=sys.stderr)
        return 1

    # 単発テキスト指定モード
    if target_text is not None:
        print(f"[Info] Sending TTS: {target_text!r} (speaker_id={args.speaker_id})")
        code = speak_text(
            client=audio_client,
            text=target_text,
            speaker_id=args.speaker_id,
            volume=args.volume,
        )
        if code == 0:
            print("[Info] TTS command succeeded.")
            return 0
        print(f"[Error] TTS command failed with code: {code}", file=sys.stderr)
        return code

    # テキスト未指定時は対話モードで連続発話
    if args.volume is not None:
        clamped_volume = max(0, min(100, args.volume))
        audio_client.SetVolume(clamped_volume)

    print("[Info] Interactive TTS mode. Type text and press Enter (Ctrl+D or 'exit' to quit).")
    try:
        while True:
            line = input("TTS> ").strip()
            if not line:
                continue
            if line.lower() in {"exit", "quit"}:
                break
            code = speak_text(
                client=audio_client,
                text=line,
                speaker_id=args.speaker_id,
            )
            if code == 0:
                print("[Info] Sent successfully.")
            else:
                print(f"[Error] TTS failed (code={code})", file=sys.stderr)
    except (EOFError, KeyboardInterrupt):
        print("\n[Info] Exiting interactive TTS mode.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
