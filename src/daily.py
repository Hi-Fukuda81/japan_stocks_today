"""夕方便・週間まとめの無人実行 (launchd から呼ばれる)。

- 多重起動を防ぐ (output/.lock)
- 月〜金は夕方便、土曜は週間まとめ (その週の月〜金) を作る
- 東証の休場日 (祝日・年末年始) と日曜は何もしない。営業日が1日もなかった週は週間まとめも作らない
- 当日分が投稿済みなら何もしない
- 成功・失敗を通知し、古い中間ファイルとログを掃除する
"""

from __future__ import annotations

import fcntl
import json
import logging
import shutil
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.config import OUTPUT_ROOT, REPO_ROOT, DayPaths, load_config
from src.data.calendar_jp import closed_reason, week_trading_days
from src.main import STEPS, run_step
from src.notify import notify

log = logging.getLogger("daily")
JST = ZoneInfo("Asia/Tokyo")
INTERMEDIATE_DIRS = ("audio", "img", "frames")
CHANNEL = "きょうの日本株"
WEEKLY_WEEKDAY = 5  # 土曜 (datetime.weekday)
EDITION_LABELS = {"evening": "夕方便", "weekly": "週間まとめ"}


class AlreadyRunning(RuntimeError):
    pass


@contextmanager
def single_instance(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise AlreadyRunning(f"別のパイプラインが実行中です ({lock_path})") from e
        f.write(str(datetime.now(JST)))
        f.flush()
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def already_uploaded(date: str, output_root: Path = OUTPUT_ROOT) -> dict | None:
    record = DayPaths.for_date(date, output_root).root / "upload.json"
    return json.loads(record.read_text(encoding="utf-8")) if record.exists() else None


def cleanup(output_root: Path, logs_root: Path, keep_intermediate_days: int, keep_log_days: int,
            now: float | None = None) -> None:
    now = now or time.time()
    for day_dir in output_root.glob("????-??-??"):
        for name in INTERMEDIATE_DIRS:
            target = day_dir / name
            if target.exists() and now - target.stat().st_mtime > keep_intermediate_days * 86400:
                shutil.rmtree(target, ignore_errors=True)
    for log_file in logs_root.glob("*.log"):
        if now - log_file.stat().st_mtime > keep_log_days * 86400:
            log_file.unlink(missing_ok=True)


def edition_for(date: str) -> str | None:
    """その日に作る動画。作らない日は None。"""
    day = datetime.fromisoformat(date)
    if day.weekday() == WEEKLY_WEEKDAY:
        # 土曜から見て直近の営業日が同じ週 (月曜以降) にあれば、まとめる中身がある
        days = week_trading_days(date)
        return "weekly" if (day - datetime.fromisoformat(days[-1])).days < 6 else None
    return None if closed_reason(date) else "evening"


def run(date: str) -> int:
    edition = edition_for(date)
    if edition is None:
        log.info("%s は配信のない日のためスキップします (%s)", date, closed_reason(date) or "営業日のない週")
        return 0
    record = already_uploaded(date)
    if record:
        log.info("%s は投稿済みです: %s", date, record.get("url"))
        return 0
    for step in STEPS:
        log.info("=== %s (%s, %s) ===", step, date, edition)
        run_step(step, date, edition)
    record = already_uploaded(date) or {}
    notify(CHANNEL, f"{date} の{EDITION_LABELS[edition]}を投稿しました ({record.get('privacy', '?')})。確認して公開してください",
           record.get("url"))
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()["daily"]
    date = datetime.now(JST).date().isoformat()
    try:
        with single_instance(REPO_ROOT / cfg["lock_file"]):
            code = run(date)
    except AlreadyRunning as e:
        log.warning("%s", e)
        return 0
    except Exception as e:
        log.error("実行に失敗しました: %s", e, exc_info=True)
        notify(f"{CHANNEL}: 失敗", f"{date} の実行に失敗しました: {str(e)[:120]}")
        return 1
    finally:
        try:
            cleanup(OUTPUT_ROOT, REPO_ROOT / "logs", cfg["keep_intermediate_days"], cfg["keep_log_days"])
        except OSError as e:
            log.warning("掃除に失敗しました: %s", e)
    return code


if __name__ == "__main__":
    sys.exit(main())
