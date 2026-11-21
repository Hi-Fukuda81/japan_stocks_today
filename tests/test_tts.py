import io
import json
import wave
from types import SimpleNamespace

import pytest
import requests

from src.config import DayPaths
from src.tts import synthesize as synth_mod
from src.tts.voicevox import VoicevoxClient, VoicevoxError


def _wav_bytes(seconds=0.5, rate=24000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


class FakeResponse:
    def __init__(self, payload=None, content=b""):
        self.payload, self.content = payload, content

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_client_tts_and_dict(monkeypatch):
    calls = []

    def fake_request(method, url, timeout, **kwargs):
        calls.append((method, url.rsplit("/", 1)[-1], kwargs))
        if url.endswith("/audio_query"):
            return FakeResponse({"speedScale": 1.0})
        if url.endswith("/synthesis"):
            assert kwargs["json"]["speedScale"] == 1.2
            return FakeResponse(content=b"WAV")
        if url.endswith("/user_dict"):
            return FakeResponse({"u1": {"surface": "ＥＴＦ"}})
        return FakeResponse({})

    monkeypatch.setattr(requests, "request", fake_request)
    client = VoicevoxClient("http://x")
    assert client.tts("こんにちは", 3, 1.2) == b"WAV"
    assert client.register_words({"ETF": "イーティーエフ", "CPI": "シーピーアイ"}) == 1
    assert [c[1] for c in calls if c[0] == "POST"][-1] == "user_dict_word"


def test_wait_until_ready_times_out(monkeypatch):
    def fail(*a, **k):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(requests, "request", fail)
    with pytest.raises(VoicevoxError, match="応答しません"):
        VoicevoxClient("http://x").wait_until_ready(max_wait_sec=0, interval=0)


class FakeClient:
    def wait_until_ready(self):
        return "0.0.0"

    def register_words(self, words):
        return len(words)

    def tts(self, text, speaker, speed):
        self.spoken = [*getattr(self, "spoken", []), text]
        return _wav_bytes()

    def kana(self, text, speaker):
        return "テ'スト/デス"


def test_synthesize_writes_manifest(monkeypatch, day_dir, example_script):
    monkeypatch.setattr(synth_mod.DayPaths, "for_date", classmethod(lambda cls, d: DayPaths(day_dir)))
    manifest_path = synth_mod.synthesize("2026-11-13", client=FakeClient())
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    n_lines = sum(len(s["lines"]) for s in example_script["scenes"])
    assert len(manifest["lines"]) == n_lines
    assert manifest["lines"][0]["duration"] == pytest.approx(0.5)
    assert (day_dir / "audio" / manifest["lines"][-1]["wav"]).exists()


def test_to_speech_text_replaces_ambiguous_words():
    assert synth_mod.to_speech_text("投資判断はご自身で行ってください。", {"行って": "おこなって"}) == \
        "投資判断はご自身でおこなってください。"


def test_synthesize_writes_readings(monkeypatch, day_dir):
    monkeypatch.setattr(synth_mod.DayPaths, "for_date", classmethod(lambda cls, d: DayPaths(day_dir)))
    synth_mod.synthesize("2026-11-13", client=FakeClient())
    assert "テスト デス" in (day_dir / "audio" / "readings.txt").read_text(encoding="utf-8")


def test_synthesize_uses_weekday_voice(monkeypatch, day_dir):
    monkeypatch.setattr(synth_mod.DayPaths, "for_date", classmethod(lambda cls, d: DayPaths(day_dir)))
    client = FakeClient()
    used = []
    client.tts = lambda text, speaker, speed: used.append((speaker, speed)) or _wav_bytes()
    manifest_path = synth_mod.synthesize("2026-11-18", client=client)  # 水曜
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    vcfg = synth_mod.load_config()["voicevox"]
    expected = vcfg["voices"]["wed"]
    assert manifest["speaker"] == expected["speaker"]
    assert manifest["speaker_name"] == expected["name"]
    assert {s for s, _ in used} == {expected["speaker"]}
