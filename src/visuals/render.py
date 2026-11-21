"""[4. visual] data.json と script.json からシーンごとの画像 img/<scene_id>.png とサムネイルを作る。

グラフのシーンは、アニメーションのコマ img/<scene_id>_anim/NNNN.png も書き出す
(動画では各シーン最初のセリフの表示時間の中で再生するので、尺は変わらない)。
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from src.config import DayPaths, load_config
from src.tts.voices import pick_voice
from src.visuals import charts, slides, thumbnail
from src.visuals import theme as t

log = logging.getLogger(__name__)

# progress (0〜1) を受け取ってアニメーションできる描画関数。キーは台本スキルと取り決めた visual ID
ANIMATED = {
    "filings_bar": charts.filings_bar,
    "holdings_table": charts.holdings_table,
    "usdjpy_line": charts.usdjpy_line,
    "jgb_yields": charts.jgb_yields,
}


def render_animation(renderer, data: dict, anim_dir: Path, n_frames: int) -> list[Path]:
    """最後のコマ (progress=1) は静止画と同じなので書かない。"""
    if anim_dir.exists():
        shutil.rmtree(anim_dir)
    anim_dir.mkdir(parents=True)
    frames = []
    for i in range(n_frames - 1):
        frame = anim_dir / f"{i:04d}.png"
        renderer(data, frame, progress=t.ease_out((i + 1) / n_frames))
        frames.append(frame)
    return frames


def speaker_name(paths: DayPaths, cfg: dict, date: str) -> str:
    """エンディングのクレジット。実際に読み上げた声 (manifest) を優先する。"""
    if paths.audio_manifest.exists():
        return json.loads(paths.audio_manifest.read_text(encoding="utf-8"))["speaker_name"]
    return pick_voice(cfg["voicevox"], date)["name"]


def render(date: str) -> list[Path]:
    cfg = load_config()
    vcfg = cfg["video"]
    paths = DayPaths.for_date(date)
    data = json.loads(paths.data_json.read_text(encoding="utf-8"))
    script = json.loads(paths.script_json.read_text(encoding="utf-8"))
    ch = cfg["channel"]
    voice_name = speaker_name(paths, cfg, date)
    renderers = {
        **ANIMATED,
        "title": slides.title,
        "events_list": slides.events_list,
        "ending": lambda d, out: slides.ending(d, out, voice_name, ch["disclaimer"],
                                              ch["data_credits"]),
    }
    n_frames = max(2, round(vcfg["animation_seconds"] * vcfg["animation_fps"]))
    outputs = []
    for scene in script["scenes"]:
        out = paths.img_dir / f"{scene['id']}.png"
        renderer = renderers.get(scene["visual"])
        if renderer is None:
            raise RuntimeError(f"未対応の visual です: {scene['visual']}")
        renderer(data, out)
        if scene["visual"] in ANIMATED:
            render_animation(renderer, data, paths.anim_dir(scene["id"]), n_frames)
        outputs.append(out)
    thumbnail.render(data, paths.thumbnail)
    log.info("%d 枚の画像とサムネイルを作成しました", len(outputs))
    return outputs
