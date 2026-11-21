import json
import wave

import pytest
from PIL import Image, ImageFont

from src.config import load_config
from src.upload.description import build_description, timestamp
from src.video.audio import concat_wavs
from src.video.compose import ffmpeg_command
from src.video.subtitles import LEAD_IN_SEC, TAIL_SEC, build_timeline, draw_subtitle, wrap_text

LINES = [
    {"scene_id": "01_opening", "text": "a", "wav": "01_01.wav", "duration": 1.0},
    {"scene_id": "01_opening", "text": "b", "wav": "01_02.wav", "duration": 2.0},
    {"scene_id": "02_tender", "text": "c", "wav": "02_01.wav", "duration": 1.5},
]


def test_build_timeline():
    tl = build_timeline(LINES, gap=0.5)
    starts = [line["start"] for line in tl["lines"]]
    assert starts == [0.0, LEAD_IN_SEC + 1.5, LEAD_IN_SEC + 1.5 + 2.5]
    assert tl["total"] == pytest.approx(LEAD_IN_SEC + 1.5 + 2.5 + 1.5 + TAIL_SEC)
    assert [s["scene_id"] for s in tl["scenes"]] == ["01_opening", "02_tender"]
    assert sum(line["display"] for line in tl["lines"]) == pytest.approx(tl["total"])


def test_build_timeline_empty():
    with pytest.raises(ValueError):
        build_timeline([], gap=0.3)


def _write_wav(path, seconds, rate=24000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(seconds * rate))


def test_concat_wavs_matches_timeline(tmp_path):
    for line in LINES:
        _write_wav(tmp_path / line["wav"], line["duration"])
    tl = build_timeline(LINES, gap=0.5)
    out = tmp_path / "narration.wav"
    concat_wavs(tl, tmp_path, out)
    with wave.open(str(out), "rb") as w:
        assert w.getnframes() / w.getframerate() == pytest.approx(tl["total"], abs=0.01)


def test_concat_wavs_rejects_mixed_formats(tmp_path):
    _write_wav(tmp_path / "01_01.wav", 1.0)
    _write_wav(tmp_path / "01_02.wav", 1.0, rate=48000)
    _write_wav(tmp_path / "02_01.wav", 1.0)
    with pytest.raises(RuntimeError):
        concat_wavs(build_timeline(LINES, gap=0.5), tmp_path, tmp_path / "out.wav")


def test_wrap_text_keeps_punctuation_off_line_start():
    font = ImageFont.truetype(load_config()["video"]["font"], size=40)
    rows = wrap_text("あ" * 30 + "。", font, max_width=int(font.getlength("あ" * 30)))
    assert len(rows) == 1 and rows[0].endswith("。")
    assert "".join(wrap_text("い" * 50, font, 400)) == "い" * 50


def test_draw_subtitle(tmp_path):
    base = tmp_path / "base.png"
    Image.new("RGB", (1920, 1080), "navy").save(base)
    out = tmp_path / "frame.png"
    draw_subtitle(base, "テスト字幕です。", out, load_config()["video"]["font"], 0.17)
    img = Image.open(out)
    assert img.size == (1920, 1080)
    assert img.getpixel((10, 1070)) != img.getpixel((10, 10))  # 字幕帯で暗くなる


def test_ffmpeg_command_with_and_without_bgm(tmp_path):
    vcfg = load_config()["video"]
    cmd = ffmpeg_command(tmp_path / "l", tmp_path / "n.wav", tmp_path / "o.mp4", vcfg, 10.0, "libx264", None)
    assert "libx264" in cmd and "-filter_complex" not in cmd
    cmd = ffmpeg_command(tmp_path / "l", tmp_path / "n.wav", tmp_path / "o.mp4", vcfg, 10.0,
                         "h264_videotoolbox", tmp_path / "bgm.mp3")
    assert "-filter_complex" in cmd and "h264_videotoolbox" in cmd


@pytest.mark.parametrize("sec,expected", [(0, "0:00"), (75.9, "1:15"), (3661, "1:01:01")])
def test_timestamp(sec, expected):
    assert timestamp(sec) == expected


def test_build_description(example_script):
    tl = build_timeline(LINES, gap=0.5)
    text = build_description(example_script, tl, load_config(), "ずんだもん")
    assert "VOICEVOX:ずんだもん" in text
    assert "投資助言ではありません" in text
    assert "0:00 オープニング" in text and "公開買付（TOB）" in text
