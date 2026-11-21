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


def tender_offers(data: dict, out: Path, progress: float = 1.0) -> None:
    """公開買付届出書の一覧: 誰が、どの会社の株を買い付けるか。"""
    offers = data["filings"]["tender_offers"]
    fig, rect = t.new_figure("公開買付 (TOB) の届出", f"{t.filings_label(data)} / {offers['count']} 件")
    top = rect[1] + rect[3] - 0.01
    for x, label in ((0.06, "対象の会社 (証券コード)"), (0.47, "買い付ける側"), (0.80, "区分")):
        fig.text(x, top, label, fontsize=22, color=t.MUTED, va="center")
    items = offers["items"][:8]
    if not items:
        fig.text(0.5, 0.52, "公開買付の届出はありません", ha="center", fontsize=38, color=t.MUTED)
    step = min(0.085, (rect[3] - 0.07) / max(len(items), 1))
    for i, item in enumerate(items):
        a = t.stagger(progress, i, len(items))
        if a <= 0:
            continue
        y = top - 0.07 - i * step
        code = f" ({item['sec_code']})" if item.get("sec_code") else ""
        fig.text(0.06, y, _short(item.get("target") or "(非上場)", 13) + code, fontsize=30, fontweight="bold",
                 va="center", alpha=a)
        fig.text(0.47, y, _short(item["filer"], 13), fontsize=28, va="center", alpha=a)
        own = item.get("self_tender")
        fig.text(0.80, y, "自社株" if own else "他社から", fontsize=28, fontweight="bold", va="center", alpha=a,
                 color=t.ACCENT if own else t.WARM)
    t.save(fig, out)


DIRECTION_COLORS = {"新規": "WARM", "増加": "WARM", "減少": "ACCENT"}


def _ratio_text(item: dict) -> str:
    if item.get("ratio_pct") is None:
        return "-"
    if item.get("prev_ratio_pct") is None:
        return f"{item['ratio_pct']:.2f}%"
    return f"{item['prev_ratio_pct']:.2f}% → {item['ratio_pct']:.2f}%"


def holdings_table(data: dict, out: Path, progress: float = 1.0) -> None:
    """大量保有報告書・変更報告書: 誰が、どの会社の株を、何%から何%にしたか。"""
    h = data["filings"]["large_holdings"]
    fig, rect = t.new_figure("大量保有報告書・変更報告書", t.filings_label(data))
    top = rect[1] + rect[3] - 0.01
    for x, label in ((0.05, "発行会社 (証券コード)"), (0.36, "提出者"), (0.63, "保有割合"), (0.90, "区分")):
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
        color = getattr(t, DIRECTION_COLORS.get(item.get("direction"), "MUTED"))
        fig.text(0.05, y, f"{_short(item['issuer'], 9)} ({item['sec_code']})", fontsize=27, fontweight="bold",
                 va="center", alpha=a)
        fig.text(0.36, y, _short(item["filer"], 10), fontsize=25, va="center", alpha=a)
        fig.text(0.63, y, _ratio_text(item), fontsize=27, fontweight="bold", va="center", alpha=a)
        fig.text(0.90, y, item.get("direction") or item["kind"][:2], fontsize=27, fontweight="bold", va="center",
                 alpha=a, color=color)
    fig.text(0.05, rect[1] - 0.005, f"上場会社についての報告 {h['listed_count']} 件から、保有割合の動きが大きいものを抜粋  "
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
    fig.text(x0, rect[1] + rect[3] * 0.53, f"{t.change_word(data)} {fx['change']:+.2f}円", fontsize=30, color=t.ACCENT)
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
        ax.text(x, y + top * 0.03, f"{t.change_word(data)} {r['change_pt']:+.3f}", ha="center", fontsize=22, color=t.MUTED,
                alpha=progress)
    t.save(fig, out)
