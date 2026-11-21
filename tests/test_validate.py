import json

import pytest


def with_line(script, scene_id, line):
    scenes = [
        {**s, "lines": [*s["lines"], line]} if s["id"] == scene_id else s
        for s in script["scenes"]
    ]
    return {**script, "scenes": scenes}


def run(validate_mod, script, data):
    return validate_mod.validate(script, data, validate_mod.load_ng_words())


def test_example_script_passes(validate_mod, example_script, example_data):
    issues, _ = run(validate_mod, example_script, example_data)
    assert issues == []


def test_ng_word_detected(validate_mod, example_script, example_data):
    script = with_line(example_script, "03_holdings", "今が買い時かもしれません。")
    issues, _ = run(validate_mod, script, example_data)
    assert any("買い時" in i for i in issues)


def test_ng_words_loaded_from_markdown(validate_mod):
    words = validate_mod.load_ng_words()
    assert "おすすめ" in words and "上がりそう" in words


@pytest.mark.parametrize("line", [
    "提出書類は500件でした。",                  # filings にない件数
    "ドル円は160円12銭でした。",
    "前日から3円の円安です。",
    "10年は2.9%でした。",                       # 2.841 は 2.8
    "前の日から0.016ポイント上昇しました。",    # 30年は -0.016 (向きが違う)
    "前の日から83銭の円高です。",               # 実際は円安
    "保有割合が20%を超えました。",              # 制度の基準値 (reference) にない
    "ドル円は5%の円安でした。",                 # 前日比は 0.52% (制度の基準値 5% と混同しない)
    "保有割合が3%上昇しました。",
    "10年は2%上昇しました。",                   # 利回りの水準を前日比として言っている
    "10年は0.001ポイント下がりました。",        # 実際は上昇
])
def test_unknown_number_detected(validate_mod, example_script, example_data, line):
    issues, _ = run(validate_mod, with_line(example_script, "02_tender", line), example_data)
    assert any("data.json にありません" in i for i in issues)


@pytest.mark.parametrize("line", [
    "提出書類は424件でした。",
    "大量保有報告書は35件、公開買付届出書は1件です。",
    "ドル円は159.71円でした。",
    "ドル円は159円71銭まで円安が進みました。",  # 水準は向きの照合をしない
    "10年は2.84%に上昇しました。",
    "30年は0.016ポイント低下しました。",
    "5%を超えて保有すると提出が必要です。",
    "ドル円は0.52%の円安でした。",
    "過去30日の安値は156円91銭でした。",
])
def test_known_numbers_accepted(validate_mod, example_script, example_data, line):
    issues, _ = run(validate_mod, with_line(example_script, "02_tender", line), example_data)
    assert issues == []


@pytest.mark.parametrize("line", ["11月20日に発表があります。", "11/20に提出されました。"])
def test_unknown_date_detected(validate_mod, example_script, example_data, line):
    issues, _ = run(validate_mod, with_line(example_script, "05_usdjpy", line), example_data)
    assert any("日付" in i for i in issues)


def test_history_values_are_not_accepted_as_current(validate_mod, example_script, example_data):
    fx = example_data["usdjpy"]
    current = {fx["close"], fx["prev_close"], fx["period_high"], fx["period_low"]}
    past = next(h["close"] for h in fx["history"] if h["close"] not in current)
    yen, sen = divmod(round(past * 100), 100)
    issues, _ = run(validate_mod, with_line(example_script, "05_usdjpy", f"ドル円は{yen}円{sen:02d}銭です。"), example_data)
    assert any("data.json にありません" in i for i in issues)


@pytest.mark.parametrize("line", ["買付総額は300億円です。", "上場会社は12社でした。", "長期金利は4.6ベーシスポイント上昇しました。"])
def test_uncheckable_units_detected(validate_mod, example_script, example_data, line):
    issues, _ = run(validate_mod, with_line(example_script, "04_events", line), example_data)
    assert any("照合できない単位" in i for i in issues)


def test_kanji_numbers_detected(validate_mod, example_script, example_data):
    issues, _ = run(validate_mod, with_line(example_script, "03_holdings", "大量保有報告書は三件でした。"), example_data)
    assert any("漢数字" in i for i in issues)


def test_title_date_is_not_matched_by_prefix_only(validate_mod, example_script, example_data):
    data = {**example_data, "date": "2026-11-01"}
    script = {**example_script, "date": "2026-11-01", "title": "きょうの日本株【夕】11/13 開示まとめ"}
    issues, _ = run(validate_mod, script, data)
    assert any("title は" in i for i in issues)


def test_scene_order_violation(validate_mod, example_script, example_data):
    scenes = example_script["scenes"]
    script = {**example_script, "scenes": [scenes[1], scenes[0], *scenes[2:]]}
    issues, _ = run(validate_mod, script, example_data)
    assert any("シーン構成" in i for i in issues)


def test_long_line_detected(validate_mod, example_script, example_data):
    issues, _ = run(validate_mod, with_line(example_script, "04_events", "あ" * 46 + "。"), example_data)
    assert any("45 字以内" in i for i in issues)


def test_fullwidth_digits_detected(validate_mod, example_script, example_data):
    issues, _ = run(validate_mod, with_line(example_script, "04_events", "１つ目です。"), example_data)
    assert any("全角数字" in i for i in issues)


def test_date_mismatch_and_missing_title(validate_mod, example_script, example_data):
    script = {**example_script, "date": "2026-01-01", "title": ""}
    issues, _ = run(validate_mod, script, example_data)
    assert any("date が" in i for i in issues) and any("title" in i for i in issues)


@pytest.mark.parametrize("title", ["【日本株】11/13 開示まとめ", "きょうの日本株【夕】11/14 開示まとめ"])
def test_title_must_start_with_channel_prefix_and_date(validate_mod, example_script, example_data, title):
    issues, _ = run(validate_mod, {**example_script, "title": title}, example_data)
    assert any("きょうの日本株【夕】11/13" in i for i in issues)


def test_weekly_title_prefix(validate_mod, example_script, example_data):
    data = {**example_data, "edition": "weekly",
            "period": {"kind": "weekly", "start": "2026-11-09", "end": "2026-11-13", "days": []}}
    ok = {**example_script, "title": "きょうの日本株【週間まとめ】11/9〜11/13 大量保有報告書 35件"}
    assert run(validate_mod, ok, data)[0] == []
    issues, _ = run(validate_mod, example_script, data)   # 夕方便の書き出しのまま
    assert any("週間まとめ" in i for i in issues)


def test_too_short_script(validate_mod, example_script, example_data):
    scenes = [{**s, "lines": s["lines"][:1]} for s in example_script["scenes"]]
    issues, _ = run(validate_mod, {**example_script, "scenes": scenes}, example_data)
    assert any("短すぎ" in i for i in issues)


def test_main_exit_codes(validate_mod, day_dir, capsys):
    assert validate_mod.main(["validate.py", str(day_dir)]) == 0
    script = json.loads((day_dir / "script.json").read_text(encoding="utf-8"))
    (day_dir / "script.json").write_text(json.dumps({**script, "title": "おすすめ銘柄"}, ensure_ascii=False),
                                         encoding="utf-8")
    assert validate_mod.main(["validate.py", str(day_dir)]) == 1
    assert "NG" in capsys.readouterr().out
    assert validate_mod.main(["validate.py", str(day_dir / "missing")]) == 2


def test_half_up_rounding(validate_mod, example_script, example_data):
    yields = [{**y, "yield_pct": 2.25} if y["tenor"] == "10年" else y for y in example_data["jgb"]["yields"]]
    data = {**example_data, "jgb": {**example_data["jgb"], "yields": yields}}
    issues, _ = run(validate_mod, with_line(example_script, "06_jgb", "10年は2.3%でした。"), data)
    assert not any("2.3%" in i for i in issues)


def test_non_string_lines_reported_without_crash(validate_mod, example_script, example_data):
    scenes = [{**s, "lines": [123]} if s["id"] == "05_usdjpy" else s for s in example_script["scenes"]]
    issues, _ = run(validate_mod, {**example_script, "scenes": scenes}, example_data)
    assert any("lines は" in i for i in issues)
