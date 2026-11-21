"""データを図にするシーン: 書類種別の件数・大量保有の一覧・ドル円・国債金利。

どの関数も progress (0〜1) を受け取り、1 未満ならアニメーションの途中のコマを描く。
"""

from __future__ import annotations

from pathlib import Path

from src.visuals import theme as t


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _clean_axes(ax) -> None:
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def filings_bar(data: dict, out: Path, progress: float = 1.0) -> None:
    f = data["filings"]
    fig, rect = t.new_figure("EDINET 提出書類の内訳", f"{t.ja_date(f['date'])} 提出分 / 全 {f['total']:,} 件")
    rows = list(reversed(f["by_type"]))  # 件数の多いものを上に
    ax = fig.add_axes([rect[0] + 0.24, rect[1] + 0.02, rect[2] - 0.32, rect[3] - 0.02])
    top = max(r["count"] for r in rows)
    ax.set_xlim(0, top * 1.15)
    ys = list(range(len(rows)))
    ax.barh(ys, [r["count"] * progress for r in rows], color=t.ACCENT, height=0.62)
    ax.set_yticks(ys, [_short(r["name"], 14) for r in rows], fontsize=26)
    for y, r in zip(ys, rows):
        ax.text(r["count"] * progress + top * 0.015, y, f"{round(r['count'] * progress):,} 件", va="center",
                fontsize=26, fontweight="bold")
    ax.tick_params(axis="x", labelsize=16)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=t.GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _clean_axes(ax)
    t.save(fig, out)


def holdings_table(data: dict, out: Path, progress: float = 1.0) -> None:
    h = data["filings"]["large_holdings"]
    fig, rect = t.new_figure("大量保有報告書・変更報告書", f"{t.ja_date(data['filings']['date'])} 提出分 / 全 {h['count']:,} 件")
    top = rect[1] + rect[3] - 0.01
    for x, label in ((0.06, "発行会社 (証券コード)"), (0.47, "提出者"), (0.82, "種類")):
        fig.text(x, top, label, fontsize=22, color=t.MUTED, va="center")
    items = h["items"]
    if not items:
        fig.text(0.5, 0.52, "上場会社についての提出はありません", ha="center", fontsize=38, color=t.MUTED)
    step = min(0.072, (rect[3] - 0.07) / max(len(items), 1))
    for i, item in enumerate(items):
        a = t.stagger(progress, i, len(items))
        if a <= 0:
            continue
        y = top - 0.065 - i * step
        is_new = item["kind"] == "大量保有報告書"
        fig.text(0.06, y, f"{_short(item['issuer'], 14)} ({item['sec_code']})", fontsize=30, fontweight="bold",
                 va="center", alpha=a)
        fig.text(0.47, y, _short(item["filer"], 17), fontsize=26, va="center", alpha=a)
        fig.text(0.82, y, "新規" if is_new else "変更", fontsize=28, fontweight="bold", va="center", alpha=a,
                 color=t.WARM if is_new else t.ACCENT)
    fig.text(0.06, rect[1] - 0.005, f"上場会社分 {h['listed_count']} 件のうち {len(items)} 件を表示  "
             f"(新規 {h['listed_new_count']} / 変更 {h['listed_change_count']})", fontsize=22, color=t.MUTED)
    t.save(fig, out)


def usdjpy_line(data: dict, out: Path, progress: float = 1.0) -> None:
    fx = data["usdjpy"]
    fig, rect = t.new_figure("ドル円 (東京市場 17時時点)", f"{t.ja_date(fx['date'])} 時点")
    ax = fig.add_axes([rect[0] + 0.02, rect[1] + 0.04, rect[2] - 0.24, rect[3] - 0.04])
    hist = fx["history"]
    xs = list(range(len(hist)))
    ys = [h["close"] for h in hist]
    n = min(len(xs), max(1, round(len(xs) * progress)))
    # 軸はアニメーション中も動かないよう、全期間の値で固定する
    ax.set_xlim(-0.5, max(len(xs) - 0.5, 0.5))
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.1 or 0.5
    ax.set_ylim(lo - pad, hi + pad)
    ax.plot(xs[:n], ys[:n], color=t.ACCENT, linewidth=4)
    ax.scatter([xs[n - 1]], [ys[n - 1]], s=220, color=t.ACCENT, zorder=5)
    ax.axhline(fx["period_high"], color=t.MUTED, linestyle="--", linewidth=1.5)
    ax.axhline(fx["period_low"], color=t.MUTED, linestyle="--", linewidth=1.5)
    ticks = xs[:: max(1, len(xs) // 6)]
    ax.set_xticks(ticks, [t.ja_date(hist[i]["date"]) for i in ticks], fontsize=18)
    ax.tick_params(axis="y", labelsize=18)
    ax.grid(color=t.GRID, linewidth=0.8)
    _clean_axes(ax)
    x0 = rect[0] + rect[2] - 0.2
    fig.text(x0, rect[1] + rect[3] * 0.84, "17時時点", fontsize=26, color=t.MUTED)
    fig.text(x0, rect[1] + rect[3] * 0.67, f"{fx['close']:.2f}円", fontsize=60, fontweight="bold")
    fig.text(x0, rect[1] + rect[3] * 0.53, f"前日比 {fx['change']:+.2f}円", fontsize=30, color=t.ACCENT)
    fig.text(x0, rect[1] + rect[3] * 0.41, fx["direction"], fontsize=40, fontweight="bold", color=t.ACCENT)
    fig.text(x0, rect[1] + rect[3] * 0.22, f"期間高値 {fx['period_high']:.2f}", fontsize=22, color=t.MUTED)
    fig.text(x0, rect[1] + rect[3] * 0.12, f"期間安値 {fx['period_low']:.2f}", fontsize=22, color=t.MUTED)
    t.save(fig, out)


def jgb_yields(data: dict, out: Path, progress: float = 1.0) -> None:
    jgb = data["jgb"]
    fig, rect = t.new_figure("国債金利 (年限別)", f"{t.ja_date(jgb['date'])} 時点")
    rows = jgb["yields"]
    ax = fig.add_axes([rect[0] + 0.02, rect[1] + 0.07, rect[2] - 0.04, rect[3] - 0.12])
    xs = list(range(len(rows)))
    top = max(r["yield_pct"] for r in rows)
    ax.set_ylim(0, top * 1.3)
    ax.bar(xs, [r["yield_pct"] * progress for r in rows], color=t.ACCENT, width=0.55)
    ax.set_xticks(xs, [r["tenor"] for r in rows], fontsize=30)
    ax.tick_params(axis="y", labelsize=18)
    ax.tick_params(axis="x", length=0)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.1f}%")
    ax.grid(axis="y", color=t.GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _clean_axes(ax)
    for x, r in zip(xs, rows):
        y = r["yield_pct"] * progress
        ax.text(x, y + top * 0.12, f"{r['yield_pct'] * progress:.3f}%", ha="center", fontsize=34, fontweight="bold")
        ax.text(x, y + top * 0.03, f"前日比 {r['change_pt']:+.3f}", ha="center", fontsize=22, color=t.MUTED,
                alpha=progress)
    t.save(fig, out)
