"""東証の営業日判定 (土日・祝日・年末年始 12/31〜1/3 は休場)。"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta

import jpholiday

YEAR_END_HOLIDAYS = {(12, 31), (1, 1), (1, 2), (1, 3)}


def is_trading_day(day: str) -> bool:
    d = Date.fromisoformat(day)
    if d.weekday() >= 5 or (d.month, d.day) in YEAR_END_HOLIDAYS:
        return False
    return not jpholiday.is_holiday(d)


def closed_reason(day: str) -> str | None:
    """休場なら理由、営業日なら None。"""
    d = Date.fromisoformat(day)
    if d.weekday() >= 5:
        return "土日"
    if (d.month, d.day) in YEAR_END_HOLIDAYS:
        return "年末年始"
    name = jpholiday.is_holiday_name(d)
    return f"祝日 ({name})" if name else None


def week_trading_days(day: str) -> list[str]:
    """day 以前でいちばん新しい営業日を含む週 (月〜金) の営業日のうち、その営業日までのもの。

    土曜に呼ぶと、その週の月〜金の営業日が返る。
    """
    ref = Date.fromisoformat(day if is_trading_day(day) else previous_trading_day(day))
    monday = ref - timedelta(days=ref.weekday())
    days = [(monday + timedelta(days=i)).isoformat() for i in range(ref.weekday() + 1)]
    return [d for d in days if is_trading_day(d)]


def previous_trading_day(day: str) -> str:
    d = Date.fromisoformat(day) - timedelta(days=1)
    while not is_trading_day(d.isoformat()):
        d -= timedelta(days=1)
    return d.isoformat()
