# DDS トピック（状態の購読・腕の直接制御・低レベル制御）

R1 は G1 と同じ `unitree_hg` IDL を使う（`unitree_go` は Go2/B2/H1 用）。

## 目次

- [トピック一覧](#トピック一覧)
- [状態を読む（rt/lowstate）](#状態を読むrtlowstate)
- [リモコン入力を読む](#リモコン入力を読む)
- [関節番号](#関節番号)
- [腕を直接動かす（rt/arm_sdk）](#腕を直接動かすrtarm_sdk)
- [低レベル制御（rt/lowcmd）](#低レベル制御rtlowcmd)
- [OS ごとの制約](#os-ごとの制約)

## トピック一覧

| トピック | 型 | 向き | 内容 |
| --- | --- | --- | --- |
| `rt/lowstate` | `unitree_hg.msg.dds_.LowState_` | 購読 | 全関節・IMU・リモコン生データ（高頻度） |
| `rt/lf/lowstate` | 同上 | 購読 | 同じ内容の低頻度版。上流の G1 向けサンプルが使っているトピックで、R1 のマニュアルには記載が無い。届かなければ `rt/lowstate` を使う |
| `rt/lowcmd` | `unitree_hg.msg.dds_.LowCmd_` | 発行 | 全関節の直接制御。デバッグモード専用 |
| `rt/arm_sdk` | `unitree_hg.msg.dds_.LowCmd_` | 発行 | 歩行制御を残したまま上半身だけ制御 |
| `rt/arm/action/state` | `std_msgs.msg.dds_.String_` | 購読 | 腕プリセット動作の状態（JSON、10 Hz） |
| `rt/audio_msg` | `std_msgs.msg.dds_.String_` | 購読 | 音声認識結果・再生状態（JSON） |
| `rt/dex3/(left\|right)/cmd`, `/state` | `HandCmd_` / `HandState_` | 発行 / 購読 | Dex3-1 ハンド装着時のみ |
| `rt/api/<service>/request`, `/response` | `unitree_api.msg.dds_.Request_` / `Response_` | — | RPC の中身。通常はクライアントクラス経由で使う |

## 状態を読む（rt/lowstate）

読むだけならロボットのモードを問わず安全。

```python
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

latest = {}

def on_state(msg: LowState_):
    latest["msg"] = msg          # コールバックは受信スレッドで走る。重い処理はここでしない

sub = ChannelSubscriber("rt/lowstate", LowState_)
sub.Init(on_state, 10)           # 第 2 引数はキュー長

# 使う側
msg = latest.get("msg")
if msg is not None:
    roll, pitch, yaw = msg.imu_state.rpy
    q_left_elbow = msg.motor_state[18].q
```

`LowState_` の主なフィールド:

| フィールド | 内容 |
| --- | --- |
| `mode_pr` | 足首の制御モード（0: PR、1: AB） |
| `mode_machine` | 機種 ID。`LowCmd_` を送る時はこの値をそのまま写す |
| `tick` | 1 ms ごとに増えるカウンタ |
| `imu_state` | `quaternion[4]`(w,x,y,z)、`gyroscope[3]`、`accelerometer[3]`、`rpy[3]`、`temperature` |
| `motor_state[35]` | 各関節の `q`(rad)、`dq`(rad/s)、`ddq`、`tau_est`、`temperature[2]`、`vol`、`motorstate`（0 以外は異常） |
| `wireless_remote[40]` | リモコンの生データ |
| `crc` | チェックサム |

ハンドラを渡さず `sub.Init()` して `sub.Read(timeout)` でポーリングする書き方もある。

## リモコン入力を読む

`wireless_remote` の 40 バイトを分解する。「ボタンを押したら自作プログラムの動作を開始」のような使い方ができる。
ただしモード切替やエモーションに割り当て済みの組み合わせ（L2+…、R2+A、R1+…、SELECT+…、各ボタン 2 度押し）はロボット側も反応するので、トリガーには使わない。

```python
import struct

def parse_remote(data) -> dict:
    raw = bytes(data)
    b1, b2 = raw[2], raw[3]
    lx, rx, ry, _l2, ly = struct.unpack("<5f", raw[4:24])
    names1 = ["R1", "L1", "Start", "Select", "R2", "L2", "F1", "F2"]
    names2 = ["A", "B", "X", "Y", "Up", "Right", "Down", "Left"]
    keys = {n: (b1 >> i) & 1 for i, n in enumerate(names1)}
    keys.update({n: (b2 >> i) & 1 for i, n in enumerate(names2)})
    return {"lx": lx, "ly": ly, "rx": rx, "ry": ry, **keys}   # スティックは -1.0〜1.0
```

## 関節番号

`motor_cmd[]` / `motor_state[]` の添字（PR モード）。R1 標準機は 26 自由度で、腕は片側 5 自由度（手首はロールのみ）。

| 添字 | 関節 | 添字 | 関節 |
| --- | --- | --- | --- |
| 0 | 左 股関節ピッチ | 6 | 右 股関節ピッチ |
| 1 | 左 股関節ロール | 7 | 右 股関節ロール |
| 2 | 左 股関節ヨー | 8 | 右 股関節ヨー |
| 3 | 左 膝 | 9 | 右 膝 |
| 4 | 左 足首ピッチ（AB モードでは B） | 10 | 右 足首ピッチ（B） |
| 5 | 左 足首ロール（AB モードでは A） | 11 | 右 足首ロール（A） |
| 12 | 腰ロール | 13 | 腰ヨー |
| 14 | （未使用） | | |
| 15 | 左 肩ピッチ | 22 | 右 肩ピッチ |
| 16 | 左 肩ロール | 23 | 右 肩ロール |
| 17 | 左 肩ヨー | 24 | 右 肩ヨー |
| 18 | 左 肘 | 25 | 右 肘 |
| 19 | 左 手首ロール | 26 | 右 手首ロール |
| 20, 21 | （7 自由度腕のみ: 左 手首ピッチ / ヨー） | 27, 28 | （7 自由度腕のみ: 右 手首ピッチ / ヨー） |
| 29 | 頭ピッチ | 30 | 頭ヨー |

G1 とは腕の添字が違う（G1 は左腕 15–21、右腕 22–28 で腰が 12–14）。G1 用サンプルの関節表を流用しない。

## 腕を直接動かす（rt/arm_sdk）

プリセット動作で足りない時の手段。内蔵コントローラーが歩行とバランスを保ったまま、腕 10 関節・腰ヨー・頭 2 関節の計 13 関節を自分のプログラムで動かす。

**関節リミットも干渉チェックも一切無い。** 目標角は全て自分の責任。Python からの実装例は上流に無く（C++ の `r1_arm_sdk_dds_example.cpp` のみ）、以下は公式マニュアル arm_control_routine の仕様を Python に写したもので**実機未検証**。必ず吊った状態・小さい動きから試す。

- 発行: `rt/arm_sdk` に `LowCmd_`、**100 Hz**。
- 制御の重み: **R1 は `mode_pr` フィールドに 0〜100 を入れる**（= 重み 0.0〜1.0）。G1 は `motor_cmd[29].q` に 0〜1 を入れる方式で、互換性が無い。
- 対象の添字: 15–19（左腕）、22–26（右腕）、13（腰ヨー）、29・30（頭）。脚と腰ロールに書いても無視される。
- 出力トルク: `kp * (q目標 - q) + kd * (dq目標 - dq) + tau`。
- 推奨ゲイン（内蔵の腕動作サービスと同じ値）:

  | 関節 | kp | kd |
  | --- | --- | --- |
  | 肩ピッチ / ロール | 50 | 2 |
  | 肩ヨー / 肘 | 40 | 2 |
  | 手首ロール | 30 | 2 |
  | 腰ヨー | 50 | 3 |
  | 頭ピッチ / ヨー | 15 | 1 |

手順:

1. **引き継ぎ**: `rt/lowstate` を受信してから、全対象関節の `q` を**現在の実測値**で初期化し、ゲインを書き、重みを 100 にする。いきなり離れた目標を入れない。
2. **指令**: 100 Hz で目標角を補間しながら送り続ける。`motor_state[i].motorstate != 0` を見たら即座に解放する。
3. **解放**: 重みを 100 → 0 へ**約 1 秒かけて**線形に下げる（その間も 100 Hz で発行）。一気に 0 にしない。

```python
import threading, time
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.utils.crc import CRC

JOINTS = [15, 16, 17, 18, 19, 22, 23, 24, 25, 26, 13, 29, 30]
KP = [50, 50, 40, 40, 30, 50, 50, 40, 40, 30, 50, 15, 15]
KD = [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 1, 1]
DT = 0.01

class ArmSdk:
    def __init__(self):
        self.state = None
        self.cmd = unitree_hg_msg_dds__LowCmd_()
        self.crc = CRC()
        self.pub = ChannelPublisher("rt/arm_sdk", LowCmd_)
        self.pub.Init()
        self.sub = ChannelSubscriber("rt/lowstate", LowState_)
        self.sub.Init(lambda m: setattr(self, "state", m), 10)

    def _publish(self, weight: float):
        self.cmd.mode_pr = int(round(max(0.0, min(1.0, weight)) * 100))
        self.cmd.crc = self.crc.Crc(self.cmd)
        self.pub.Write(self.cmd)

    def enable(self):
        while self.state is None:
            time.sleep(0.1)
        for j, kp, kd in zip(JOINTS, KP, KD):
            m = self.cmd.motor_cmd[j]
            m.q, m.dq, m.tau, m.kp, m.kd = self.state.motor_state[j].q, 0.0, 0.0, float(kp), float(kd)
        self._publish(1.0)

    def movej(self, q_target, duration: float):
        """q_target は JOINTS と同じ順の 13 要素（rad）。duration 秒かけて線形補間。"""
        q0 = [self.cmd.motor_cmd[j].q for j in JOINTS]
        t0, r = time.time(), 0.0
        while r < 1.0:                       # 経過時間で補間するので、送信周期がずれても所要時間は変わらない
            r = min(1.0, (time.time() - t0) / duration)
            for j, a, b in zip(JOINTS, q0, q_target):
                self.cmd.motor_cmd[j].q = a + (b - a) * r
            self._publish(1.0)
            time.sleep(DT)

    def hold(self, duration: float):
        t0 = time.time()
        while time.time() - t0 < duration:   # 止まっている間も送り続ける
            self._publish(1.0)
            time.sleep(DT)

    def release(self, duration: float = 1.0):
        t0, r = time.time(), 0.0
        while r < 1.0:
            r = min(1.0, (time.time() - t0) / duration)
            self._publish(1.0 - r)
            time.sleep(DT)
```

使う時は `enable()` → `movej(...)` / `hold(...)` → `finally: release()`。腕プリセット動作 API と同時には使えない（7400）。

送信周期の実測（この Windows 環境、ロボットなし）: `time.sleep(0.01)` の粒度と純 Python の CRC（1 回約 2 ms）のため、実際の発行は約 55 Hz にとどまった。公式の要求は 100 Hz なので、arm_sdk を本気で使うなら Linux で動かす（CRC がネイティブ実装になり、sleep の粒度も細かい）。

## 低レベル制御（rt/lowcmd）

全関節を自分で制御する。**ハッカソンでは原則使わない。** 内蔵コントローラーを止めるためロボットは自立できず、高レベル API（歩行・腕動作）も全て無効になる。使うなら吊った状態で。

流れ（上流 `example/r1/low_level/r1_low_level_example.py`）:

1. `MotionSwitcherClient` で `CheckMode()` し、`result["name"]` が空になるまで `ReleaseMode()` を繰り返す（デバッグモードに入る）。
2. `rt/lowstate` を受信して `mode_machine` を控える。
3. `rt/lowcmd` に 500 Hz（2 ms）で `LowCmd_` を発行する。各関節に `mode=1`（有効）、`q` `dq` `tau` `kp` `kd` を入れ、`mode_pr`（0: PR、1: AB）、`mode_machine`（受信した値）、`crc` を設定する。最初の数秒は現在角から目標角へ補間する。

上流サンプルのゲイン: 脚 kp 200 / kd 3、腰 300 / 5、腕 100 / 2（手首 50 / 2）、頭ピッチ 50 / 2、頭ヨー 10 / 0.1。
足首は並行リンク機構で、PR モードはピッチ / ロール角（URDF と一致）、AB モードはモーター A / B を直接指定する。
元に戻すにはロボットの再起動、または `MotionSwitcherClient.SelectMode("ai")`（上流サンプルの値。R1 での名前は `CheckMode()` の戻り値で確認する）。

## OS ごとの制約

| 項目 | Linux | Windows / macOS |
| --- | --- | --- |
| RPC クライアント、購読・発行 | ○ | ○ |
| `unitree_sdk2py.utils.thread.RecurrentThread` | ○ | × import 時に `TypeError`。`threading.Thread` + `time.sleep` で代替 |
| `CRC().Crc()` | ネイティブ（速い） | 純 Python（約 2 ms / 回）。500 Hz の低レベル制御には実質使えない |
| 上流の low_level / arm_sdk サンプル | そのまま動く | `RecurrentThread` を使うためそのままでは動かない |

公式マニュアルは開発 OS として Ubuntu 20.04 のみを挙げている（Windows / macOS は非対応と明記）。このリポジトリの pixi 環境で高レベル API と購読が Windows で動くことは確認済みだが、周期の厳しい制御は Linux で行う。
