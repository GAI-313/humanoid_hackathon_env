---
name: unitree-r1-sdk
description: Unitree R1（G1 系含む）ヒューマノイドを unitree_sdk2py で動かす Python スクリプトの書き方。歩行・モード切替（LocoClient）、腕のプリセット動作、TTS・音声再生・LED、LowState 購読、arm_sdk、実機なしでのテスト（モック／MuJoCo）を扱う。scripts/ や samples/ にロボット制御コードを書く・直す・レビューする・動作確認する時、「ロボットを歩かせたい／喋らせたい／手を振らせたい」「シミュレーターで試したい」といった依頼の時に使う。
---

# Unitree R1 SDK（unitree_sdk2py）

このリポジトリは R1 実機に開発 PC から DDS でコマンドを送る環境。コードは必ず開発 PC で実行する（ロボット内蔵 PC は使用禁止）。

出典: 公式 R1 開発者マニュアル（support.unitree.com/home/en/R1_developer）、unitree_sdk2_python（コミット 814556d）、ハッカソン運用ガイド（docs/）。実機での確認が取れていない項目は「未検証」と明記してある。

## 最初に知っておくこと

1. **`unitree_sdk2py.r1` は import できない。** 上流リポジトリには `r1/loco/r1_loco_client.py` があるが `__init__.py` が無く、pip インストールから漏れる。R1 用クライアントは [assets/r1_clients.py](assets/r1_clients.py) を `scripts/r1_clients.py` にコピーして使う（`scripts/` に無ければコピーする）。
2. **G1 用クライアントを R1 にそのまま使える範囲は限られる。**

   | やりたいこと | 使うもの | 注意 |
   | --- | --- | --- |
   | 歩行 `Move` / `StopMove`、`WaveHand`、`ShakeHand`、`Damp`、`ZeroTorque` | `R1LocoClient`（G1 の `LocoClient` でも同じ API ID なので動く） | |
   | `Start`、起き上がり、Locked Stand | **`R1LocoClient` のみ** | G1 版は FSM ID が違う。G1 の `Lie2StandUp()` は 702 を送り、R1 では「立位→仰向け」になる |
   | 腕のプリセット動作 | **`R1ArmActionClient` のみ** | G1 版はパラメータ形式もアクション ID 表も違う |
   | TTS・音量・LED・音声再生 | `unitree_sdk2py.g1.audio.g1_audio_client.AudioClient` | 公式も R1 で G1 の AudioClient を使っている |

3. **Windows / macOS では `unitree_sdk2py.utils.thread`（`RecurrentThread`）が import 時に落ちる**（Linux の timerfd 依存）。周期処理は `threading` + `time.sleep` で書く。上流の low_level / arm_sdk サンプルはそのままでは Linux 専用。
4. **実機は DDS ドメイン 0。** テスト用のモックやシミュレーターはドメイン 1 を使う。

## スクリプトの型

`scripts/template.py` を複製して始める。新規スクリプトは `--domain` も受け取るようにしておくと、同じコードを実機（0）とモック（1）の両方で動かせる。

```python
#!/usr/bin/env python3
import argparse
import time
from pathlib import Path

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from r1_clients import R1LocoClient  # scripts/r1_clients.py


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interface", default=None, help="ロボットにつないだ NIC 名")
    parser.add_argument("-d", "--domain", type=int, default=0, help="0=実機, 1=モック")
    args = parser.parse_args()

    Path("/tmp").mkdir(exist_ok=True)           # -i 指定時に SDK が /tmp/cdds.LOG を書く（Windows は C:\tmp）
    ChannelFactoryInitialize(args.domain, args.interface)  # プロセス内で 1 回だけ有効

    loco = R1LocoClient()
    loco.SetTimeout(10.0)
    loco.Init()
    time.sleep(1.0)                              # DDS ディスカバリ待ち。省くと最初の呼び出しが失敗する

    try:
        t0 = time.time()
        while time.time() - t0 < 3.0:            # Move は 1 秒で失効するので 0.2 秒ごとに再送
            loco.Move(0.3, 0.0, 0.0)
            time.sleep(0.2)
    finally:
        loco.StopMove()                          # 例外・Ctrl+C でも必ず止める


if __name__ == "__main__":
    main()
```

守ること:

- クライアントは `SetTimeout()` → `Init()` → 約 1 秒待つ、の順。
- 戻り値（0 が成功）を確認する。上流 G1 `LocoClient` の `Move()` などは戻り値を返さない（常に `None`）ので、結果を見たい時は `SetVelocity()` / `SetFsmId()` を直接呼ぶか `R1LocoClient` を使う。
- 動きを伴う処理は `try/finally` で `StopMove()`（腕なら `ReleaseArm()`）を保証する。
- `Move(..., continous_move=True)` は 10 日間有効な速度指令になる。プログラムが落ちても歩き続けるので使わない。
- 実行は `pixi run python scripts/<name>.py -i <iface>`。インターフェース名は Linux `ip a`、macOS `ifconfig`、Windows `Get-NetAdapter` の Name 列（192.168.123.164 を設定したアダプタ）。

## 何を読むか

| 目的 | 参照 |
| --- | --- |
| 歩行・モード切替・腕プリセット・音声/LED の API、エラーコード | [reference/high-level-api.md](reference/high-level-api.md) |
| `rt/lowstate` 購読、リモコン入力、関節番号、`rt/arm_sdk` による腕の直接制御、低レベル制御 | [reference/low-level-dds.md](reference/low-level-dds.md) |
| 実機なしのテスト（モック、unitree_mujoco） | [reference/simulation.md](reference/simulation.md) |

## 安全（ハッカソン運用ガイドの必須事項）

コードを書く・実行を勧める時は以下を前提にする。実機を動かすコマンドをユーザーに案内する時は、該当する項目を一言添える。

- **2 名体制**: 実行者とは別に、コントローラーを持った停止担当を置く。緊急停止は底面の Emergency Stop ボタン、無ければ `L2 + B` を 5 秒以上長押し。
- **初めて動かすコード・未検証パラメータは、ロボットをスタンド／ガントリーに吊った状態で試す。** 接地で動かすなら周囲 2 m 以上を空ける。先にモックで引数と順序を確認しておく。
- **立っているロボットに `Damp()` / `ZeroTorque()` を送らない。** バランス制御が切れて倒れる。停止は `StopMove()`。
- **ダンス・カンフー等のアクロバット動作は会場で全面禁止。** 公開されていない FSM ID を `SetFsmId()` で試さない（使うのは 0 / 1 / 4 / 701 / 702 / 811 のみ）。
- **デバッグモード（低レベル制御）は内蔵コントローラーが完全に止まる。** 必ず吊った状態で行う。ハッカソンの通常用途は高レベル API で足りる。
- 歩行速度は小さく始める（既存サンプルは 0.4 m/s、旋回 1.0 rad/s）。腕の動作中は歩行できない。
- 胸の LED が黄緑点滅 = バッテリー低下。作業を止めて、寝かせるか吊って Zero Torque にしてから電源を切る。

## 変えてはいけないもの

`cyclonedds==0.10.2` と Python 3.10 の固定（実機と型ハッシュが合わなくなる）。インターフェースは環境変数や XML ではなく `ChannelFactoryInitialize(domain, iface)` の引数で渡す。
