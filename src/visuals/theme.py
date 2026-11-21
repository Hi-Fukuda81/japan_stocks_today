"""図表の共通テーマ (配色・フォント・レイアウト)。"""

from __future__ import annotations

from datetime import date as Date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from src.config import load_config  # noqa: E402

BG = "#0f172a"
PANEL = "#1e293b"
GRID = "#334155"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
WARM = "#f59e0b"
FAINT = "#475569"  # 免責文など、読めるが目立たせない文字
ACCENT = "#38bdf8"

SUBTITLE_BAND_RATIO = 0.17  # 画面下部を字幕用に空けておく割合
DPI = 100

_font_ready = False


def setup_fonts() -> None:
    global _font_ready
    if _font_ready:
        return
    vcfg = load_config()["video"]
    for path in (vcfg["font"], vcfg["font_regular"]):
        font_manager.fontManager.addfont(path)
    name = font_manager.FontProperties(fname=vcfg["font"]).get_name()
    plt.rcParams.update({
        "font.family": name, "axes.unicode_minus": False,
        "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
        "text.color": TEXT, "axes.labelcolor": TEXT, "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.edgecolor": GRID,
    })
    _font_ready = True


def new_figure(title: str, label: str):
    """見出しと右上の注記 (データの日付など) 入りの 1920x1080 の図を作る。

    戻り値の rect は字幕帯を除いた描画領域 [l, b, w, h]。
    """
    setup_fonts()
    vcfg = load_config()["video"]
    fig = plt.figure(figsize=(vcfg["width"] / DPI, vcfg["height"] / DPI), dpi=DPI)
    fig.text(0.04, 0.93, title, fontsize=46, fontweight="bold", va="center")
    fig.text(0.96, 0.93, label, fontsize=28, color=MUTED, va="center", ha="right")
    fig.add_artist(plt.Line2D([0.04, 0.96], [0.875, 0.875], color=ACCENT, linewidth=3))
    bottom = SUBTITLE_BAND_RATIO + 0.03
    return fig, [0.06, bottom, 0.88, 0.84 - bottom]


def ease_out(p: float) -> float:
    """アニメーションの進み具合 (0〜1) を、終わりにかけて減速する曲線にする。"""
    p = min(max(p, 0.0), 1.0)
    return 1 - (1 - p) ** 3


def stagger(progress: float, i: int, n: int, span: float = 0.4) -> float:
    """n 個の要素を順番に出すときの、i 番目の不透明度 (0〜1)。"""
    start = (i / max(n - 1, 1)) * (1 - span)
    return min(max((progress - start) / span, 0.0), 1.0)


def ja_date(iso: str) -> str:
    d = Date.fromisoformat(iso)
    return f"{d.month}月{d.day}日"


def save(fig, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
