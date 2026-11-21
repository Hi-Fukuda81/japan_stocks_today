"""YouTube サムネイル (1280x720)。

株価チャートは使わず、当日の開示の件数を大きく見せる。文言は data.json の件数から機械的に作るので、
売買の示唆になる表現は入らない。
"""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.config import load_config

W, H = 1280, 720
BG, BLACK, WHITE, YELLOW, TAG = (8, 8, 10), (0, 0, 0), (255, 255, 255), (255, 214, 0), (200, 30, 45)
MARGIN = 40


def _fit(draw, text: str, font_path: str, size: int, max_w: float) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(font_path, size)
    while draw.textlength(text, font=font) > max_w and font.size > 20:
        font = ImageFont.truetype(font_path, int(font.size) - 4)
    return font


def headline(data: dict) -> tuple[str, str]:
    """(大きい見出し, 補足)。公開買付があればそれを、なければ大量保有の件数を主役にする。"""
    f = data["filings"]
    if f["tender_offers"]["count"]:
        return f"公開買付 {f['tender_offers']['count']}件", f"大量保有 {f['large_holdings']['count']}件"
    return f"大量保有 {f['large_holdings']['count']}件", f"提出書類 {f['total']:,}件"


def _md(iso: str) -> str:
    d = Date.fromisoformat(iso)
    return f"{d.month}/{d.day}"


def tag_for(data: dict) -> str:
    if data.get("edition") == "weekly":
        return f"週間まとめ {_md(data['period']['start'])}〜{_md(data['period']['end'])}"
    return f"きょうの日本株【夕】{_md(data['date'])}"


def render(data: dict, out: Path, font_path: str | None = None) -> Path:
    font: str = font_path or load_config()["video"]["font_heavy"]
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    tag = tag_for(data)
    tag_font = ImageFont.truetype(font, 60)
    draw.rectangle([0, 14, draw.textlength(tag, font=tag_font) + 50, 104], fill=TAG)
    draw.text((24, 59), tag, font=tag_font, fill=WHITE, anchor="lm")
    main, sub = headline(data)
    main_font = _fit(draw, main, font, 210, W - MARGIN * 2 - 24)
    draw.text((MARGIN, 400), main, font=main_font, fill=YELLOW, anchor="ls", stroke_width=12, stroke_fill=BLACK)
    sub_font = _fit(draw, sub, font, 120, W - MARGIN * 2 - 20)
    draw.text((MARGIN, 600), sub, font=sub_font, fill=WHITE, anchor="ls", stroke_width=10, stroke_fill=BLACK)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
