![Logo](docs/B1C63B70-0118-48BA-8E98-DC4ADD1B25CB.png)

# humanoid_hackathon_env セットアップガイド <a id="title"></a>

本リポジトリは，Unitree Robotics 社の人形ロボット向け Python 開発キットである `unitree_sdk2_python` （`unitree_sdk2py`）を，パッケージマネージャー `pixi` を用いてクロスプラットフォームに構築・実行するための開発環境です．

> [!NOTE]
> 本環境は **Linux (`linux-64`)**，**macOS Intel (`osx-64`)**，**macOS Apple Silicon (`osx-arm64`)**，**Windows (`win-64`)** の 4 プラットフォームに対応しています．
> ロボット実機（Unitree G1 / R1 等）の車載ノードは **CycloneDDS 0.10.2** で稼働しており，最新の CycloneDDS 11.x 系とは XTypes $`\text{Extensible and Dynamic Topic Types for DDS}`$ の型情報ハッシュが一致せず通信が確立できないため，本リポジトリでは **Python 3.10** 環境上で公式 prebuilt wheel が提供されている **`cyclonedds==0.10.2`** を厳格に指定しています．
> また，C ライブラリを手動ビルドすることなく，`pixi install` コマンドのみで全自動セットアップが完了します．

---

## 目次 <a id="table-of-contents"></a>

1. [各 OS への Pixi インストール手順](#pixi-installation)
1. [リポジトリのセットアップ手順](#repository-setup)
1. [ロボットとの接続方法](#robot-connection)
1. [サンプルコードの実行方法](#sample-execution)
   - [音声合成（TTS 発話）](#sample-tts)
   - [基本移動（歩行・旋回）](#sample-walk)
1. [自作プログラムの作成・実行方法](#custom-program)

---

## 1. 各 OS への Pixi インストール手順 <a id="pixi-installation"></a>

`pixi` は，Conda エコシステムと PyPI の両方をシームレスに統合管理できる高速なパッケージマネージャーです．お使いの OS $`\text{Operating System}`$ に合わせて以下の手順で導入してください．

### Linux / macOS の場合 <a id="pixi-install-unix"></a>

1. **公式インストールスクリプトの実行**<br>
   ターミナルを開き，以下のコマンドを実行して Pixi をインストールします．

   ```bash
   curl -fsSL https://pixi.sh/install.sh | bash
   ```

1. **シェルの再起動と確認**<br>
   ターミナルを再起動するか，環境設定ファイルを読み直した後，バージョンが表示されることを確認します．

   ```bash
   pixi --version
   ```

### Windows の場合 <a id="pixi-install-windows"></a>

1. **PowerShell スクリプトの実行**<br>
   PowerShell を開き，以下のコマンドを実行します．

   ```powershell
   iwr -useb https://pixi.sh/install.ps1 | iex
   ```

   または，Windows パッケージマネージャー（`winget`）を使用することも可能です．

   ```powershell
   winget install prefix-dev.pixi
   ```

1. **PowerShell の再起動と確認**<br>
   シェルを再起動し，以下のコマンドで正常に導入されたことを確認します．

   ```powershell
   pixi --version
   ```

---

## 2. リポジトリのセットアップ手順 <a id="repository-setup"></a>

1. **ワークスペースディレクトリへの移動**<br>
   ターミナルまたはコマンドラインで，本リポジトリのルートディレクトリに移動します．

   ```bash
   cd humanoid_hackathon_env
   ```

1. **依存関係のインストール（環境構築）**<br>
   以下のコマンドを実行します．初回実行時は [pixi.lock](pixi.lock) に基づいて必要な Python，CycloneDDS C ライブラリ，OpenCV，NumPy，および `unitree_sdk2py` が自動的にダウンロード・構成されます．

   ```bash
   pixi install
   ```

1. **動作確認タスクの実行**<br>
   インストール完了後，環境検証タスクを実行して SDK が正常に読み込めるか確認します．

   ```bash
   pixi run verify-sdk
   ```

   ターミナルに以下が出力されれば，セットアップは正常に完了しています．

   ```text
   unitree_sdk2py & cyclonedds loaded successfully!
   ```

---

## 3. ロボットとの接続方法 <a id="robot-connection"></a>

ロボットと開発用 PC 間で制御プログラムや DDS 通信を行うためには，Ethernet（有線 LAN）ケーブルを用いて同一のローカルネットワーク（`192.168.123.0/24`）で接続します．

> [!IMPORTANT]
> **ロボット内蔵 PC（Onboard PC）への直接ログインおよび内部での開発作業は原則厳禁です．**
> 内蔵 PC は姿勢維持や歩行などの高周期リアルタイム制御を担当しています．すべての開発・検証プログラムは，必ず手元の開発用 PC 上で実行し，ネットワーク経由でロボットへ通信を行ってください．
>
> また，`unitree_sdk2py` の `ChannelFactoryInitialize()` はライブラリ内部で固定の CycloneDDS 設定を直接読み込む仕様となっているため，`CYCLONEDDS_URI` 等による外部 XML 設定ファイル（例: `cyclonedds.osx.xml`）は参照されません．通信インターフェースはプログラム引数（`-i` / `--interface`）経由で指定してください．

### 必要な機材と物理接続 <a id="hardware-connection"></a>

1. **必要な機材**<br>
   - **Ethernet ケーブル（LAN ケーブル）**：ロボットと PC をつなぐ標準的な有線 LAN ケーブル．
   - **開発用 PC**：プログラムを実行するノートパソコン等．
   - **USB-Ethernet 変換アダプタ**：PC に有線 LAN ポート（RJ45）がない場合に用意．
1. **ケーブルの接続**<br>
   Ethernet ケーブルの片側を**ロボットのうなじ（首の後ろ・背面上部）にある Ethernet ポート（RJ45）**に差し込み，もう片側を開発用 PC の有線 LAN ポートに差し込みます．

### IP アドレス設計 <a id="network-ip-settings"></a>

開発用 PC 側の有線 LAN アダプタには，以下の静的（手動）IP アドレスを設定します．

| 機器名 | IP アドレス | サブネットマスク | 役割・備考 |
| :--- | :--- | :--- | :--- |
| **ロボット** | `192.168.123.161` | `255.255.255.0` (`/24`) | 固定 IP（本体側の有線 LAN ポート） |
| **開発用 PC** | `192.168.123.164` | `255.255.255.0` (`/24`) | 手動設定（静的 IP，ゲートウェイ空欄） |

### 各 OS における IP アドレス設定手順 <a id="os-ip-setup"></a>

#### Windows 11 の場合

1. **イーサネットのプロパティを開く**<br>
   「設定」>「ネットワークとインターネット」>「イーサネット」を開きます．
1. **IP 割り当てを手動に設定**<br>
   「IP 割り当て」の「編集」をクリックし，「手動」を選択して「IPv4」をオンにします．
1. **設定値を入力して保存**<br>
   - **IP アドレス**: `192.168.123.164`
   - **サブネットマスク**: `255.255.255.0`
   - **ゲートウェイ**: 空欄

#### Ubuntu / Linux の場合

1. **NetworkManager や ip コマンドで設定**<br>
   GUI の「Settings」>「Network」から有線接続の IPv4 を「Manual」にし，Address: `192.168.123.164`, Netmask: `255.255.255.0` を設定します．
   （コマンドラインで行う場合は `sudo ip addr add 192.168.123.164/24 dev <インターフェース名>`）

#### macOS の場合

1. **ネットワーク環境設定を開く**<br>
   「システム設定」>「ネットワーク」から，接続している有線 LAN アダプタを選択します．
1. **IPv4 を手動設定**<br>
   「IPv4 の設定」を「手動」に切り替え，IP アドレス: `192.168.123.164`，サブネットマスク: `255.255.255.0`，ルーター: 空欄 にして適用します．

### 疎通確認（ping テスト） <a id="ping-test"></a>

1. **ping コマンドの実行**<br>
   ターミナル（Windows では PowerShell またはコマンドプロンプト）を開き，ロボットの固定 IP アドレス（`192.168.123.161`）に向けて ping を送信します．

   ```bash
   ping 192.168.123.161
   ```

1. **応答の確認**<br>
   以下のようにロボット（`192.168.123.161`）からの応答が返り，パケット損失が 0% であれば，開発用 PC とロボット間の有線ネットワーク疎通は正常に確立されています．

   ```text
   64 bytes from 192.168.123.161: icmp_seq=1 ttl=64 time=0.450 ms
   64 bytes from 192.168.123.161: icmp_seq=2 ttl=64 time=0.380 ms
   ```

---

## 4. サンプルコードの実行方法 <a id="sample-execution"></a>

### 4.1 音声合成（TTS 発話） <a id="sample-tts"></a>

`samples/sample_tts.py` は，Unitree ロボット（G1 や A2 などの音声サービス `voice` 搭載モデル）に対して，テキストを音声合成（TTS: $`\text{Text-to-Speech}`$）で発話させるサンプルプログラムです．

> [!NOTE]
> Unitree SDK2 の音声機能（`TtsMaker`）は，話者 ID（`speaker_id`）として **ID=0（中国語）** および **ID=1（英語）** のみをサポートしており，日本語の発話には対応していません．本サンプルでは英語（ID=1）のテキストを発話させています．

#### サンプルコードの実行 <a id="sample-tts-run"></a>

1. **ネットワークインターフェースを指定して実行**<br>
   ロボットと直結したネットワークインターフェース名（例: `en7`, `eth0` 等）を指定して発話させます．

   ```bash
   pixi run sample-tts -i en7
   ```

#### CLI 引数の詳細オプション <a id="sample-tts-cli-options"></a>

ヘルプメッセージは以下のコマンドで確認できます．

```bash
pixi run sample-tts --help
```

| オプション | 型 | 必須 | 説明 |
| :--- | :--- | :--- | :--- |
| `-i`, `--interface` | `str` | ○ | ロボット接続用ネットワークインターフェース名（例: `en7`） |

---

### 4.2 基本移動（歩行・旋回） <a id="sample-walk"></a>

`samples/sample_walk.py` は，Unitree G1 ロボットの移動制御サービス（`sport`）に対して，X 方向（前進），Y 方向（横移動），Theta 方向（旋回）への移動をそれぞれ 3 秒間実行し，最後に安全に停止させるサンプルプログラムです．

> [!WARNING]
> **安全上の警告**
> - ロボットが実際に歩行・旋回運動を行います．必ず周囲に障害物や人がいない安全なスペースを確保してください．
> - 万一の事態に備え，いつでも非常停止できるようにリモコンや電源スイッチを操作できる状態で実行してください．

#### 動作シーケンス <a id="sample-walk-sequence"></a>

1. **初期化**: 指定されたネットワークインターフェースで DDS 通信および `LocoClient` を初期化します．
1. **X 方向移動（前進）**: $v_x = 0.4\text{ m/s}$ で 3 秒間前進します．
1. **Y 方向移動（横移動）**: $v_y = 0.4\text{ m/s}$ で 3 秒間左方向へ横移動します．
1. **Theta 方向移動（旋回）**: $\omega = 0.4\text{ rad/s}$ で 3 秒間反時計回りに旋回します．
1. **停止**: `StopMove()` を呼び出して全速度を 0 にし，安全に停止します．

#### サンプルコードの実行 <a id="sample-walk-run"></a>

1. **ネットワークインターフェースを指定して実行**<br>
   ロボットと直結したネットワークインターフェース名（例: `en7`, `eth0` 等）を指定して実行します．

   ```bash
   pixi run sample-walk -i en7
   ```

#### CLI 引数の詳細オプション <a id="sample-walk-cli-options"></a>

ヘルプメッセージは以下のコマンドで確認できます．

```bash
pixi run sample-walk --help
```

| オプション | 型 | 必須 | 説明 |
| :--- | :--- | :--- | :--- |
| `-i`, `--interface` | `str` | ○ | ロボット接続用ネットワークインターフェース名（例: `en7`） |

---

## 5. 自作プログラムの作成・実行方法 <a id="custom-program"></a>

本リポジトリでは，自作の制御スクリプトや実験用プログラムを `scripts/` ディレクトリ配下に配置して開発・実行することを推奨しています．

### テンプレートスクリプト（`scripts/template.py`）の活用 <a id="use-template"></a>

`scripts/template.py` には，DDS チャンネル通信の初期化およびネットワークインターフェース指定用のコマンドライン引数解析があらかじめ組み込まれています．これを複製して独自のプログラムを実装できます．

```python
#!/usr/bin/env python3
import argparse
from pathlib import Path
from unitree_sdk2py.core.channel import ChannelFactoryInitialize


def main() -> None:
    # ネットワークインターフェース指定用の引数パーサーを設定
    parser = argparse.ArgumentParser(description="Unitree SDK2 program template")
    parser.add_argument("-i", "--interface", type=str, default=None, help="Network interface")
    args = parser.parse_args()

    # Windows 環境等での CycloneDDS ログ出力先ディレクトリを確保
    Path("/tmp").mkdir(exist_ok=True)

    # DDS チャンネル通信を初期化（ドメインID: 0，インターフェース指定）
    ChannelFactoryInitialize(0, args.interface)

    print("DDS initialized successfully.")
    # ここに任意のロボット制御コードやクライアント呼び出しを記述します


if __name__ == "__main__":
    main()
```

### プログラムの実行手順 <a id="run-custom-program"></a>

1. **直接コマンドラインから実行する場合**<br>
   `pixi run python` を使用することで，Pixi が管理する仮想環境上で直接スクリプトを実行できます．

   ```bash
   # 自動検出モードで実行
   pixi run python scripts/template.py

   # ネットワークインターフェースを指定して実行
   pixi run python scripts/template.py -i enp2s0
   ```

1. **Pixi タスクに登録して実行する場合**<br>
   頻繁に実行するスクリプトは，[pixi.toml](pixi.toml) の `[tasks]` セクションに登録することで，ショートカットコマンドとして実行可能になります．

   ```toml
   [tasks]
   my-script = "python scripts/my_script.py"
   ```

   登録後は，以下のコマンドで引数を渡して実行できます．

   ```bash
   pixi run my-script -i enp2s0
   ```

