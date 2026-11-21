"""[5. video] 画像・音声・字幕・BGM を ffmpeg で1本の mp4 にする。概要欄テキストも作る。"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from src.config import REPO_ROOT, DayPaths, load_config
from src.upload.description import build_description
from src.video.audio import concat_wavs
from src.video.subtitles import build_timeline, draw_subtitle
from src.visuals.theme import SUBTITLE_BAND_RATIO

log = logging.getLogger(__name__)


def plan_frames(timeline: dict, paths: DayPaths, fps: float) -> list[tuple[Path, str, float]]:
    """(元画像, 字幕, 表示秒数) の並び。

    各シーンの冒頭でアニメーションのコマを流し、終わったら静止画にする。コマはセリフの区切りをまたいで
    続けてよい (字幕だけ切り替わる)。各セリフの表示時間の合計は変えないので、動画の尺は伸びない。
    """
    plan: list[tuple[Path, str, float]] = []
    queue: list[Path] = []
    prev_scene = None
    for line in timeline["lines"]:
        scene, display, text = line["scene_id"], line["display"], line["text"]
        if scene != prev_scene:
            queue = sorted(paths.anim_dir(scene).glob("*.png"))
            prev_scene = scene
        take, queue = queue[:int(display * fps)], queue[int(display * fps):]
        plan += [(f, text, 1 / fps) for f in take]
        rest = display - len(take) / fps
        if queue and take:
            # アニメーションが次のセリフに続くときは、端数の時間を最後のコマに足す
            src, _, dur = plan[-1]
            plan[-1] = (src, text, dur + rest)
        elif rest > 1e-6:
            plan.append((paths.img_dir / f"{scene}.png", text, rest))
    return plan


def write_frames(timeline: dict, paths: DayPaths, font: str, fps: float) -> Path:
    """字幕付きフレームを描き、ffmpeg の concat デマルチプレクサ用のリストを書く。"""
    paths.frames_dir.mkdir(parents=True, exist_ok=True)
    for old in paths.frames_dir.glob("*.png"):
        old.unlink()
    entries = []
    plan = plan_frames(timeline, paths, fps)
    for i, (src, text, duration) in enumerate(plan, start=1):
        frame = paths.frames_dir / f"{i:05d}.png"
        draw_subtitle(src, text, frame, font, SUBTITLE_BAND_RATIO)
        entries.append(f"file '{frame.name}'\nduration {duration:.5f}")
    last = paths.frames_dir / f"{len(plan):05d}.png"
    listing = paths.frames_dir / "frames.ffconcat"
    listing.write_text("ffconcat version 1.0\n" + "\n".join(entries) + f"\nfile '{last.name}'\n", encoding="utf-8")
    return listing


def ffmpeg_command(listing: Path, narration: Path, out: Path, vcfg: dict, total: float, encoder: str,
                   bgm: Path | None) -> list[str]:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(narration)]
    if bgm:
        cmd += ["-stream_loop", "-1", "-i", str(bgm)]
        audio = (f"[2:a]volume={vcfg['bgm_volume_db']}dB[bgm];"
                 "[1:a][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
        cmd += ["-filter_complex", audio, "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    vcodec = ["-c:v", encoder, "-b:v", vcfg["bitrate"]] if encoder != "libx264" else [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    return cmd + [
        "-vf", f"fps={vcfg['fps']},scale={vcfg['width']}:{vcfg['height']},format=yuv420p",
        *vcodec, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-t", f"{total:.3f}", "-movflags", "+faststart", str(out),
    ]


def run_ffmpeg(listing: Path, narration: Path, out: Path, vcfg: dict, total: float, bgm: Path | None) -> None:
    encoders = [vcfg["encoder"]] + (["libx264"] if vcfg["encoder"] != "libx264" else [])
    last_err = ""
    for encoder in encoders:
        res = subprocess.run(ffmpeg_command(listing, narration, out, vcfg, total, encoder, bgm),
                             capture_output=True, text=True)
        if res.returncode == 0:
            log.info("エンコード完了 (%s)", encoder)
            return
        last_err = res.stderr.strip()[-1500:]
        log.warning("エンコーダ %s で失敗しました: %s", encoder, last_err)
    raise RuntimeError(f"ffmpeg での動画合成に失敗しました: {last_err}")


def compose(date: str) -> Path:
    cfg = load_config()
    vcfg = cfg["video"]
    paths = DayPaths.for_date(date)
    manifest = json.loads(paths.audio_manifest.read_text(encoding="utf-8"))
    script = json.loads(paths.script_json.read_text(encoding="utf-8"))
    timeline = build_timeline(manifest["lines"], cfg["voicevox"]["line_gap_sec"], cfg["video"].get("end_screen_sec", 0))
    paths.timeline_json.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")

    narration = paths.audio_dir / "narration.wav"
    concat_wavs(timeline, paths.audio_dir, narration)
    listing = write_frames(timeline, paths, vcfg["font"], vcfg["animation_fps"])
    bgm = REPO_ROOT / vcfg["bgm"] if vcfg.get("bgm") else None
    if bgm and not bgm.exists():
        log.info("BGM ファイルがないため BGM なしで合成します: %s", bgm)
        bgm = None
    run_ffmpeg(listing, narration, paths.video, vcfg, timeline["total"], bgm)

    description = build_description(script, timeline, cfg, manifest["speaker_name"])
    paths.description_txt.write_text(description, encoding="utf-8")
    log.info("動画を作成しました: %s (%.1f 秒)", paths.video, timeline["total"])
    return paths.video
