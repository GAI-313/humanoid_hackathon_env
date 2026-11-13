# Unitree R1 SDK スキル作成まとめ

作成日: 2026-11-13

「ヒューマノイドロボット運用ガイド_v1.pdf」で紹介されている Unitree 公式 R1 開発者マニュアルと Unitree SDK2 Python ラッパーリポジトリを参照し、SDK の使い方を Claude Code のスキル `unitree-r1-sdk` として `.claude/skills/unitree-r1-sdk/` にまとめた。実機にはつないでいないので、確認できたのはロボットなしで動く範囲まで。

## シミュレーターはあるか

歩行指令・腕のプリセット動作・TTS といった高レベル API を物理込みで再現する公式シミュレーターは無い。

- **公式の unitree_mujoco**: R1 のモデルは入っているが、対応は低レベル制御（関節への直接指令）だけ。`Move()` や TTS に応答するサービスは無く、制御を与えないとロボットは崩れ落ちる。Python 版は Linux 専用で、R1 での動作は未確認。
- **代わりに作ったモック**: 開発 PC 上で R1 の `sport` / `arm` / `voice` サービスになりすます `mock_robot.py` をスキルに同梱した。受け取ったコマンドの引数・順序・タイミングを表示し、R1 に無いモード ID や腕の姿勢保持中の重複指令はエラーで返す。物理は再現しないので、転倒や干渉は分からない。
- **最終確認**: 運用ガイドどおり、実機をスタンドに吊った状態で行う。

モックは Windows 上で別プロセスのスクリプトから呼び出して動作を確認済み。

```bash
cp .claude/skills/unitree-r1-sdk/assets/*.py scripts/
pixi run python scripts/mock_robot.py             # ターミナル1
pixi run python scripts/my_script.py --domain 1   # ターミナル2
```

モックは DDS ドメイン 1 で動くので、スクリプト側に `--domain` 引数が必要（スキルのテンプレートに入れてある）。`samples/` の 2 本はドメイン 0 固定のままで、変更していない。

## 調査で分かった注意点

- **R1 用クライアントが pixi 環境に入っていない**: 上流リポジトリに `r1_loco_client.py` はあるが、パッケージ化から漏れていて `unitree_sdk2py.r1` は import できない。同等品を `r1_clients.py` として同梱した。
- **G1 用クライアントの流用は危険な箇所がある**: `Move` / `StopMove` は G1 版でも同じだが、モード ID が違う。G1 版の `Lie2StandUp()` は R1 では「立位から仰向けへ」になる。
- **腕のプリセット動作は G1 版が使えない**: パラメータ形式とアクション ID 表が R1 と異なる。公式マニュアルの仕様から `R1ArmActionClient` を実装したが、実機では未検証。
- **Windows / macOS の制約**: SDK の周期スレッド（`RecurrentThread`）が import 時に落ちるため、上流の低レベル制御サンプルはそのままでは動かない。腕の直接制御（arm_sdk）も、検証に使った Windows PC では公式要求 100 Hz に対し約 55 Hz しか出なかった。

## スキルの中身

| ファイル | 内容 |
| --- | --- |
| `SKILL.md` | スクリプトの型、G1/R1 の使い分け、運用ガイドの安全ルール |
| `reference/high-level-api.md` | 歩行・モード切替、腕プリセット、音声・LED、エラーコード |
| `reference/low-level-dds.md` | 状態購読、リモコン入力、関節番号、arm_sdk、低レベル制御 |
| `reference/simulation.md` | モックと unitree_mujoco の使い分け |
| `assets/r1_clients.py` | R1 用の `R1LocoClient` / `R1ArmActionClient` |
| `assets/mock_robot.py` | 実機なしテスト用の偽 R1 サーバー |

## 参照元

- Unitree 公式 R1 開発者マニュアル: <https://support.unitree.com/home/en/R1_developer/about_R1>（ブラウザ描画のサイトのため、サイトが使っている公開 API から本文を取得した）
- Unitree SDK2 Python: <https://github.com/unitreerobotics/unitree_sdk2_python>（コミット 814556d）
- unitree_mujoco: <https://github.com/unitreerobotics/unitree_mujoco>
- ハッカソン運用ガイド: `docs/ヒューマノイドロボット運用ガイド_v1.pdf`
