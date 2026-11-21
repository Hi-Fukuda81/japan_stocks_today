"""文字中心のシーン: タイトル・開示イベントの一覧・エンディング。"""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path

import matplotlib.pyplot as plt

from src.config import load_config
from src.visuals import theme as t

MAX_EVENT_ROWS = 8


def _blank_figure():
    t.setup_fonts()
    vcfg = load_config()["video"]
    return plt.figure(figsize=(vcfg["width"] / t.DPI, vcfg["height"] / t.DPI), dpi=t.DPI)


def headline_numbers(data: dict) -> list[tuple[str, int]]:
    """タイトル画面とサムネイルに出す件数。"""
    f = data["filings"]
    return [("提出書類", f["total"]), ("大量保有", f["large_holdings"]["count"]),
            ("臨時報告書", f["extraordinary"]["count"])]


def title(data: dict, out: Path) -> None:
    fig = _blank_figure()
    d = Date.fromisoformat(data["date"])
    fig.text(0.5, 0.78, f"{d.year}年{d.month}月{d.day}日", ha="center", fontsize=44, color=t.MUTED)
    weekly = t.is_weekly(data)
    fig.text(0.5, 0.64, "きょうの日本株 週間まとめ" if weekly else "きょうの日本株 夕方便", ha="center", fontsize=96,
             fontweight="bold")
    sub = f"{t.ja_date(data['period']['start'])}〜{t.ja_date(data['period']['end'])}の開示" if weekly else "大引け後の開示まとめ"
    fig.text(0.5, 0.555, sub, ha="center", fontsize=36, color=t.ACCENT)
    numbers = headline_numbers(data)
    for i, (label, count) in enumerate(numbers):
        x = (i + 0.5) / len(numbers) * 0.84 + 0.08
        fig.text(x, 0.40, label, ha="center", fontsize=30, color=t.MUTED)
        fig.text(x, 0.31, f"{count:,} 件", ha="center", fontsize=52, fontweight="bold")
    t.save(fig, out)


def event_rows(data: dict) -> list[tuple[str, str, str]]:
    """(区分, 会社, 内容) の一覧。公開買付を先に、続けて臨時報告書。"""
    f = data["filings"]
    rows = [("公開買付", f"{o['target']} ({o['sec_code']})" if o.get("target") else "対象会社は一覧に未収録",
             f"買付者: {o['filer']}") for o in f["tender_offers"]["items"]]
    rows += [("臨時報告書", f"{e['filer']} ({e['sec_code']})", "・".join(e["reasons"]))
             for e in f["extraordinary"]["items"]]
    return rows[:MAX_EVENT_ROWS]


def events_list(data: dict, out: Path) -> None:
    f = data["filings"]
    fig, rect = t.new_figure("公開買付・臨時報告書", t.filings_label(data))
    rows = event_rows(data)
    y = rect[1] + rect[3] - 0.03
    if not rows:
        fig.text(0.5, 0.52, "該当する提出はありません", ha="center", fontsize=38, color=t.MUTED)
    for kind, company, detail in rows:
        fig.text(0.06, y, kind, fontsize=24, fontweight="bold", va="center",
                 color=t.WARM if kind == "公開買付" else t.ACCENT)
        fig.text(0.19, y, company if len(company) <= 20 else company[:19] + "…", fontsize=28, fontweight="bold",
                 va="center")
        fig.text(0.55, y, detail if len(detail) <= 24 else detail[:23] + "…", fontsize=24, va="center")
        y -= 0.07
    fig.text(0.06, rect[1] - 0.005, f"公開買付届出書 {f['tender_offers']['count']} 件 / 臨時報告書 "
             f"{f['extraordinary']['count']} 件 / 自己株券買付状況報告書 {f['buybacks']['count']} 件",
             fontsize=22, color=t.MUTED)
    t.save(fig, out)


def ending(data: dict, out: Path, speaker_name: str, disclaimer: str, credits: list[str]) -> None:
    fig = _blank_figure()
    fig.text(0.5, 0.78, "ご視聴ありがとうございました", ha="center", fontsize=64, fontweight="bold")
    fig.text(0.5, 0.64, "データ出典", ha="center", fontsize=26, color=t.MUTED)
    for i, c in enumerate(credits):
        fig.text(0.5, 0.59 - i * 0.045, c, ha="center", fontsize=22, color=t.MUTED)
    fig.text(0.5, 0.59 - len(credits) * 0.045 - 0.02, f"音声: VOICEVOX:{speaker_name}", ha="center", fontsize=22,
             color=t.MUTED)
    # 免責文は読み上げず、字幕帯の上に薄い色で小さく表示する
    fig.text(0.5, t.SUBTITLE_BAND_RATIO + 0.04, disclaimer, ha="center", fontsize=18, color=t.FAINT)
    t.save(fig, out)
