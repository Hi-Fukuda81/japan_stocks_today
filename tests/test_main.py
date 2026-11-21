from src import main as main_mod


def test_runs_selected_step(monkeypatch):
    called = []
    monkeypatch.setattr(main_mod, "run_step", lambda step, date, kind="daily": called.append((step, date)))
    assert main_mod.main(["--step", "tts", "--date", "2026-11-14"]) == 0
    assert called == [("tts", "2026-11-14")]


def test_all_steps_in_order_and_stops_on_error(monkeypatch):
    called = []

    def fake(step, date, kind="daily"):
        called.append(step)
        if step == "script":
            raise RuntimeError("boom")

    monkeypatch.setattr(main_mod, "run_step", fake)
    assert main_mod.main(["--date", "2026-11-14"]) == 1
    assert called == ["fetch", "script"]


def test_rejects_invalid_date():
    import pytest
    with pytest.raises(SystemExit):
        main_mod.main(["--date", "../etc"])
