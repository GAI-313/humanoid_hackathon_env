# 高レベル API（RPC サービス）

高レベル API は内蔵コントローラー（ai_sport）に依存する。ロボットがデバッグモードの時は全て無効。
RPC は DDS トピック `rt/api/<サービス名>/request` と `/response` の往復で、パラメータと戻り値は JSON 文字列。

## 目次

- [運動サービス sport（R1LocoClient）](#運動サービス-sportr1lococlient)
- [腕プリセット動作 arm（R1ArmActionClient）](#腕プリセット動作-armr1armactionclient)
- [音声・LED voice（AudioClient）](#音声led-voiceaudioclient)
- [その他のサービス](#その他のサービス)
- [エラーコード](#エラーコード)

## 運動サービス sport（R1LocoClient）

`from r1_clients import R1LocoClient`（[assets/r1_clients.py](../assets/r1_clients.py)）。サービス名 `sport`、API バージョン `1.0.0.0`。
ai_sport が 1.0.2.0 未満の古い機体はサービス名が `loco`。全呼び出しがタイムアウト（3104）する時は `R1LocoClient("loco")` を試す。

| メソッド | 送る内容 | 説明 |
| --- | --- | --- |
| `GetFsmId()` → `(code, id)` | API 7001 | 現在のモード ID |
| `SetFsmId(id)` | API 7101 `{"data": id}` | モード切替。成否は内蔵コントローラーの遷移規則しだい |
| `SetVelocity(vx, vy, omega, duration=1.0)` | API 7105 `{"velocity":[vx,vy,omega],"duration":d}` | 速度指令。範囲外の値はロボット側で許容範囲に丸められる |
| `Move(vx, vy, vyaw)` | `SetVelocity(..., 1.0)` | 1 秒で失効。歩き続けるには 0.2 秒程度の周期で再送 |
| `StopMove()` | `SetVelocity(0,0,0)` | 停止 |
| `Start()` | FSM 811 | 歩行・走行制御（Running Mode）へ |
| `Stance()` | FSM 4 | Locked Stand（直立固定、バランス制御なし）。公式 C++ の `StandUp()` に相当 |
| `Lie2StandUp()` | FSM 701 | 仰向けから起立。先に `Stance()` を送る（上流サンプルは 3 秒待ってから 701） |
| `StandUp2Lie()` | FSM 702 | 立位から仰向けへ |
| `Damp()` | FSM 1 | ダンピング。バランス制御なし |
| `ZeroTorque()` | FSM 0 | 脱力。バランス制御なし |
| `WaveHand(turn_flag=False)` | API 7106 `{"data": 0 or 1}` | 手を振る。`True` で振り向きながら |
| `ShakeHand(stage=-1)` | API 7106 `{"data": 2 or 3}` | 握手。1 回目で手を出し、2 回目で戻す（間に 3 秒ほど置く） |

速度の向き: `vx` 前進が正（m/s）、`vy` 左が正（m/s）、`vyaw` 反時計回りが正（rad/s）。

### R1 のモード ID

| ID | モード | コントローラー操作との対応 | LED |
| --- | --- | --- | --- |
| 0 | Zero Torque | L2 + Y | 紫 |
| 1 | Damping | L2 + B | オレンジ |
| 4 | Locked Stand | L2 + ↑ | 青 |
| 811 | Running（歩行・走行） | R2 + A | 白 |
| 701 | 仰向け → 起立 | L2 + X 長押し | |
| 702 | 起立 → 仰向け | L2 + X 長押し | |

通常の起動順は Zero Torque → Damping → Locked Stand → Running。ハッカソンではモード遷移はコントローラー担当者が行い、プログラムからは Running 中の `Move` / ジェスチャー / 音声だけを送る運用が安全。

G1 との違い（G1 用コードを移植する時の罠）: G1 は `Start`=500、`Lie2StandUp`=702、`Squat2StandUp`=706、`Sit`=3。R1 には `HighStand` / `LowStand` / `BalanceStand` / `SetSpeedMode` に相当する公開 API が無い。

## 腕プリセット動作 arm（R1ArmActionClient）

`from r1_clients import R1ArmActionClient, R1_ARM_ACTIONS`。サービス名 `arm`、API バージョン `1.0.0.0`。
公式マニュアルの仕様から実装したもので、**実機では未検証**。初回は `GetActionList()` が 0 を返すことを確認してから使う。

```python
arm = R1ArmActionClient()
arm.SetTimeout(10.0)   # ExecuteAction は再生終了までブロックする。動作時間より長くする
arm.Init()
time.sleep(1.0)

code, lists = arm.GetActionList()      # [プリセット一覧, カスタム一覧]。この結果が表より優先
code = arm.ExecuteAction("high_five")  # 名前でも ID(18) でも可
time.sleep(2.0)
arm.ReleaseArm()                       # 保持系の動作は必ず解除する
```

| メソッド | API ID | パラメータ | 備考 |
| --- | --- | --- | --- |
| `ExecuteAction(id または名前)` | 7106 | `{"action_id": 27}` | ブロッキング |
| `GetActionList()` | 7107 | なし | `[[{"id","name"},...], [{"name","time"},...]]` |
| `ExecuteCustomAction(name)` | 7108 | `{"action_name": "..."}` | ティーチング済み動作。ノンブロッキング |
| `StopCustomAction()` | 7113 | なし | |
| `ReleaseArm()` | 7106 | `{"action_id": 99}` | 初期姿勢に戻す |

### アクション ID

| ID | 名前 | 内容 | 時間(s) | 終了後に姿勢保持 | リモコン |
| --- | --- | --- | --- | --- | --- |
| 99 | `release_arm` | 腕を初期姿勢に戻す | — | | ↓ 2 回 |
| 11 | `blow_kiss_with_both_hands` | 両手で投げキッス | 3.0 | | |
| 12 | `blow_kiss_with_left_hand` | 左手で投げキッス | 3.0 | | |
| 13 | `blow_kiss_with_right_hand` | 右手で投げキッス | 3.0 | | |
| 15 | `both_hands_up` | 両腕を肩の高さに上げる | 1.0 | ○ | |
| 17 | `clamp` | 拍手 | 2.2 | | A 2 回 |
| 18 | `high_five` | ハイタッチ | 1.0 | ○ | |
| 19 | `hug` | ハグ | 2.0 | ○ | |
| 22 | `refuse` | 両腕でバツ | 0.9 | ○ | SELECT + X |
| 23 | `right_hand_up` | 右腕を肩の高さに上げる | 1.0 | ○ | |
| 24 | `ultraman_ray` | 光線ポーズ | 2.1 | ○ | |
| 25 | `wave_under_head` | 胸の前で手を振る | 2.6 | | Y 2 回 |
| 26 | `wave_above_head` | 頭上で手を振る | 5.7 | | SELECT + Y |
| 27 | `shake_hand` | 握手 | 1.0 | ○ | SELECT + A |
| 28 | `box_left_hand_win` | 左手ガッツポーズ | 1.0 | ○ | |
| 29 | `box_right_hand_win` | 右手ガッツポーズ | 1.0 | ○ | |
| 30 | `box_both_hand_win` | 両手ガッツポーズ | 2.5 | ○ | |
| 31 | `extend_right_arm_forward` | 右腕を前に伸ばす | 1.0 | ○ | |
| 33 | `right_hand_on_heart` | 右手を胸に当てる | 1.6 | ○ | |
| 34 | `both_hands_up_deviate_right` | 両腕を上げる（右寄り） | 1.0 | ○ | |
| 35 | `emphasize` | 強調のジェスチャー | 0.6 | ○ | |
| 36 | `forward_push` | 前に押し出す | 1.5 | ○ | |

リモコン列は運用ガイドの「エモーション操作」との対応の推定（公式に対応表は無い）。ID はファームウェアで変わるので `GetActionList()` を正とする。

姿勢保持（○）の規則:

- 保持中に別の ID を送ると 7401 で拒否される。`99` か、保持中と同じ ID を送ると解除される。
- 保持は最長 20 秒で自動解除。
- 歩行・走行中は実行できない動作がある（7404）。動作中は歩行できない。
- `rt/arm_sdk` を自分で使っている最中に呼ぶと 7400。

状態は `rt/arm/action/state`（`std_msgs.msg.dds_.String_`、10 Hz、JSON `{"holding": bool, "id": int, "name": str}`）で購読できる。カスタム動作再生中は id=100、ティーチング中は -1。

ティーチング API（7110 開始/心拍/停止、7111 一時停止、7109 改名、7112 削除）は腕が低剛性になり重力で落ちるため、通常は Unitree アプリから行う。必要なら公式ページ arm_action_interface を参照。

## 音声・LED voice（AudioClient）

```python
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

audio = AudioClient()
audio.SetTimeout(10.0)
audio.Init()
time.sleep(1.0)
```

| メソッド | 説明 |
| --- | --- |
| `TtsMaker(text, speaker_id)` | 音声合成して再生。`speaker_id` 0=中国語、1=英語。混在不可、**日本語不可**。上流サンプルは呼び出し後に発話時間ぶん `sleep` している（発話終了を待たずに戻る前提）ので、続けて喋らせる時は間を空ける |
| `GetVolume()` → `(code, {"volume": n})` | 音量取得（0–100） |
| `SetVolume(n)` | 音量設定（0–100） |
| `LedControl(R, G, B)` | RGB ライト（各 0–255）。呼び出し間隔は 200 ms より長く空ける |
| `PlayStream(app_name, stream_id, pcm_bytes)` | PCM 再生。**16 kHz・モノラル・16 bit リトルエンディアン**。同じ `stream_id` は続きとして連結再生、違う ID は現在の再生を中断 |
| `PlayStop(app_name)` | 再生停止 |

日本語を喋らせたい時は、PC 側で日本語 TTS（任意のエンジン）から 16 kHz モノラル 16 bit の WAV を作り、`PlayStream` で流す。

```python
import time, wave

def play_wav(audio, path, app="hackathon"):
    with wave.open(path, "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2), "16kHz/mono/16bit のみ"
        pcm = w.readframes(w.getnframes())
    stream_id = str(int(time.time() * 1000))
    chunk = 96000                              # 3 秒ぶん。上流サンプルと同じ分割
    start = time.time()
    for off in range(0, len(pcm), chunk):
        code, _ = audio.PlayStream(app, stream_id, pcm[off:off + chunk])
        if code != 0:
            return code
        time.sleep(1.0)
    remaining = len(pcm) / 32000 - (time.time() - start)   # 32000 bytes = 1 秒
    time.sleep(max(0.0, remaining) + 0.5)      # 鳴り終わるのを待ってから止める
    audio.PlayStop(app)
    return 0
```

音声認識: マイクが有効（アプリまたはリモコンで wake-up モード）の時、`rt/audio_msg`（`std_msgs.msg.dds_.String_`）に JSON が流れる。フィールドは `index` `timestamp` `text` `angle`(0–180) `speaker_id` `sense` `confidence` `language` `is_final`。再生状態 `{"play_state": 0|1}` も同じトピックに流れる。内蔵 ASR の対応言語は機体設定しだい（日本語は未検証）。

```python
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_

sub = ChannelSubscriber("rt/audio_msg", String_)
sub.Init(lambda msg: print(msg.data), 10)
```

必要なファームウェア: Vui_Service ≥ 2.2.0.0。マイクの生音声は UDP マルチキャスト `239.168.123.161:5555`（16 kHz PCM）で取得できる。

## その他のサービス

| サービス | Python での利用 | 備考 |
| --- | --- | --- |
| `motion_switcher` | `unitree_sdk2py.comm.motion_switcher.motion_switcher_client.MotionSwitcherClient` の `CheckMode()` / `ReleaseMode()` / `SelectMode(name)` | `ReleaseMode()` は内蔵コントローラーを止めてデバッグモードに入れる操作。吊った状態でのみ |
| `robot_state` | `unitree_sdk2py.b2.robot_state.robot_state_client`（B2 用を流用） | サービスの on/off。`ai_sport` `basic_service` `vui_service` など。通常は触らない |
| 映像・SLAM/ナビ | Python クライアント無し | 公式ページ video_service、slam_navigation_services_interface を参照。EDU 版向け |

## エラーコード

| コード | 意味 | 対処 |
| --- | --- | --- |
| 0 | 成功 | |
| 3102 | リクエスト送信失敗 | DDS 初期化、`Init()` 後の待ち時間 |
| 3103 | API 未登録 | Python SDK ではクライアント側の未登録（`Init()` の呼び忘れ） |
| 3104 | タイムアウト（応答なし） | 配線・IP・インターフェース名・ドメイン ID、`Init()` 後の待ち時間、サービス名（`sport`/`loco`）、デバッグモードになっていないか。`SetTimeout()` を呼ばないと既定は 1 秒 |
| 3203 | サーバー側にその API が無い | ファームウェアが古い、またはサービス名違い |
| 3204 | パラメータ不正 | JSON のキー名（R1 の腕は `action_id`） |
| 7301 | 運動状態が取得できない | 7301–7303 は SDK の H2 用定義にある値。R1 でも同じと推定（未検証） |
| 7302 | 無効な FSM ID | |
| 7303 | 無効なタスク ID | |
| 7399 | 腕サービス内部エラー | |
| 7400 | 上半身の制御権が使用中 | `rt/arm_sdk` を使っている、または別の動作が再生中 |
| 7401 | 腕が姿勢保持中 | `99` か同じ ID で解除 |
| 7402 | 無効なアクション ID | `GetActionList()` で確認 |
| 7403 | 動作ファイルが無い | カスタム動作名の間違い |
| 7404 | 今のモードでは実行不可 | 歩行中、またはデバッグモード |
| 7406 | バッテリー残量不足（6% 未満） | |
| 7407 | モーターがエラー状態 | |

31xx / 32xx は SDK の `unitree_sdk2py/rpc/internal.py` の定義、74xx は公式マニュアル arm_action_interface の定義。
