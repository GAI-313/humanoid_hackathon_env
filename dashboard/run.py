"""receiver（:8000）と Streamlit（:8501）を同時に起動する。Ctrl+C で両方止める。"""
from __future__ import annotations

import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "receiver:app", "--app-dir", str(HERE),
             "--host", "0.0.0.0", "--port", "8000"]
        ),
        # headless: 初回のメールアドレス入力待ちで止まるのを防ぐ（ブラウザは下で開く）
        subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", str(HERE / "app.py"),
             "--server.port", "8501", "--server.headless", "true",
             "--browser.gatherUsageStats", "false"],
            stdin=subprocess.DEVNULL,
        ),
    ]
    threading.Timer(3.0, webbrowser.open, args=("http://localhost:8501",)).start()
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    main()
