# humanoid_hackathon_env セットアップガイド <a id="title"></a>

本リポジトリは，Unitree Robotics 社の人形ロボット向け Python 開発キットである `unitree_sdk2_python` （`unitree_sdk2py`）を，パッケージマネージャー `pixi` を用いてクロスプラットフォームに構築・実行するための開発環境です．

> [!NOTE]
> 本環境は **Linux (`linux-64`)**，**macOS Intel (`osx-64`)**，**macOS Apple Silicon (`osx-arm64`)**，**Windows (`win-64`)** の 4 プラットフォームに対応しています．CycloneDDS の C ライブラリを手動ビルドすることなく，`pixi install` コマンドのみで全自動セットアップが完了します．

---

## 目次 <a id="table-of-contents"></a>

1. [各 OS への Pixi インストール手順](#pixi-installation)
1. [リポジトリのセットアップ手順](#repository-setup)
1. [サンプルコード（TTS 発話）の実行方法](#sample-execution)
1. [クロスプラットフォーム動作の技術仕様](#technical-specifications)

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

## 3. サンプルコード（TTS 発話）の実行方法 <a id="sample-execution"></a>

`samples/sample_tts.py` は，Unitree R1 に対して，任意のテキストを音声合成（TTS: $`\text{Text-to-Speech}`$）で発話させるサンプルプログラムです．

### 単発で任意のテキストを発話させる場合 <a id="sample-single-run"></a>

1. **自動検出モードで実行**<br>
   ネットワークインターフェースを自動検出して発話させます．

   ```bash
   pixi run sample-tts "こんにちは，Unitree ロボットです．"
   ```

1. **ネットワークインターフェースや音量を指定して実行**<br>
   ロボットと直結したネットワークインターフェース名（例: `enp2s0`, `eth0`, `en0` 等）や，スピーカー音量（`0`〜`100`），話者 ID を指定して発話させます．

   ```bash
   pixi run sample-tts -i enp2s0 -v 85 -s 0 -t "音声発話テストを実行します．"
   ```

### 対話型モードで連続発話させる場合 <a id="sample-interactive-run"></a>

1. **対話型コンソールの起動**<br>
   テキスト引数を指定せずに起動すると，対話型モードに入ります．

   ```bash
   pixi run sample-tts -i enp2s0
   ```

1. **テキストの入力と発話**<br>
   プロンプト `TTS> ` が表示されたら，発話させたい文字列を入力して Enter キーを押します．終了する場合は `exit` と入力するか，`Ctrl+D`（Windows では `Ctrl+Z` + Enter）を押します．

   ```text
   TTS> こんにちは
   [Info] Sent successfully.
   TTS> exit
   [Info] Exiting interactive TTS mode.
   ```

### CLI 引数の詳細オプション <a id="cli-options"></a>

ヘルプメッセージは以下のコマンドで確認できます．

```bash
pixi run sample-tts --help
```

| オプション | 型 | デフォルト値 | 説明 |
| :--- | :--- | :--- | :--- |
| `text_pos` / `-t`, `--text` | `str` | `None` | 発話させるテキスト（省略時は対話モード） |
| `-i`, `--interface` | `str` | `None` | ロボット接続用ネットワークインターフェース名（省略時は自動検出） |
| `-d`, `--domain-id` | `int` | `0` | DDS ドメイン ID |
| `-s`, `--speaker-id` | `int` | `0` | 話者 ID |
| `-v`, `--volume` | `int` | `None` | 発話前に設定するスピーカー音量（0〜100） |
| `--timeout` | `float` | `10.0` | RPC 通信のタイムアウト秒数 |

---
