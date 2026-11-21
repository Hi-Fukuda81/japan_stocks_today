import pytest

from src.tts.voices import VoiceConfigError, pick_voice

VCFG = {
    "speed": 1.15,
    "default_voice": {"speaker": 3, "name": "ずんだもん"},
    "voices": {
        "tue": {"speaker": 3, "name": "ずんだもん"},
        "wed": {"speaker": 30, "name": "No.7", "speed": 1.05},
        "sun": {"speaker": 2, "name": "四国めたん"},
    },
}


def test_pick_voice_by_weekday():
    assert pick_voice(VCFG, "2026-11-17")["name"] == "ずんだもん"  # 火
    assert pick_voice(VCFG, "2026-11-18")["name"] == "No.7"       # 水
    assert pick_voice(VCFG, "2026-11-22")["name"] == "四国めたん"   # 日
    assert pick_voice(VCFG, "2026-11-25") == pick_voice(VCFG, "2026-11-18")  # 翌週の水曜も同じ


def test_pick_voice_speed_override_and_default():
    assert pick_voice(VCFG, "2026-11-18")["speed"] == 1.05
    assert pick_voice(VCFG, "2026-11-17")["speed"] == 1.15


def test_pick_voice_falls_back_to_default_voice():
    assert pick_voice(VCFG, "2026-11-16") == {"speaker": 3, "name": "ずんだもん", "speed": 1.15}  # 月


def test_pick_voice_errors_without_any_voice():
    with pytest.raises(VoiceConfigError, match="mon"):
        pick_voice({"speed": 1.0, "voices": {}}, "2026-11-16")
