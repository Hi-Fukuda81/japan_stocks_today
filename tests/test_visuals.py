"""サンプルの data.json / script.json から全シーンの画像が作れるかのスモークテスト。"""

from PIL import Image

from src.config import DayPaths, load_config
from src.visuals import render as render_mod
from src.visuals import slides, thumbnail


def test_render_all_scenes(monkeypatch, day_dir):
    monkeypatch.setattr(render_mod.DayPaths, "for_date", classmethod(lambda cls, d: DayPaths(day_dir)))
    cfg = load_config()
    fast = {**cfg, "video": {**cfg["video"], "animation_seconds": 0.5, "animation_fps": 6}}  # 3 コマ
    monkeypatch.setattr(render_mod, "load_config", lambda: fast)
    outputs = render_mod.render("2026-11-13")
    assert len(outputs) == 7
    assert all(Image.open(p).size == (1920, 1080) for p in outputs)
    assert Image.open(day_dir / "thumbnail.png").size == (1280, 720)
    for scene in ("02_overview", "03_holdings", "05_usdjpy", "06_jgb"):
        assert len(list((day_dir / "img" / f"{scene}_anim").glob("*.png"))) == 2
    assert not (day_dir / "img" / "04_events_anim").exists()


def test_render_with_no_listed_items(monkeypatch, day_dir, example_data, tmp_path):
    """上場会社の該当がない日でも描ける。"""
    f = example_data["filings"]
    empty = {**example_data, "filings": {
        **f, "large_holdings": {**f["large_holdings"], "items": []},
        "extraordinary": {**f["extraordinary"], "items": []}, "tender_offers": {"count": 0, "items": []}}}
    from src.visuals import charts
    charts.holdings_table(empty, tmp_path / "h.png")
    slides.events_list(empty, tmp_path / "e.png")
    assert (tmp_path / "h.png").exists() and (tmp_path / "e.png").exists()
    assert slides.event_rows(empty) == []


def test_event_rows_put_tender_offers_first(example_data):
    rows = slides.event_rows(example_data)
    assert rows[0] == ("公開買付", "テスト精密工業 (9903)", "買付者: 例示ホールディングス")
    assert rows[1][0] == "臨時報告書" and rows[1][2] == "代表取締役の異動"


def test_thumbnail_headline(example_data):
    assert thumbnail.headline(example_data) == ("公開買付 1件", "大量保有 35件")
    f = example_data["filings"]
    no_tob = {**example_data, "filings": {**f, "tender_offers": {"count": 0, "items": []}}}
    assert thumbnail.headline(no_tob) == ("大量保有 35件", "提出書類 424件")


def test_weekly_labels(example_data):
    from src.visuals import theme
    weekly = {**example_data, "edition": "weekly",
              "period": {"kind": "weekly", "start": "2026-11-09", "end": "2026-11-13", "days": []}}
    assert theme.filings_label(weekly) == "11月9日〜11月13日 提出分" and theme.change_word(weekly) == "前週末比"
    assert theme.filings_label(example_data) == "11月13日 提出分" and theme.change_word(example_data) == "前日比"
    assert thumbnail.tag_for(weekly) == "週間まとめ 11/9〜11/13"
    assert thumbnail.tag_for(example_data) == "きょうの日本株【夕】11/13"


def test_ending_credit_prefers_manifest(tmp_path):
    from src.visuals.render import speaker_name

    paths = DayPaths(tmp_path)
    cfg = {"voicevox": {"speed": 1.0, "voices": {"wed": {"speaker": 30, "name": "No.7"}}}}
    assert speaker_name(paths, cfg, "2026-11-18") == "No.7"
    paths.audio_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.audio_manifest.write_text('{"speaker_name": "青山龍星", "lines": []}', encoding="utf-8")
    assert speaker_name(paths, cfg, "2026-11-18") == "青山龍星"
