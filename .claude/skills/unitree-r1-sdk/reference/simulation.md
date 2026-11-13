# 実機なしでテストする

結論: **高レベル API（歩行指令・腕プリセット・TTS）を物理込みで再現する公式シミュレーターは無い。** 公式の unitree_mujoco は低レベル制御（`rt/lowcmd` / `rt/lowstate`）専用。目的に応じて使い分ける。

| 確認したいこと | 手段 | 実機との差 |
| --- | --- | --- |
| スクリプトが落ちないか、API の引数・順序・タイミング、エラー処理 | **モック**（[assets/mock_robot.py](../assets/mock_robot.py)） | 物理なし。倒れる・ぶつかる・実際の歩幅は分からない |
| 自作の関節制御（低レベル）が物理的に成り立つか | **unitree_mujoco**（R1 モデルあり） | 内蔵コントローラーが無いので `Move()` などは使えない |
| 歩行ポリシーの学習・検証 | unitree_rl_mjlab / unitree_rl_lab | 別環境（GPU、Linux）。このリポジトリの範囲外 |
| 最終確認 | 実機を**スタンドに吊った状態**で実行 | — |

## モック（高レベル API 用）

`sport` / `arm` / `voice` の RPC サーバーを開発 PC 上に立て、受け取ったコマンドを表示する。SDK 付属の `unitree_sdk2py.rpc.server.Server` を使っており、追加の依存は無い。Windows でも動く。

```bash
# 初回のみ: scripts/ にコピー
cp .claude/skills/unitree-r1-sdk/assets/mock_robot.py scripts/
cp .claude/skills/unitree-r1-sdk/assets/r1_clients.py scripts/

pixi run python scripts/mock_robot.py              # ターミナル 1（DDS ドメイン 1 で待ち受け）
pixi run python scripts/my_script.py --domain 1    # ターミナル 2（-i は付けない）
```

モックは Running Mode（811）で起動する。これは「コントローラー担当者がロボットを歩行状態にした後にスクリプトを流す」という会場での手順に合わせたもの。別のモードから始めたい時は `--fsm 4` などを付ける。

出力例:

```text
[23:03:51] sport SetVelocity vx=+0.30 vy=+0.00 omega=+0.00 duration=1s
[23:03:53] sport 停止。推定位置 x=+0.51m y=+0.00m yaw=+0deg
[23:03:53] voice TtsMaker[英語] "Hello from the mock test"
[23:03:53] arm   ExecuteAction(27) = shake_hand（1.0s 再生・姿勢保持）
[23:03:54] arm   ExecuteAction(19=hug) -> 保持中 (7401)。先に 99 で解除する
```

モックが再現すること:

- R1 の FSM ID 以外は 7302 で拒否（G1 用の ID を送る間違いが分かる）。
- Running(811) 以外で送った速度指令に警告。立位からの `Damp` / `ZeroTorque` に警告。
- 速度指令の失効（`duration`）を含めて位置を積分し、止まった時に推定位置を表示。
- 腕動作のブロッキング時間、姿勢保持と 7401、`{"action_id": N}` 以外のパラメータを 3204 で拒否。
- TTS のテキストと話者、音量、LED。

再現しないこと: `PlayStream`（音声ストリーム再生）、`rt/lowstate` の配信、`rt/audio_msg`、物理全般。

注意:

- スクリプト側が `ChannelFactoryInitialize(args.domain, args.interface)` のようにドメインを引数で受ける必要がある。`samples/` の 2 本はドメイン 0 固定なので、モックで試すなら `mock_robot.py --domain 0` で起動する。**その時は実機の LAN ケーブルを抜いておく**（同じ名前のサービスが 2 つ応答してしまう）。
- 同じドメインにモックが 2 つあると、両方が応答して呼び出しがときどき 3105 で失敗する（Windows で再現確認済み）。自分の PC で二重起動していないか確認する。ドメイン 1・インターフェース自動選択なので、同じ LAN に別の人のモックがいても同じことが起きる。その場合は各自 `--domain 2` などに変える（両方のプロセスで同じ値にする）。
- モックで通っても実機で通るとは限らない。実機の拒否条件（モード遷移の可否、歩行中に出せない動作など）はモックより厳しい。

## unitree_mujoco（低レベル制御用）

<https://github.com/unitreerobotics/unitree_mujoco> — MuJoCo 上のロボットが実機と同じ DDS トピックを喋る。`unitree_robots/r1/`（`scene.xml`、`R1_C++.xml`）が含まれている。

- 対応メッセージは `LowCmd` / `LowState` / `SportModeState` と、ゲームパッドによる `rt/wirelesscontroller` のみ。README に「Current version only supports low-level development」と明記。**`LocoClient.Move()`、腕プリセット、AudioClient は動かない**（応答するサービスが存在しない）。
- シミュレーター内のロボットは制御を与えないと崩れ落ちる。立たせる・歩かせるには自分で制御則か学習済みポリシーを用意する必要がある。
- 既定はドメイン 1、インターフェース `lo`。スクリプト側は `ChannelFactoryInitialize(1, "lo")` でシミュレーター、`ChannelFactoryInitialize(0, iface)` で実機、と切り替える。

2 つの実装:

| | C++ 版（`simulate/`、推奨とされる） | Python 版（`simulate_python/`） |
| --- | --- | --- |
| 設定 | `config.yaml`: `robot: "r1"`、または `./unitree_mujoco -r r1 -s scene.xml` | `config.py`: `ROBOT = "r1"` |
| 依存 | unitree_sdk2（C++）、MuJoCo、yaml-cpp、spdlog、boost、glfw | `pip install mujoco pygame` + unitree_sdk2py |
| OS | Linux | Linux（`RecurrentThread` を使うため Windows / macOS ネイティブでは動かない） |

R1 は設定ファイルのコメントにある対応機種一覧（go2, b2, b2w, h1, go2w, g1, h2, as2）に載っておらず、R1 での動作は未検証。モデルファイルはあるので、モーター数から `unitree_hg` IDL が自動選択されれば動く見込み。動かない場合は C++ 版で `-t 1`（unitree_hg を明示）を試す。

Windows で使うなら WSL2（Ubuntu）上に別環境を作るのが現実的。このリポジトリの pixi 環境には mujoco は入っていない（`pixi.toml` を変える時はユーザーに確認する。`cyclonedds==0.10.2` と Python 3.10 は維持）。

吊り下げの再現: 設定の `enable_elastic_band` を有効にすると仮想のゴムバンドでロボットを吊れる（`9` で着脱、`7` で下げる、`8` で上げる）。

## その他の公式リソース

- URDF: <https://github.com/unitreerobotics/unitree_ros/tree/master/robots/r1_description>
- 強化学習: <https://github.com/unitreerobotics/unitree_rl_mjlab>（MuJoCo ベース。R1 対応の有無はリポジトリの README で確認する）
- C++ SDK と R1 サンプル（`r1_loco_client`、`r1_arm_action_example`、`r1_arm_sdk_dds_example`）: <https://github.com/unitreerobotics/unitree_sdk2>
