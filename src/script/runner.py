"""[2. script] Claude Code のスキル evening-disclosure-script を `claude -p` で起動して台本を作る。

台本作成のルールはスキル側 (.claude/skills/evening-disclosure-script/) にあり、ここにはプロンプトを持たない。
スキルが OK と言っても、最後にこのモジュールで validate.py を再実行する (最終ゲート)。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from src.config import REPO_ROOT, VALIDATE_SCRIPT, DayPaths, load_config

log = logging.getLogger(__name__)

ALLOWED_TOOLS = [
    "Read(output/**)", "Read(.claude/skills/evening-disclosure-script/**)",
    "Skill(evening-disclosure-script)",
    "Edit(output/**)",  # Edit ルールは Write を含むすべての編集ツールに効く
    "Bash(uv run python .claude/skills/evening-disclosure-script/scripts/validate.py:*)",
]
DISALLOWED_TOOLS = ["WebFetch", "WebSearch", "Edit(src/**)", "Read(.env)", "Read(.env.*)"]


class ScriptGenerationError(RuntimeError):
    pass


def build_command(date: str, skill: str, max_turns: int) -> list[str]:
    return [
        "claude", "-p", f"/{skill} {date}",
        "--output-format", "json",
        "--max-turns", str(max_turns),
        "--permission-mode", "dontAsk",
        "--allowedTools", ",".join(ALLOWED_TOOLS),
        "--disallowedTools", ",".join(DISALLOWED_TOOLS),
    ]


def child_env() -> dict[str, str]:
    """サブスクリプションで動かすため ANTHROPIC_API_KEY を子プロセスに渡さない。"""
    return {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}


def run_validate(day_dir: Path) -> tuple[bool, str]:
    res = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT), str(day_dir)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    return res.returncode == 0, res.stdout.strip()


def invoke_claude(date: str, cfg: dict) -> dict:
    cmd = build_command(date, cfg["skill"], cfg["max_turns"])
    try:
        res = subprocess.run(cmd, cwd=REPO_ROOT, env=child_env(), capture_output=True, text=True,
                             timeout=cfg["timeout_sec"])
    except FileNotFoundError as e:
        raise ScriptGenerationError("claude コマンドが見つかりません (PATH を確認してください)") from e
    except subprocess.TimeoutExpired as e:
        raise ScriptGenerationError(f"claude -p が {cfg['timeout_sec']} 秒でタイムアウトしました") from e
    try:
        result = json.loads(res.stdout) if res.stdout.strip() else {}
    except json.JSONDecodeError:
        result = {"result": res.stdout[-2000:]}
    if res.returncode != 0 or result.get("is_error"):
        detail = result.get("result") or res.stderr[-2000:] or f"exit {res.returncode}"
        raise ScriptGenerationError(f"claude -p が失敗しました: {detail}")
    log.info("claude -p 完了 (turns=%s, cost=%s)", result.get("num_turns"), result.get("total_cost_usd"))
    return result


def run_script_skill(date: str, attempts: int = 2) -> Path:
    cfg = load_config()["script"]
    paths = DayPaths.for_date(date)
    if not paths.data_json.exists():
        raise ScriptGenerationError(f"data.json がありません: {paths.data_json} (先に fetch を実行してください)")

    last_report = ""
    for attempt in range(1, attempts + 1):
        log.info("台本生成 %d/%d 回目", attempt, attempts)
        try:
            invoke_claude(date, cfg)
        except ScriptGenerationError as e:
            last_report = str(e)
            log.warning("%s", last_report)
            continue
        if not paths.script_json.exists():
            err = paths.script_error.read_text(encoding="utf-8") if paths.script_error.exists() else "理由不明"
            last_report = f"script.json が作られませんでした: {err}"
            log.warning("%s", last_report)
            continue
        ok, last_report = run_validate(paths.root)
        if ok:
            if paths.script_error.exists():
                paths.script_error.unlink()
            return paths.script_json
        log.warning("最終検証で NG:\n%s", last_report)
    raise ScriptGenerationError(f"台本が検証を通りませんでした:\n{last_report}")
