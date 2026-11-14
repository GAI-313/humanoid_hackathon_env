# 認識（担当B）引き継ぎメモ

最終更新: 2026-11-14（Day1 午後）

QRの読取からダッシュボードへの送信までは、PC内蔵カメラで動いています。R1 の頭部カメラから映像を取る部分だけが、実機で未確認です。次に実機を使える人は「次にやること」の1から進めてください。

## いま動くもの・未確認のもの

| 項目 | 状態 | 確認方法 |
|---|---|---|
| QRの読取と分類先の判定 | 動作確認済み | `scripts/test_recognition.py` が 6/6 成功 |
| receiver への送信（`scanned` / `error`） | 動作確認済み | ローカルの receiver が 201 を返し、`logs/events.jsonl` に保存された |
| PC内蔵カメラからの取得（`webcam`） | 動作確認済み | 640x480、約15fps |
| R1 頭部カメラからの取得（`videohub`） | **実機で未確認** | 下の「次にやること」1 |
| R1 の UDP 配信の受信（`udp`） | **実機で未確認** | `videohub` で取れない場合の予備 |
| pixi 環境での実行 | **未確認** | 確認はシステムの Python 3.12 / OpenCV 5.0 で行った |

## 構成

```
R1 頭部カメラ ─(有線LAN・DDS)─▶ camera_source.py ─▶ qr_reader.py ─▶ events.py ─POST /events─▶ receiver (:8000)
                                  取得元を切替        読取と確定       log_schema.md の形式
```

| ファイル | 役割 |
|---|---|
| `scripts/camera_source.py` | カメラの取得元。`webcam` / `file` / `videohub` / `udp` を `--source` で切り替える |
| `scripts/qr_reader.py` | QRの読取。同じ内容が3フレーム続いたら確定し、5秒間は同じ内容を再送しない |
| `scripts/events.py` | イベントの生成と POST。形式は [log_schema.md](log_schema.md) |
| `scripts/recognize.py` | 上の3つをつないだ本体 |
| `scripts/camera_check.py` | 取得元の診断。解像度・fps・成功率を表示し、1枚を `work/camera_check.jpg` に保存する |
| `scripts/make_qr.py` | テスト用QRの生成（`work/qr/` に出力） |
| `scripts/test_recognition.py` | 実機なしの自己テスト |

`pixi.toml` の `[tasks]` に `recognize` / `camera-check` / `make-qr` / `test-recognition` を追加しました。依存パッケージは変えていません。

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

## 次にやること

1. **実機で `camera-check --source videohub` を実行する**。`work/camera_check.jpg` に画像が保存されれば、取得経路はこれで確定です。
2. **1 が失敗した場合**、表示されるエラーコードで切り分けます。`3104`（応答なし）なら、R1 のアプリの「Settings → Service Status」で `video_hub` が動いているかをスタッフに確認します。それでも取れなければ `--source udp --port 5001` を試します。公式マニュアルでは、`video_hub` を止めて `Stereo Patch PC1` を起動すると、ポート 5001 に 1280x720 の映像が RTP/H264 で配信されます。Windows ではファイアウォールで UDP 5001 の受信を許可する必要があるかもしれません。
3. **どちらも取れない場合**は、外付けの Web カメラを頭部に固定し、`--source webcam --index 1` で進めます。
4. **実機のカメラで QR の読取成功率を測る**（距離・角度・照明）。`--save-dir work/shots` を付けると、確定した瞬間のフレームが残ります。
5. **制御（担当A）との連携を決める**。いまは `scanned` を receiver へ送るだけで、A の `go_to(zone)` を呼ぶ処理はありません。`recognize.py` の `run()` は発行したイベントを返すので、A のスクリプトから呼び出す形にできます。
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

## 参照

- Unitree SDK2 Python の映像サンプル: <https://github.com/unitreerobotics/unitree_sdk2_python/tree/master/example/go2/front_camera>
- R1 開発者マニュアル（映像）: <https://support.unitree.com/home/en/R1_developer/video_service>
- ダッシュボードの使い方: [dashboard_manual.md](dashboard_manual.md)
- イベントの形式: [log_schema.md](log_schema.md)
