"""設定ファイル (config.yaml) と出力パスの読み込み。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = REPO_ROOT / "output"
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "evening-disclosure-script"
VALIDATE_SCRIPT = SKILL_DIR / "scripts" / "validate.py"


@lru_cache(maxsize=1)
def load_config(path: str | None = None) -> dict[str, Any]:
    load_dotenv(REPO_ROOT / ".env")
    config_path = Path(path) if path else REPO_ROOT / "config.yaml"
    try:
        with config_path.open(encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError as e:
        raise RuntimeError(f"設定ファイルが見つかりません: {config_path}") from e


def env(name: str) -> str | None:
    load_dotenv(REPO_ROOT / ".env")
    value = os.environ.get(name, "").strip()
    return value or None


@dataclass(frozen=True)
class DayPaths:
    """1日分の成果物のパス。各ステップはここにあるファイルだけを受け渡す。"""

    root: Path

    @classmethod
    def for_date(cls, date: str, output_root: Path = OUTPUT_ROOT) -> "DayPaths":
        """date は slot_key の値 (夕方便・週間まとめは日付そのまま、朝便は「日付-am」)。"""
        return cls(output_root / date)

    @property
    def data_json(self) -> Path:
        return self.root / "data.json"

    @property
    def script_json(self) -> Path:
        return self.root / "script.json"

    @property
    def script_error(self) -> Path:
        return self.root / "script_error.txt"

    @property
    def audio_dir(self) -> Path:
        return self.root / "audio"

    @property
    def audio_manifest(self) -> Path:
        return self.audio_dir / "manifest.json"

    @property
    def img_dir(self) -> Path:
        return self.root / "img"

    @property
    def frames_dir(self) -> Path:
        return self.root / "frames"

    @property
    def video(self) -> Path:
        return self.root / "video.mp4"

    @property
    def thumbnail(self) -> Path:
        return self.root / "thumbnail.png"

    def anim_dir(self, scene_id: str) -> Path:
        """グラフのアニメーションのコマ (img/<scene_id>_anim/NNNN.png)。"""
        return self.img_dir / f"{scene_id}_anim"

    @property
    def timeline_json(self) -> Path:
        return self.root / "timeline.json"

    @property
    def description_txt(self) -> Path:
        return self.root / "description.txt"


MORNING_SUFFIX = "-am"


def slot_key(date: str, edition: str) -> str:
    """成果物を置くディレクトリ名。朝便と夕方便は同じ日付なので、朝便だけ「2026-11-20-am」にして分ける。"""
    return f"{date}{MORNING_SUFFIX}" if edition == "morning" else date


def slot_date(key: str) -> str:
    """slot_key から日付 (YYYY-MM-DD) を取り出す。"""
    return key[:10]
