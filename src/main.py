"""パイプライン全体の実行。ステップ単位でも実行できる。

例: uv run python -m src.main --step fetch --date 2026-11-20
    uv run python -m src.main --date 2026-11-21 --edition weekly   # 土曜の週間まとめ
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date as Date
from datetime import datetime
from zoneinfo import ZoneInfo

STEPS = ["fetch", "script", "tts", "visual", "video", "upload"]
log = logging.getLogger("pipeline")


def iso_date(value: str) -> str:
    try:
        return Date.fromisoformat(value).isoformat()
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"日付は YYYY-MM-DD 形式で指定してください: {value}") from e


def run_step(step: str, date: str, edition: str = "evening") -> None:
    if step == "fetch":
        from src.data.fetch import fetch

        fetch(date, edition)
    elif step == "script":
        from src.script.runner import run_script_skill

        run_script_skill(date)
    elif step == "tts":
        from src.tts.synthesize import synthesize

        synthesize(date)
    elif step == "visual":
        from src.visuals.render import render

        render(date)
    elif step == "video":
        from src.video.compose import compose

        compose(date)
    elif step == "upload":
        from src.upload.youtube import upload

        upload(date)
    else:
        raise ValueError(f"不明なステップです: {step}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="きょうの日本株 (夕方便・週間まとめ) の動画生成")
    parser.add_argument("--step", choices=["all", *STEPS], default="all")
    parser.add_argument("--date", type=iso_date, default=datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat(),
                        help="動画の日付 = 開示の対象日 (JST, YYYY-MM-DD)。既定は今日")
    parser.add_argument("--edition", choices=["evening", "weekly"], default="evening",
                        help="weekly は土曜の週間まとめ (直近の月〜金)。fetch だけが使い、以降のステップは data.json に従う")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    steps = STEPS if args.step == "all" else [args.step]
    for step in steps:
        log.info("=== %s (%s) ===", step, args.date)
        try:
            run_step(step, args.date, args.edition)
        except Exception as e:
            log.error("ステップ %s が失敗しました: %s", step, e, exc_info=True)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
