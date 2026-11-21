"""文字中心のシーン: タイトル・開示イベントの一覧・エンディング。"""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Rectangle

from src.config import load_config
from src.visuals import theme as t

MAX_EVENT_ROWS = 8


def _blank_figure():
    t.setup_fonts()
    vcfg = load_config()["video"]
    return plt.figure(figsize=(vcfg["width"] / t.DPI, vcfg["height"] / t.DPI), dpi=t.DPI)


def ratio_move(item: dict) -> str:
    """「16.52%→80.32%」「新規 54.12%」。保有割合がわからなければ空文字。"""
    if item.get("ratio_pct") is None:
        return ""
    if item.get("prev_ratio_pct") is None:
        return f"新規 {item['ratio_pct']:.2f}%" if item.get("direction") == "新規" else f"{item['ratio_pct']:.2f}%"
    return f"{item['prev_ratio_pct']:.2f}%→{item['ratio_pct']:.2f}%"


def headline_topics(data: dict, limit: int = 3) -> list[tuple[str, str]]:
    """タイトル画面とサムネイルに出す (会社名, 保有割合の動き)。動いた幅の大きい順、1社1件。なければ新規の報告。"""
    items = [x for x in data["filings"]["large_holdings"]["items"] if x.get("ratio_pct") is not None]
    moved = sorted((x for x in items if x.get("change_pt")), key=lambda x: -abs(x["change_pt"]))
    seen: set[str] = set()
    unique = [x for x in moved + [x for x in items if not x.get("change_pt")]
              if not (x["sec_code"] in seen or seen.add(x["sec_code"]))]
    return [(x["issuer"], ratio_move(x)) for x in unique[:limit]]


def title(data: dict, out: Path) -> None:
    fig = _blank_figure()
    d = Date.fromisoformat(data["date"])
    fig.text(0.5, 0.80, f"{d.year}年{d.month}月{d.day}日", ha="center", fontsize=44, color=t.MUTED)
    weekly = t.is_weekly(data)
    morning = data.get("edition") == "morning"
    name = "週間まとめ" if weekly else "朝のまとめ" if morning else "夕方のまとめ"
    fig.text(0.5, 0.67, f"きょうの日本株 {name}", ha="center", fontsize=96, fontweight="bold")
    sub = (f"{t.ja_date(data['period']['start'])}〜{t.ja_date(data['period']['end'])}の開示" if weekly
           else f"{t.filings_label(data)}の開示")
    fig.text(0.5, 0.585, sub, ha="center", fontsize=36, color=t.ACCENT)
    topics = headline_topics(data)
    if topics:
        fig.text(0.5, 0.49, "大量保有報告書で保有割合が大きく動いた会社", ha="center", fontsize=28, color=t.MUTED)
    for i, (company, move) in enumerate(topics):
        y = 0.41 - i * 0.075
        fig.text(0.47, y, company if len(company) <= 14 else company[:13] + "…", ha="right", fontsize=44,
                 fontweight="bold", va="center")
        fig.text(0.51, y, move, ha="left", fontsize=44, fontweight="bold", va="center", color=t.WARM)
    t.save(fig, out)


def event_rows(data: dict) -> list[tuple[str, str, str]]:
    """(区分, 会社, 提出事由) の一覧。臨時報告書だけ (公開買付は別のシーンで出す)。"""
    return [("臨時報告書", f"{e['filer']} ({e['sec_code']})", "・".join(e["reasons"]))
            for e in data["filings"]["extraordinary"]["items"]][:MAX_EVENT_ROWS]


def events_list(data: dict, out: Path) -> None:
    f = data["filings"]
    fig, rect = t.new_figure("臨時報告書 (会社の重要な出来事)", t.filings_label(data))
    rows = event_rows(data)
    y = rect[1] + rect[3] - 0.03
    if not rows:
        fig.text(0.5, 0.52, "該当する提出はありません", ha="center", fontsize=38, color=t.MUTED)
    for kind, company, detail in rows:
        fig.text(0.06, y, company if len(company) <= 17 else company[:16] + "…", fontsize=30, fontweight="bold",
                 va="center")
        fig.text(0.47, y, detail if len(detail) <= 26 else detail[:25] + "…", fontsize=28, va="center",
                 color=t.ACCENT)
        y -= 0.07
    fig.text(0.06, rect[1] - 0.005, f"上場会社の臨時報告書 {f['extraordinary']['listed_count']} 件から、"
             "支配や経営に関わるものを先に表示", fontsize=22, color=t.MUTED)
    t.save(fig, out)


def ending(data: dict, out: Path, speaker_name: str, disclaimer: str, credits: list[str]) -> None:
    """終了画面。YouTube Studio で置く「チャンネル登録」と「おすすめ動画」2本の場所を空けておく。"""
    fig = _blank_figure()
    fig.text(0.5, 0.90, "ご視聴ありがとうございました", ha="center", fontsize=52, fontweight="bold")
    # 画面は 16:9 なので、図の座標で幅と高さが同じ四角は 16:9 になる
    fig.patches.append(Ellipse((0.17, 0.61), 0.15, 0.15 * 16 / 9, transform=fig.transFigure, fill=False,
                               edgecolor=t.MUTED, linewidth=2, linestyle="--"))
    fig.text(0.17, 0.42, "チャンネル登録", ha="center", fontsize=34, fontweight="bold", color=t.ACCENT)
    for x in (0.34, 0.66):
        fig.patches.append(Rectangle((x, 0.47), 0.30, 0.30, transform=fig.transFigure, fill=False,
                                     edgecolor=t.MUTED, linewidth=2, linestyle="--"))
    fig.text(0.65, 0.42, "おすすめ動画", ha="center", fontsize=34, fontweight="bold", color=t.ACCENT)
    line = "データ出典: " + " / ".join(credits) + f"   音声: VOICEVOX:{speaker_name}"
    fig.text(0.5, 0.31, line, ha="center", fontsize=18, color=t.MUTED)
    # 免責文は読み上げず、字幕帯の上に薄い色で小さく表示する
    fig.text(0.5, t.SUBTITLE_BAND_RATIO + 0.04, disclaimer, ha="center", fontsize=18, color=t.FAINT)
    t.save(fig, out)
