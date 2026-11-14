# ダッシュボード 使い方マニュアル

ロボットの行動ログを受け取り、Web 画面に表示するツールの使い方。仕様は [dashboard_spec.md](dashboard_spec.md)、ログの形式は [log_schema.md](log_schema.md) を参照。

## 構成

```
認識(B)・制御(A) ──POST /events──▶ receiver (:8000) ──追記──▶ logs/events.jsonl
                                                                  ▲ 読み取り（1秒ごと）
                                                       ダッシュボード画面 (:8501)
```

| ファイル | 役割 |
|---|---|
| `dashboard/receiver.py` | イベント受信サーバー（FastAPI）。検証してログに追記する |
| `dashboard/app.py` | 画面（Streamlit） |
| `dashboard/common.py` | ログの読み書き、状態の導出、集計 |
| `dashboard/send_dummy.py` | ダミーイベント送信 |
| `dashboard/run.py` | receiver と画面の同時起動 |

## 1. 起動する

初回のみ、環境を作る。

```bash
pixi install
```

ダッシュボードを起動する（receiver と画面が同時に立ち上がる）。

```bash
pixi run dashboard
```

次の2行がログに出れば起動完了。ブラウザが自動で開く。開かない場合は http://localhost:8501 を開く。

```
Uvicorn running on http://0.0.0.0:8000
Local URL: http://localhost:8501
```

- **このターミナルは開いたままにする。** 閉じる・Ctrl+C を押すと receiver も画面も止まる
- 止めるときは Ctrl+C を1回押す
- 別のPC（プロジェクタ用PCなど）から見る場合は `http://<このPCのIP>:8501`

### 個別に起動する場合
```bash
pixi run receiver        # receiver のみ（:8000）
pixi run dashboard-ui    # 画面のみ（:8501）
```

## 2. 動作確認（ダミーイベントを送る）

別のターミナルを開いて実行する。実機がなくても画面の動きを確認できる。

```bash
pixi run send-dummy --zone A     # 1箱ぶん（読取 → 移動 → 到着）を区画Aへ
pixi run send-dummy --zone B     # 区画Bへ
pixi run send-dummy --error      # 想定外QR（誤出荷アラート）
pixi run send-dummy --zone A --box B010   # 箱IDを指定
```

画面左のサイドバーにも同じ操作のボタンがある（「箱を流す → 区画A/B」「誤出荷」）。

## 3. 画面の見方

| 場所 | 内容 |
|---|---|
| 上部のバッジ | ロボット状態。待機（灰）／読取中（青）／移動中（橙）／完了（緑）／エラー（赤）。現在の箱IDと分類先も表示 |
| 赤いバナー | 想定外のQRを検知したとき（誤出荷の可能性）。次のイベントが来ると消える |
| 作業タイムライン | 新しい順。時刻・種別・箱ID・分類先・詳細 |
| 現在地 | スタートと区画A/B の図。位置は状態から推定して表示（実測ではない） |
| 集計 | 区画A・B の処理数、誤出荷検知数 |
| サイドバー | receiver の接続状態、デモ操作、ログのリセット |

- 完了・エラーのまま15秒イベントが来ないと「待機」に戻る
- 画面は1秒ごとに自動更新される

## 4. 実機・認識側からイベントを送る

`POST http://<ダッシュボードのPCのIP>:8000/events` に JSON を送る。形式は [log_schema.md](log_schema.md)。

Python の例（標準ライブラリのみ）:

```python
import json, urllib.request
from datetime import datetime

body = {
    "v": 1,
    "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
    "robot": "R1",
    "run_id": "20261115-1030",
    "box_id": "B001",
    "event": "scanned",        # scanned / moving / arrived / error
    "zone": "A",               # 不明なら None
    "source": "recognition",   # recognition / control / dashboard
    "detail": "QR読取成功",
}
req = urllib.request.Request(
    "http://127.0.0.1:8000/events",
    data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
urllib.request.urlopen(req, timeout=3)
```

- `box_id` と `zone` はキー自体が必須。値が無いときは `null`（`None`）を入れる
- `ts` にはタイムゾーン（`+09:00`）が必要
- `id` と `received_at` は送らない（receiver が付ける）
- 必須項目が足りない・形式が違うと `422` が返り、保存されない
- `send_dummy.py` の `build()` と `post()` をそのまま import して使うこともできる

## 5. ログの扱い

- 保存先は `logs/events.jsonl`（1行1イベント。git には入らない）
- **リセット**: サイドバーの「ログをリセット」を押す。`logs/events.<日時>.bak.jsonl` に退避してから空になる
- 場所を変えるには環境変数を使う
  - `EVENTS_LOG`: ログファイルのパス
  - `RECEIVER_URL`: 画面とダミー送信が使う receiver の URL（既定 `http://127.0.0.1:8000`）

## 6. 困ったとき

| 症状 | 原因と対処 |
|---|---|
| `send-dummy` が `ConnectionRefusedError` / `WinError 10061` | receiver が動いていない。`pixi run dashboard` を起動したターミナルが開いているか確認する |
| 画面のサイドバーが「receiver に接続できません」 | 同上。`dashboard` のターミナルのログに `Uvicorn running on http://0.0.0.0:8000` があるか確認する |
| 起動時に `Address already in use` / ポートが使用中 | 前回のプロセスが残っている。ターミナルを閉じて再度開くか、タスクマネージャーで python を終了する |
| 画面が更新されない | ブラウザを再読み込みする。`logs/events.jsonl` に行が増えているか確認する |
| ロボット側から送ると `422` | 必須項目の不足、`ts` のタイムゾーンなし、`source` の値違いを確認する（レスポンス本文に理由が出る） |
| 別PCから画面が開けない | ファイアウォールで 8000・8501 番を許可する。PC と同じネットワークにいるか確認する |
