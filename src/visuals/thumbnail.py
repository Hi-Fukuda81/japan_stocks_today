"""YouTube サムネイル (1280x720)。

米国株モーニングデータのサムネイルと構図を揃える。株価チャートの代わりに、保有割合がいちばん大きく動いた
大量保有報告を主役にし、背景に保有割合の横棒を敷く。文言は data.json から機械的に作るので、売買の示唆になる表現は入らない。
"""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.config import load_config
from src.visuals import slides

W, H = 1280, 720
BG, BLACK, WHITE, YELLOW, TAG = (8, 8, 10), (0, 0, 0), (255, 255, 255), (255, 214, 0), (200, 30, 45)
MARGIN = 40


def _fit(draw, text: str, font_path: str, size: int, max_w: float) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(font_path, size)
    while draw.textlength(text, font=font) > max_w and font.size > 20:
        font = ImageFont.truetype(font_path, int(font.size) - 4)
    return font


def headline(data: dict) -> tuple[str, str]:
    """(大きい見出し, 補足)。保有割合がいちばん大きく動いた会社を主役にする。なければ公開買付の件数。"""
    topics = slides.headline_topics(data, 1)
    if topics:
        return topics[0]
    f = data["filings"]
    return f"公開買付 {f['tender_offers']['count']}件", f"大量保有 {f['large_holdings']['count']}件"


def _md(iso: str) -> str:
    d = Date.fromisoformat(iso)
    return f"{d.month}/{d.day}"


def tag_for(data: dict) -> str:
    if data.get("edition") == "weekly":
        return f"週間まとめ {_md(data['period']['start'])}〜{_md(data['period']['end'])}"
    mark = "朝" if data.get("edition") == "morning" else "夕"
    return f"きょうの日本株【{mark}】{_md(data['date'])}"


GREEN, RED, GREY = (0, 200, 100), (240, 30, 45), (120, 120, 132)
GRID, AXIS_TEXT, BAR_BEFORE = (40, 40, 48), (200, 200, 210), (58, 58, 70)
AXIS_W = 110  # 右端の目盛りの幅 (米国株モーニングデータのサムネイルと同じ構図)
VERBS = {"増加": "保有増", "減少": "保有減", "新規": "新規保有"}
COLORS = {"増加": GREEN, "減少": RED, "新規": YELLOW}


def star(data: dict) -> dict | None:
    """主役にする大量保有報告。保有割合がいちばん大きく動いたもの、なければ新規で割合が最大のもの。"""
    items = [x for x in data["filings"]["large_holdings"]["items"] if x.get("ratio_pct") is not None]
    moved = sorted((x for x in items if x.get("change_pt")), key=lambda x: -abs(x["change_pt"]))
    new = sorted((x for x in items if x.get("direction") == "新規"), key=lambda x: -x["ratio_pct"])
    return (moved or new or [None])[0]


def _sticker(draw, xy, text, font, fill, anchor="ls", inner=10, outer=0) -> None:
    """黒縁 (必要なら外側に白縁も) を付けた文字。"""
    if outer:
        draw.text(xy, text, font=font, fill=WHITE, anchor=anchor, stroke_width=inner + outer, stroke_fill=WHITE)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=inner, stroke_fill=BLACK)


def _ratio_bars(draw, item: dict, font_path: str) -> None:
    """背景の図: 保有割合を横棒で見せる (上が前回、下が今回)。右端に 0〜100% の目盛り。"""
    x0, x1, y0, y1 = 0, W - AXIS_W, 150, H - 100
    small = ImageFont.truetype(font_path, 22)
    for k in range(6):
        x = x0 + (x1 - x0) * k / 5
        draw.line([(x, y0), (x, y1)], fill=GRID, width=1)
        draw.text((x - 6 if k else 6, y1 + 6), f"{k * 20}%", font=small, fill=AXIS_TEXT, anchor="ra" if k else "la")
    color = COLORS.get(item.get("direction"), GREY)
    mid = (y0 + y1) / 2
    prev, now = item.get("prev_ratio_pct"), item["ratio_pct"]
    if prev is not None:
        draw.rectangle([x0, y0 + 20, x0 + (x1 - x0) * min(prev, 100) / 100, mid - 12], fill=BAR_BEFORE)
    end = x0 + (x1 - x0) * min(now, 100) / 100
    dark = tuple(int(c * 0.42) for c in color)
    draw.rectangle([x0, mid + 12, end, y1 - 20], fill=dark)
    draw.line([(end, mid + 12), (end, y1 - 20)], fill=color, width=10)


def _headline(draw, item: dict, font_path: str) -> None:
    name, verb = item["issuer"], VERBS.get(item.get("direction"), "大量保有")
    big, small = 210, 120
    while True:
        fb, fs = ImageFont.truetype(font_path, big), ImageFont.truetype(font_path, small)
        if draw.textlength(name, font=fb) + draw.textlength(verb, font=fs) + 60 <= W - 40 or big <= 70:
            break
        big, small = big - 8, max(small - 4, 60)
    x, base = 36, 350
    _sticker(draw, (x, base), name, fb, WHITE, inner=12)
    _sticker(draw, (x + draw.textlength(name, font=fb) + 24, base), verb, fs, WHITE, inner=10)
    now = f"{item['ratio_pct']:.2f}%"
    before = f"{item['prev_ratio_pct']:.2f}%→" if item.get("prev_ratio_pct") is not None else ""
    size = 200
    while True:
        fn, fp = ImageFont.truetype(font_path, size), ImageFont.truetype(font_path, int(size * 0.5))
        if draw.textlength(before, font=fp) + draw.textlength(now, font=fn) + 80 <= W - 40 or size <= 80:
            break
        size -= 8
    if before:
        _sticker(draw, (x, 580), before, fp, WHITE, inner=8)
    _sticker(draw, (x + draw.textlength(before, font=fp) + (16 if before else 0), 580), now, fn,
             COLORS.get(item.get("direction"), WHITE), inner=10, outer=8)


def _chips(draw, item: dict, others: list[tuple[str, str]], font_path: str) -> None:
    """下端の小さなパネル: 提出者と、ほかに動きの大きかった会社。"""
    f_label, f_val = ImageFont.truetype(font_path, 24), ImageFont.truetype(font_path, 30)
    filer = item["filer"] if len(item["filer"]) <= 14 else item["filer"][:13] + "…"
    chips = [("提出者", filer)] + [(n if len(n) <= 10 else n[:9] + "…", m) for n, m in others]
    x, y, gap = 36, H - 76, 16
    for label, value in chips:
        w = draw.textlength(label, font=f_label) + draw.textlength(value, font=f_val) + gap * 3
        if x + w > W - 20:
            break
        draw.rounded_rectangle([x, y, x + w, y + 54], radius=10, fill=(20, 20, 24), outline=(90, 90, 100), width=2)
        draw.text((x + gap, y + 27), label, font=f_label, fill=(210, 210, 210), anchor="lm")
        draw.text((x + gap * 2 + draw.textlength(label, font=f_label), y + 27), value, font=f_val, fill=WHITE,
                  anchor="lm")
        x += w + 14


def render(data: dict, out: Path, font_path: str | None = None) -> Path:
    """米国株モーニングデータと同じ構図: 左上に赤いタグ、極太の縁取り文字、背景に図、下端に小さなパネル。"""
    font: str = font_path or load_config()["video"]["font_heavy"]
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    item = star(data)
    if item:
        _ratio_bars(draw, item, font)
    tag = tag_for(data)
    tag_font = ImageFont.truetype(font, 60)
    draw.rectangle([0, 14, draw.textlength(tag, font=tag_font) + 50, 104], fill=TAG)
    draw.text((24, 59), tag, font=tag_font, fill=WHITE, anchor="lm")
    if item:
        _headline(draw, item, font)
        others = [t for t in slides.headline_topics(data, 3) if t[0] != item["issuer"]][:1]
        _chips(draw, item, others, font)
    else:
        main, sub = headline(data)
        _sticker(draw, (MARGIN, 400), main, _fit(draw, main, font, 210, W - MARGIN * 2 - 24), YELLOW, inner=12)
        _sticker(draw, (MARGIN, 600), sub, _fit(draw, sub, font, 120, W - MARGIN * 2 - 20), WHITE, inner=10)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
