# 認識（担当B）引き継ぎメモ

最終更新: 2026-11-14（Day1 午後）

箱のQRの読取、区画マーカーの認識、ダッシュボードへの送信、制御（担当A）への指示の受け渡しまで、PC内蔵カメラと合成画像で動いています。R1 の頭部カメラから映像を取る部分と、A のスクリプトとの結合が未確認です。次に実機を使える人は「次にやること」の1から進めてください。

## いま動くもの・未確認のもの

| 項目 | 状態 | 確認方法 |
|---|---|---|
| QRの読取と分類先の判定 | 動作確認済み | `scripts/test_recognition.py` が 12/12 成功 |
| receiver への送信（`scanned` / `error`） | 動作確認済み | ローカルの receiver が 201 を返し、`logs/events.jsonl` に保存された |
| 区画マーカー（`ZONE:A`）の認識と位置の算出 | 動作確認済み | 合成画像で左右のずれと大きさが期待どおり |
| 制御（担当A）への指示（`go_to` / `target`） | 動作確認済み（受け側は見本） | `control_example.py --listen` が受信した |
| 担当A の実コードとの結合 | **未着手** | A のスクリプトが main にまだ無い |
| PC内蔵カメラからの取得（`webcam`） | 動作確認済み | 640x480、約15fps |
| R1 頭部カメラからの取得（`videohub`） | **実機で未確認** | 下の「次にやること」1 |
| R1 の UDP 配信の受信（`udp`） | **実機で未確認** | `videohub` で取れない場合の予備 |
| pixi 環境での実行 | **未確認** | 確認はシステムの Python 3.12 / OpenCV 5.0 で行った |

## 構成

```
R1 頭部カメラ ─(有線LAN・DDS)─▶ camera_source.py ─▶ qr_reader.py ─▶ events.py ─POST /events─▶ receiver (:8000)
                                  取得元を切替        読取と確定       log_schema.md の形式
                                                          │
                                                          └─▶ recognition_link.py ─(import または POST /command)─▶ 制御（担当A）
```

| ファイル | 役割 |
|---|---|
| `scripts/camera_source.py` | カメラの取得元。`webcam` / `file` / `videohub` / `udp` を `--source` で切り替える |
| `scripts/qr_reader.py` | QRの読取。同じ内容が3フレーム続いたら確定し、5秒間は同じ内容を再送しない |
| `scripts/events.py` | イベントの生成と POST。形式は [log_schema.md](log_schema.md) |
| `scripts/recognition_link.py` | `Recognizer` クラス。認識をバックグラウンドで回し、箱の確定と区画マーカーの位置を A に渡す |
| `scripts/commands.py` | A への指示（`go_to` / `target`）の生成と POST |
| `scripts/control_example.py` | A 向けの見本。ロボットは動かさず、判断結果を表示するだけ |
| `scripts/recognize.py` | `Recognizer` を使う CLI |
| `scripts/camera_check.py` | 取得元の診断。解像度・fps・成功率を表示し、1枚を `work/camera_check.jpg` に保存する |
| `scripts/make_qr.py` | テスト用QRの生成（`work/qr/` に出力） |
| `scripts/test_recognition.py` | 実機なしの自己テスト |

`pixi.toml` の `[tasks]` に `recognize` / `camera-check` / `make-qr` / `test-recognition` / `control-example` を追加しました。依存パッケージは変えていません。

## R1 のカメラ映像の取り方

接続は README「3. ロボットとの接続方法」のとおりです。PC の有線LANに `192.168.123.164` を手動で設定し、R1（`192.168.123.161`）と LAN ケーブルで直接つなぎます。R1 内蔵 PC にはログインしません。

取得には、Unitree 公式 SDK のサンプルと同じ方法を使います。`unitree_sdk2_python` の `example/go2/front_camera/camera_opencv.py` にある、`VideoClient` の `GetImageSample()` で JPEG を1枚ずつ受け取る方法です。SDK に R1 専用のカメラサンプルは無く、あるのは Go2 / B2 用だけなので、R1 で同じサービス（`videohub`）が応答するかは実機で確かめる必要があります。`scripts/camera_source.py` の `videohub` がこの方法の実装です。

```python
from unitree_sdk2py.go2.video.video_client import VideoClient

client = VideoClient()
client.SetTimeout(3.0)
client.Init()
code, data = client.GetImageSample()          # code == 0 なら成功
image = cv2.imdecode(np.frombuffer(bytes(data), np.uint8), cv2.IMREAD_COLOR)
```

`videohub` と `udp` を指定すると、起動時に PC の IP と R1 への ping を確かめ、README の前提と違えば警告を出します。

## 使い方

実機なしで一通り試す場合は、ダッシュボードを起動してから別のターミナルで実行します。

```bash
pixi run dashboard
pixi run make-qr --box-id B001 B002 --zone A B
pixi run recognize --source webcam --show --server http://localhost:8000/events
```

実機につないだら、先に診断で映像が来るかを確かめます。`<iface>` は `192.168.123.164` を設定した有線LANアダプタの名前です（Windows は `Get-NetAdapter` の Name 列）。

```bash
pixi run camera-check --source videohub -i <iface>
pixi run recognize --source videohub -i <iface> --show --server http://localhost:8000/events
```

QRの中身は `{"box_id":"B001","zone":"A"}` の JSON か、`B001:A` の簡易形式のどちらでも読めます。`--zones`（既定 `A,B`）に無い分類先と、解釈できない内容は、`error`（`UNKNOWN_QR`）として送ります。ダッシュボードの誤出荷アラートはこのイベントで出ます。

## 分類する場所の認識と、制御（担当A）への指示

区画A/B には、中身が `ZONE:A` / `ZONE:B` の QR を貼ります（`pixi run make-qr --zone-marker A B` で `work/qr/ZONE_A.png` などを生成）。認識側は、このマーカーが画面のどこに、どの大きさで見えているかを毎フレーム計算します。

| 値 | 意味 |
|---|---|
| `offset` | 画面中心からの左右のずれ。-1.0（左端）〜 +1.0（右端） |
| `bearing` | `left` / `center` / `right`。`offset` の絶対値が 0.15 以下なら `center` |
| `size_ratio` | マーカーの辺の長さ ÷ 画像の幅。近づくほど大きくなる |
| `distance_m` | 距離の推定値。`--marker-size-cm` と `--hfov-deg` を両方指定したときだけ出る。カメラの画角は未計測なので目安 |

A への渡し方は2通りあります。R1 に有線でつなぐ PC は1台なので、**同じプロセスに組み込む方式を基本**にしています。

同じプロセスに組み込む場合は、A のスクリプトから `Recognizer` を使います。DDS の初期化（`ChannelFactoryInitialize`）は A の側で1回だけ行い、`Recognizer` は初期化しません。

```python
from camera_source import open_source
from recognition_link import Recognizer

rec = Recognizer(open_source("videohub"), zones=("A", "B"),
                 server="http://localhost:8000/events")
rec.start()
box = rec.pop_box(timeout=0.2)        # 箱のQRが確定したら {"box_id": "B001", "zone": "A"}
target = rec.get_target(box["zone"])  # 区画マーカーが見えていれば offset / bearing / size_ratio
# target が None なら探索、bearing が left / right なら旋回、size_ratio が閾値以上なら到着
rec.stop()
```

別のプロセスで受ける場合は、`recognize` に `--command-url` を付けます。箱が確定すると `go_to` を1回、その後は区画マーカーの位置を `target` として毎秒2回まで POST します。見失って1秒たつと `visible: false` を1回送ります。

```json
{"v": 1, "ts": "2026-11-14T14:58:48+09:00", "cmd": "go_to", "box_id": "B001", "zone": "A", "run_id": "20261114-1458"}
{"v": 1, "ts": "2026-11-14T14:58:48+09:00", "cmd": "target", "zone": "A", "visible": true, "offset": 0.64, "bearing": "right", "size_ratio": 0.104, "distance_m": 0.72, "run_id": "20261114-1458"}
```

動きを確かめるには、ターミナルを2つ使います。

```bash
pixi run control-example --listen 8001
pixi run recognize --source webcam --show --command-url http://localhost:8001/command
```

`scripts/control_example.py` の `decide()` が、観測から「探索・左へ旋回・右へ旋回・前進・到着」を決める見本です。`loco.Move()` と `StopMove()` を書く場所をコメントで示してあります。

## ほかの担当と決めること

| 相手 | 決めること |
|---|---|
| A（制御） | 同じプロセスに組み込むか、HTTP で受けるか。到着の判定（`size_ratio` の閾値）をどちらが持つか。`moving` / `arrived` イベントは A が送る |
| C（ダッシュボード） | receiver を動かす PC の IP。`pixi.toml` の `[tasks]` を双方が編集しているので、main に入れる順番 |
| D（PM・デモ） | 印刷済みの箱の QR の中身が `{"box_id":"B001","zone":"A"}` か `B001:A` になっているか。区画マーカー（`ZONE:A` / `ZONE:B`）の印刷と、貼る高さ・大きさ。実機の時間割（カメラの確認に15分ほど） |
| スタッフ | `videohub` が応答しない場合の、R1 のアプリでのサービス状態の確認 |

## 次にやること

1. **実機で `camera-check --source videohub` を実行する**。`work/camera_check.jpg` に画像が保存されれば、取得経路はこれで確定です。
2. **1 が失敗した場合**、表示されるエラーコードで切り分けます。`3104`（応答なし）なら、R1 のアプリの「Settings → Service Status」で `video_hub` が動いているかをスタッフに確認します。それでも取れなければ `--source udp --port 5001` を試します。公式マニュアルでは、`video_hub` を止めて `Stereo Patch PC1` を起動すると、ポート 5001 に 1280x720 の映像が RTP/H264 で配信されます。Windows ではファイアウォールで UDP 5001 の受信を許可する必要があるかもしれません。
3. **どちらも取れない場合**は、外付けの Web カメラを頭部に固定し、`--source webcam --index 1` で進めます。
4. **実機のカメラで QR の読取成功率を測る**（距離・角度・照明）。`--save-dir work/shots` を付けると、確定した瞬間のフレームが残ります。
5. **制御（担当A）と結合する**。受け渡しの口は用意してあるので、A のスクリプトに `Recognizer` を組み込み、`control_example.py` の `decide()` に当たる部分を実際の `Move()` に置き換えます。区画マーカーを実機のカメラで読める距離と、到着とみなす `size_ratio` は実測で決めます。
6. **Gemini による商品認識（Could）**は未着手です。QR の読取が実機で安定してから、停止位置の静止画を1枚だけ送る形で足す想定です。

## 既知の注意点

- 同じ QR を映し続けると、5秒ごとに `scanned` を再送します。1箱1回にしたい場合は、`qr_reader.py` の `StableDecoder` を「一度見えなくなるまで再送しない」動きに変えてください。
- `run_id` は起動時刻（`YYYYMMDD-HHMM`）を自動で付けます。リハーサルごとに `recognize` を起動し直すと、通し実行ごとに分かれます。
- receiver への送信に失敗しても認識は止まらず、警告を1行出します。422 が返る場合は、警告に出る本文で不足している項目が分かります。
- `videohub` は1枚ごとに要求と応答を往復するので、fps は高くありません。QR の読取には足りる見込みですが、実測はまだです。
- OpenCV 4.8 系（pixi 環境）では未実行です。版による API の違いはコード側で吸収していますが、最初に `pixi run test-recognition` を通してください。

## 作業の記録（2026-11-14）

- `docs/task_schedule.md` の担当B のタスクと、配布資料（Google Drive）を確認した。配布資料にカメラの取得方法は載っていなかった。
- Unitree 公式の R1 開発者マニュアル（Video streaming service interface）と、`unitree_sdk2_python` の映像サンプルを確認した。
- 取得元を差し替えられる構成で、取得・読取・送信のスクリプトを作成した。
- `docs/log_schema.md` と `dashboard/receiver.py` に合わせて、イベントに `v` / `run_id` / `source` を付け、`ts` をタイムゾーン付きにした。`task_schedule.md` の「イベント JSON」の6項目だけでは、receiver が 422 を返す。
- 合成した QR 画像で、正常系と想定外 QR の両方が receiver に保存されることを確認した。
- 区画マーカーの認識と、制御（担当A）への指示の受け渡し（`Recognizer` と `--command-url`）を追加した。合成画像で、箱の確定から `go_to`、`target` の受信までを確認した。

## 参照

- Unitree SDK2 Python の映像サンプル: <https://github.com/unitreerobotics/unitree_sdk2_python/tree/master/example/go2/front_camera>
- R1 開発者マニュアル（映像）: <https://support.unitree.com/home/en/R1_developer/video_service>
- ダッシュボードの使い方: [dashboard_manual.md](dashboard_manual.md)
- イベントの形式: [log_schema.md](log_schema.md)
