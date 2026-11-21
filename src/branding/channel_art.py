"""YouTube のチャンネルアート (バナー) とアイコンを作る。

uv run python -m src.branding.channel_art  →  assets/branding/banner.png, icon.png

- バナー: 2560x1440。どの端末でも切れないセーフエリア (中央 1546x423) に文字を収める。
- アイコン: 800x800。円形に切り抜かれるので、内容は中央の円の内側に収める。
"""

from __future__ import annotations

import logging
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.config import REPO_ROOT, load_config
from src.visuals import theme as t

log = logging.getLogger(__name__)
OUT_DIR = REPO_ROOT / "assets" / "branding"
BANNER_SIZE = (2560, 1440)
SAFE_AREA = (1546, 423)
ICON_SIZE = 800


def _rgb(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def _random_walk(n: int, seed: int) -> list[float]:
    rng = random.Random(seed)  # 装飾用。毎回同じ形になるよう固定シード
    values, v = [], 0.0
    for i in range(n):
        v += rng.gauss(0.08, 1.0) + 0.6 * math.sin(i / 9)
        values.append(v)
    return values


def _draw_chart_line(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], seed: int,
                     color: tuple[int, int, int, int], width: int) -> None:
    x0, y0, x1, y1 = box
    values = _random_walk(90, seed)
    lo, hi = min(values), max(values)
    pts = [(x0 + (x1 - x0) * i / (len(values) - 1), y1 - (y1 - y0) * (v - lo) / (hi - lo or 1))
           for i, v in enumerate(values)]
    draw.line(pts, fill=color, width=width, joint="curve")


def _draw_columns(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], seed: int, alpha: int) -> None:
    """装飾の棒グラフ。株価のローソク足ではなく、件数や割合を表す棒にする (このチャンネルは株価チャートを主役にしない)。"""
    rng = random.Random(seed)
    x0, y0, x1, y1 = box
    n = 46
    step = (x1 - x0) / n
    for i in range(n):
        height = (y1 - y0) * (0.25 + 0.6 * abs(math.sin(i / 7)) * rng.uniform(0.6, 1.0))
        color = _rgb(t.WARM if i % 6 == 0 else t.ACCENT, alpha)
        cx = x0 + step * (i + 0.5)
        draw.rounded_rectangle([cx - step * 0.28, y1 - height, cx + step * 0.28, y1], radius=6, fill=color)


def make_banner(name: str, tagline: str, topics: list[str], font_bold: str, font_regular: str) -> Image.Image:
    w, h = BANNER_SIZE
    img = Image.new("RGBA", BANNER_SIZE, _rgb(t.BG))
    layer = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for x in range(0, w, 80):
        draw.line([(x, 0), (x, h)], fill=_rgb(t.GRID, 70), width=1)
    for y in range(0, h, 80):
        draw.line([(0, y), (w, y)], fill=_rgb(t.GRID, 70), width=1)
    _draw_columns(draw, (0, int(h * 0.62), w, int(h * 0.95)), seed=7, alpha=60)
    _draw_chart_line(draw, (0, int(h * 0.2), w, int(h * 0.8)), seed=3, color=_rgb(t.ACCENT, 90), width=6)
    img = Image.alpha_composite(img, layer)

    # セーフエリアの背後を少し暗くして文字を読みやすくする
    sw, sh = SAFE_AREA
    sx, sy = (w - sw) // 2, (h - sh) // 2
    veil = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(veil).rounded_rectangle([sx - 40, sy - 10, sx + sw + 40, sy + sh + 10], radius=36,
                                           fill=_rgb(t.BG, 215))
    img = Image.alpha_composite(img, veil)
    draw = ImageDraw.Draw(img)

    title_font = _font(font_bold, 150)
    while draw.textlength(name, font=title_font) > sw - 80:
        title_font = _font(font_bold, title_font.size - 6)
    cx = w / 2
    draw.text((cx, sy + 130), name, font=title_font, fill=_rgb(t.TEXT), anchor="mm")
    draw.line([(cx - 200, sy + 225), (cx + 200, sy + 225)], fill=_rgb(t.WARM), width=6)
    draw.text((cx, sy + 285), tagline, font=_font(font_regular, 60), fill=_rgb(t.WARM), anchor="mm")

    chip_font = _font(font_bold, 36)
    widths = [draw.textlength(tp, font=chip_font) + 56 for tp in topics]
    gap = 22
    x = cx - (sum(widths) + gap * (len(topics) - 1)) / 2
    y = sy + 370
    for tp, cw in zip(topics, widths):
        draw.rounded_rectangle([x, y - 30, x + cw, y + 30], radius=30, outline=_rgb(t.MUTED), width=3)
        draw.text((x + cw / 2, y), tp, font=chip_font, fill=_rgb(t.TEXT), anchor="mm")
        x += cw + gap
    return img.convert("RGB")


def make_icon(font_bold: str) -> Image.Image:
    """米国株モーニングデータのアイコンと同じ構図で、色だけ変える (輪と強調をオレンジに)。"""
    s = ICON_SIZE
    img = Image.new("RGBA", (s, s), _rgb(t.BG))
    draw = ImageDraw.Draw(img)
    c, r = s / 2, s * 0.47
    draw.ellipse([c - r, c - r, c + r, c + r], outline=_rgb(t.WARM), width=14)

    base = s * 0.66
    bars = [(0.25, 0.12, t.ACCENT), (0.36, 0.20, t.ACCENT), (0.47, 0.17, t.ACCENT), (0.58, 0.27, t.ACCENT),
            (0.69, 0.36, t.WARM)]
    bw = s * 0.075
    for fx, fh, color in bars:
        x = s * fx
        draw.rounded_rectangle([x, base - s * fh, x + bw, base], radius=10, fill=_rgb(color))
    pts = [(s * fx + bw / 2, base - s * fh - s * 0.06) for fx, fh, _ in bars]
    draw.line(pts, fill=_rgb(t.TEXT), width=16, joint="curve")
    ex, ey = pts[-1]
    draw.polygon([(ex + 34, ey - 30), (ex - 14, ey - 22), (ex + 22, ey + 16)], fill=_rgb(t.TEXT))

    draw.text((c, s * 0.79), "日本株", font=_font(font_bold, 112), fill=_rgb(t.TEXT), anchor="mm")
    return img.convert("RGB")


def main() -> list[Path]:
    cfg = load_config()
    ch, vcfg = cfg["channel"], cfg["video"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    banner = OUT_DIR / "banner.png"
    icon = OUT_DIR / "icon.png"
    make_banner(ch["name"], ch["tagline"], ch["topics"], vcfg["font"], vcfg["font_regular"]).save(banner)
    make_icon(vcfg["font"]).save(icon)
    log.info("チャンネルアートを作成しました: %s, %s", banner, icon)
    return [banner, icon]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
