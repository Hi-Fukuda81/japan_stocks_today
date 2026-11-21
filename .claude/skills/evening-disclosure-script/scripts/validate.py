#!/usr/bin/env python3
"""台本 (script.json) の検証。標準ライブラリのみで動く。

使い方: python validate.py output/<日付>
終了コード: 0=OK, 1=NG (標準出力に修正箇所を出す), 2=入力ファイルの問題
"""

from __future__ import annotations

import json
import re
import sys
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
NG_WORDS_MD = SKILL_DIR / "references" / "ng_words.md"

SCENES = [
    ("01_opening", "title"),
    ("02_overview", "filings_bar"),
    ("03_holdings", "holdings_table"),
    ("04_events", "events_list"),
    ("05_usdjpy", "usdjpy_line"),
    ("06_jgb", "jgb_yields"),
    ("07_ending", "ending"),
]
TITLE_PREFIX = "きょうの日本株【夕】"
WEEKLY_TITLE_PREFIX = "きょうの日本株【週間まとめ】"
MAX_LINE_CHARS = 45
MIN_TOTAL_CHARS = 600
TARGET_TOTAL_CHARS = (1000, 2200)
MAX_TITLE_CHARS = 100

# 単位付きの数値。「159円88銭」「0.046ポイント」「2.87%」「1,204件」などを1トークンとして読む
NUMBER_TOKEN = re.compile(
    r"(?P<int>[0-9][0-9,]*)"
    r"(?:円(?P<sen>[0-9]{1,2})銭"
    r"|(?P<frac>\.[0-9]+)?(?:万(?P<man>[0-9]{1,4})?)?\s*(?P<unit>%|％|パーセント|ポイント|円|銭|件))"
)
UP_WORDS = ("上昇", "上がり", "上げ", "円安", "ドル高")
DOWN_WORDS = ("低下", "下落", "下がり", "下げ", "円高", "ドル安")
LEVEL_MARKERS = ("に", "まで", "へ")  # 「2.84%に上昇」のように、数値が前日比ではなく水準であることを示す語
# data.json と照合できない書き方の数値 (照合できる単位は NUMBER_TOKEN のものだけ)
UNCHECKED_NUMBER = re.compile(r"[0-9][0-9,.]*\s*(?:億|兆|千|社|銘柄|倍|割|ドル|bp|ｂｐ|ベーシスポイント)")
KANJI_NUMBER = re.compile(r"[〇一二三四五六七八九十百千万]+(?:件|社|円|銭|%|％|パーセント|ポイント)")
SLASH_DATE = re.compile(r"(?<![0-9/])([0-9]{1,2})/([0-9]{1,2})(?![0-9/])")
DIRECTION_WINDOW = 6  # 数値の直後この文字数以内 (読点・句点まで) にある方向の語を見る
MONTH_DAY = re.compile(r"([0-9]{1,2})月([0-9]{1,2})日")
FULLWIDTH_DIGIT = re.compile(r"[０-９]")


def load_ng_words(path: Path = NG_WORDS_MD) -> list[str]:
    words = re.findall(r"^- `([^`]+)`", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    if not words:
        raise ValueError(f"NG ワードが読み込めません: {path}")
    return words


def collect_numbers(obj, path: tuple = ()) -> list[tuple[tuple, float]]:
    """data.json の数値を (パス, 値) の一覧で返す。符号は残す。"""
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [(path, float(obj))]
    if isinstance(obj, dict):
        return [x for k, v in obj.items() for x in collect_numbers(v, (*path, k))]
    if isinstance(obj, list):
        return [x for v in obj for x in collect_numbers(v, path)]
    return []


def _is_pct(path: tuple) -> bool:
    return bool(path) and str(path[-1]).endswith("pct")


UNIT_FILTERS = {
    # 単位ごとに照合してよい data.json のフィールドを絞る
    "%": _is_pct,
    "円": lambda p: p[:1] == ("usdjpy",) and not _is_pct(p) and "history" not in p,
    "ポイント": lambda p: p[:1] == ("jgb",) and p[-1] == "change_pt",
    "件": lambda p: p[:1] == ("filings",),
}
UNIT_ALIASES = {"％": "%", "パーセント": "%", "銭": "円"}


def _is_change(path: tuple) -> bool:
    return bool(path) and str(path[-1]).startswith("change")


def candidates_for(unit: str, numbers: list[tuple[tuple, float]], after: str = "") -> list[float]:
    """単位に合う data.json の値。数値の直後の語で、照合する相手を絞る。

    - 「2.84%に上昇」(水準を示す語が続く): 前日比 (change*) 以外
    - 「0.5%上昇」「83銭の円安」(向きの語が続く): 前日比のうち、向きの合うものだけ
    - どちらでもない: 単位に合う値すべて
    """
    pred = UNIT_FILTERS[UNIT_ALIASES.get(unit, unit)]
    matched = [(path, v) for path, v in numbers if pred(path)]
    if after.startswith(LEVEL_MARKERS):
        return [v for path, v in matched if not _is_change(path)]
    direction = direction_after(after)
    if direction:
        return [v for path, v in matched if _is_change(path) and v * direction > 0]
    return [v for _, v in matched]


def direction_after(text: str) -> int:
    """数値の直後の語から方向を読む。+1=上昇/円安, -1=低下/下落/円高, 0=不明。"""
    window = re.split(r"[、。,]", text, maxsplit=1)[0][:DIRECTION_WINDOW]
    hits = [(window.find(w), 1) for w in UP_WORDS if w in window]
    hits += [(window.find(w), -1) for w in DOWN_WORDS if w in window]
    return min(hits)[1] if hits else 0


def collect_month_days(obj, acc: set[tuple[int, int]] | None = None) -> set[tuple[int, int]]:
    acc = set() if acc is None else acc
    if isinstance(obj, str):
        m = re.fullmatch(r"\d{4}-(\d{2})-(\d{2})", obj)
        if m:
            acc.add((int(m.group(1)), int(m.group(2))))
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_month_days(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            collect_month_days(v, acc)
    return acc


def number_matches(value: Decimal, step: Decimal, candidates: list[float]) -> bool:
    """value が候補のいずれかを step 単位で四捨五入 (100 以上の整数は切り捨ても可) したものと一致するか。"""
    for v in candidates:
        units = Decimal(repr(abs(v))) / step
        if units.quantize(Decimal(1), rounding=ROUND_HALF_UP) * step == value:
            return True
        if step >= 1 and value >= 100 and units.to_integral_value(rounding=ROUND_FLOOR) * step == value:
            return True
    return False


def parse_token(m: re.Match) -> tuple[Decimal, Decimal, str]:
    """(値, 精度, 単位) を返す。"""
    integer = Decimal(m.group("int").replace(",", ""))
    if m.group("sen") is not None:
        return integer + Decimal(m.group("sen")) / 100, Decimal("0.01"), "円"
    unit = m.group("unit")
    frac = m.group("frac") or ""
    value = Decimal(m.group("int").replace(",", "") + frac)
    step = Decimal(1).scaleb(-(len(frac) - 1)) if frac else Decimal(1)
    if m.group("man") is not None or "万" in m.group(0):
        value = value * 10000 + Decimal(m.group("man") or 0)
        step = Decimal(1) if m.group("man") else step * 10000
    if unit == "銭":
        value, step = value / 100, step / 100
    return value, step, unit


def check_numbers(line: str, numbers: list[tuple[tuple, float]]) -> list[str]:
    issues = []
    for m in NUMBER_TOKEN.finditer(line):
        value, step, unit = parse_token(m)
        candidates = candidates_for(unit, numbers, line[m.end():])
        if not number_matches(value, step, candidates):
            issues.append(f"数値 '{m.group(0)}' が data.json にありません (前日比は上昇/低下の向きも照合しています)")
    for m in UNCHECKED_NUMBER.finditer(line):
        issues.append(f"数値 '{m.group(0)}' は data.json と照合できない単位です。件・%・ポイント・円・銭で書くか、削ってください")
    for m in KANJI_NUMBER.finditer(line):
        issues.append(f"数値 '{m.group(0)}' は漢数字です。半角数字で書いてください")
    return issues


def check_dates(line: str, month_days: set[tuple[int, int]]) -> list[str]:
    return [
        f"日付 '{m.group(0)}' が data.json にありません"
        for pattern in (MONTH_DAY, SLASH_DATE)
        for m in pattern.finditer(line)
        if (int(m.group(1)), int(m.group(2))) not in month_days
    ]


def _month_day(iso) -> str:
    m = re.fullmatch(r"\d{4}-(\d{2})-(\d{2})", str(iso or ""))
    return f"{int(m.group(1))}/{int(m.group(2))}" if m else ""


def title_prefix(data: dict) -> str:
    """夕方便は「きょうの日本株【夕】11/20」、週間まとめは「きょうの日本株【週間まとめ】11/16〜11/20」。"""
    if data.get("edition") == "weekly":
        period = data.get("period") or {}
        return f"{WEEKLY_TITLE_PREFIX}{_month_day(period.get('start'))}〜{_month_day(period.get('end'))}"
    return f"{TITLE_PREFIX}{_month_day(data.get('date'))}"


def check_structure(script: dict, data: dict) -> list[str]:
    issues = []
    if script.get("date") != data.get("date"):
        issues.append(f"date が data.json と一致しません ({script.get('date')} != {data.get('date')})")
    title = script.get("title")
    if not isinstance(title, str) or not title.strip():
        issues.append("title がありません")
    elif len(title) > MAX_TITLE_CHARS:
        issues.append(f"title が {MAX_TITLE_CHARS} 字を超えています ({len(title)} 字)")
    elif not re.match(re.escape(title_prefix(data)) + r"(?![0-9])", title):
        issues.append(f"title は '{title_prefix(data)}' で始めてください")
    if not isinstance(script.get("description_summary"), str) or not script["description_summary"].strip():
        issues.append("description_summary がありません")
    scenes = script.get("scenes")
    if not isinstance(scenes, list):
        return [*issues, "scenes が配列ではありません"]
    actual = [(s.get("id"), s.get("visual")) for s in scenes if isinstance(s, dict)]
    if actual != SCENES:
        issues.append(f"シーン構成が固定の構成と違います。期待: {SCENES} / 実際: {actual}")
    for s in scenes:
        lines = s.get("lines") if isinstance(s, dict) else None
        if not isinstance(lines, list) or not lines or not all(isinstance(x, str) and x.strip() for x in lines):
            issues.append(f"[{s.get('id') if isinstance(s, dict) else s}] lines は空でない文字列の配列にしてください")
    return issues


def iter_texts(script: dict):
    for key in ("title", "description_summary"):
        if isinstance(script.get(key), str):
            yield key, script[key]
    for s in script.get("scenes") or []:
        if not isinstance(s, dict):
            continue
        for i, line in enumerate(s.get("lines") or [], start=1):
            if isinstance(line, str):
                yield f"{s.get('id')} #{i}", line


def validate(script: dict, data: dict, ng_words: list[str]) -> tuple[list[str], list[str]]:
    """(NG 一覧, 警告一覧) を返す。"""
    issues = check_structure(script, data)
    warnings: list[str] = []
    if any(i.startswith(("scenes が配列", "シーン構成")) or "lines は" in i for i in issues):
        return issues, warnings
    numbers = collect_numbers(data)
    month_days = collect_month_days(data)
    for where, text in iter_texts(script):
        if FULLWIDTH_DIGIT.search(text):
            issues.append(f"[{where}] 全角数字は使わないでください: {text}")
        for w in ng_words:
            if w in text:
                issues.append(f"[{where}] NG ワード '{w}': {text}")
        issues += [f"[{where}] {p}: {text}" for p in check_numbers(text, numbers)]
        issues += [f"[{where}] {p}: {text}" for p in check_dates(text, month_days)]
        if where[:2].isdigit() and len(text) > MAX_LINE_CHARS:
            issues.append(f"[{where}] 1セリフ {MAX_LINE_CHARS} 字以内にしてください ({len(text)} 字): {text}")
    total = sum(len(line) for s in script["scenes"] for line in s["lines"])
    if total < MIN_TOTAL_CHARS:
        issues.append(f"台本が短すぎます (合計 {total} 字。{MIN_TOTAL_CHARS} 字以上必要)")
    elif not TARGET_TOTAL_CHARS[0] <= total <= TARGET_TOTAL_CHARS[1]:
        warnings.append(f"合計 {total} 字。目安は {TARGET_TOTAL_CHARS[0]}〜{TARGET_TOTAL_CHARS[1]} 字 (3〜5分)")
    return issues, warnings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("使い方: python validate.py output/<日付>")
        return 2
    day_dir = Path(argv[1])
    try:
        data = json.loads((day_dir / "data.json").read_text(encoding="utf-8"))
        script = json.loads((day_dir / "script.json").read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        print(f"ファイルがありません: {e.filename}")
        return 2
    except json.JSONDecodeError as e:
        print(f"NG: script.json または data.json が JSON として読めません: {e}")
        return 1
    issues, warnings = validate(script, data, load_ng_words())
    for w in warnings:
        print(f"WARN: {w}")
    if issues:
        for i in issues:
            print(f"NG: {i}")
        print(f"\n{len(issues)} 件の NG があります。指摘箇所だけを直してください。")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
