import json
import os
import time
from datetime import datetime, timezone

import pytest

from src import daily
from src.upload import youtube as yt


def _day(root, date, video=True, uploaded=False):
    d = root / date
    d.mkdir(parents=True)
    if video:
        (d / "video.mp4").write_bytes(b"x")
    if uploaded:
        (d / "upload.json").write_text(json.dumps({"url": "u"}), encoding="utf-8")
    return d


def test_already_uploaded(tmp_path):
    _day(tmp_path, "2026-11-13", uploaded=True)
    assert daily.already_uploaded("2026-11-13", tmp_path) == {"url": "u"}
    assert daily.already_uploaded("2026-11-16", tmp_path) is None


def test_single_instance_blocks_second(tmp_path):
    lock = tmp_path / ".lock"
    with daily.single_instance(lock):
        with pytest.raises(daily.AlreadyRunning):
            with daily.single_instance(lock):
                pass


def test_cleanup_removes_old_intermediates_and_logs(tmp_path):
    d = _day(tmp_path / "out", "2026-11-02")
    (d / "audio").mkdir()
    old = time.time() - 10 * 86400
    os.utime(d / "audio", (old, old))
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "2026-10-01.log").write_text("x")
    os.utime(logs / "2026-10-01.log", (time.time() - 40 * 86400,) * 2)
    daily.cleanup(tmp_path / "out", logs, keep_intermediate_days=7, keep_log_days=30)
    assert not (d / "audio").exists() and (d / "video.mp4").exists()
    assert not (logs / "2026-10-01.log").exists()


@pytest.fixture
def steps(monkeypatch):
    called = []
    monkeypatch.setattr(daily, "run_step", lambda step, date: called.append(step))
    monkeypatch.setattr(daily, "notify", lambda *a, **k: called.append("notify"))
    monkeypatch.setattr(daily, "already_uploaded", lambda date: None)
    return called


@pytest.mark.parametrize("date", ["2026-11-21", "2026-11-23", "2026-12-31", "2027-01-02"])  # 土曜・祝日・年末年始
def test_run_skips_when_market_closed(steps, date):
    assert daily.run(date) == 0
    assert steps == []


def test_run_all_steps_on_trading_day(steps):
    assert daily.run("2026-11-20") == 0
    assert steps == [*daily.STEPS, "notify"]


def test_run_skips_when_already_uploaded(steps, monkeypatch):
    monkeypatch.setattr(daily, "already_uploaded", lambda date: {"url": "u"})
    assert daily.run("2026-11-20") == 0
    assert steps == []


@pytest.mark.parametrize("now,expected", [
    (datetime(2026, 11, 13, 7, 0, tzinfo=timezone.utc), "2026-11-13T07:45:00Z"),   # 16:00 JST → 16:45 JST
    (datetime(2026, 11, 13, 8, 0, tzinfo=timezone.utc), None),                     # 17:00 JST は過ぎている
])
def test_publish_at(now, expected):
    assert yt.publish_at("2026-11-13", "16:45", now) == expected
    assert yt.publish_at("2026-11-13", None, now) is None


def test_build_metadata_stays_private_without_schedule(example_script):
    from src.config import load_config
    body = yt.build_metadata(example_script, "d", load_config(), "2026-11-13",
                             now=datetime(2026, 11, 13, 7, 0, tzinfo=timezone.utc))
    assert body["status"]["privacyStatus"] == "private" and "publishAt" not in body["status"]
