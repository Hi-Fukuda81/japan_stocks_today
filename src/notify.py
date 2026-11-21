"""完了・失敗の通知 (macOS 通知 + ntfy.sh)。通知の失敗でパイプラインは止めない。"""

from __future__ import annotations

import logging
import subprocess

import requests

from src.config import env

log = logging.getLogger(__name__)


def _applescript_quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, message: str, url: str | None = None) -> None:
    try:
        script = f'display notification "{_applescript_quote(message)}" with title "{_applescript_quote(title)}"'
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("macOS 通知に失敗しました: %s", e)
    topic = env("NTFY_TOPIC")
    if not topic:
        return
    headers = {"Title": title.encode("utf-8")}
    if url:
        headers["Click"] = url
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=message.encode("utf-8"), headers=headers, timeout=10)
    except requests.RequestException as e:
        log.warning("ntfy 通知に失敗しました: %s", e.__class__.__name__)
