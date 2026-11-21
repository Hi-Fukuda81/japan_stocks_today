"""セリフごとの wav の長さからタイムラインを作り、字幕付きフレーム画像を描く。

この環境の ffmpeg には libass がないため、字幕は ASS ではなく画像に焼き込んでから合成する。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

LEAD_IN_SEC = 0.5   # 冒頭の無音
TAIL_SEC = 1.5      # 最後のセリフのあとの余白


def build_timeline(lines: list[dict], gap: float, end_screen_sec: float = 0.0) -> dict:
    """各セリフの開始・終了時刻と、シーンごとの開始時刻を計算する。

    各セリフは「音声の長さ + gap」だけ画面に表示する。冒頭の無音は最初のセリフに、末尾の余白は最後のセリフに含める。
    """
    if not lines:
        raise ValueError("セリフが1つもありません")
    t = 0.0
    entries, scenes = [], []
    for i, line in enumerate(lines):
        lead = LEAD_IN_SEC if i == 0 else 0.0
        tail = TAIL_SEC if i == len(lines) - 1 else gap
        start = t
        speech_start = t + lead
        end = speech_start + line["duration"] + tail
        if not scenes or scenes[-1]["scene_id"] != line["scene_id"]:
            scenes.append({"scene_id": line["scene_id"], "start": round(start, 3)})
        entries.append({**line, "start": round(start, 3), "speech_start": round(speech_start, 3),
                        "end": round(end, 3), "display": round(end - start, 3)})
        t = end
    # 最後のシーン (終了画面) を end_screen_sec 以上にする。足りない分は最後のセリフの表示を延ばす
    extra = end_screen_sec - (t - scenes[-1]["start"])
    if extra > 0:
        last = entries[-1]
        t = last["end"] + extra
        entries[-1] = {**last, "end": round(t, 3), "display": round(t - last["start"], 3)}
    return {"total": round(t, 3), "lines": entries, "scenes": scenes}


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """日本語向けに1文字ずつ詰めて折り返す。句読点が行頭に来ないようにする。"""
    rows, current = [], ""
    for ch in text:
        if font.getlength(current + ch) <= max_width or (ch in "、。」）)" and current):
            current += ch
        else:
            rows.append(current)
            current = ch
    if current:
        rows.append(current)
    return rows


def draw_subtitle(base: Path, text: str, out: Path, font_path: str, band_ratio: float) -> None:
    img = Image.open(base).convert("RGBA")
    w, h = img.size
    band_h = int(h * band_ratio)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([0, h - band_h, w, h], fill=(0, 0, 0, 170))
    font = ImageFont.truetype(font_path, size=int(h * 0.05))
    rows = wrap_text(text, font, int(w * 0.9))
    line_h = int(font.size * 1.3)
    y = h - band_h + (band_h - line_h * len(rows)) // 2
    for row in rows:
        x = (w - font.getlength(row)) / 2
        draw.text((x, y), row, font=font, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 255))
        y += line_h
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(img, overlay).convert("RGB").save(out)
