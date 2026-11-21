"""読み上げ音声 (VOICEVOX キャラ) を動画の日付の曜日から決める。

同じ日付なら必ず同じ声になるので、tts・visual を個別に再実行しても食い違わない。
"""

from __future__ import annotations

from datetime import date as Date

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class VoiceConfigError(RuntimeError):
    pass


def pick_voice(vcfg: dict, date: str) -> dict:
    """config.yaml の voicevox 節と動画の日付 (JST) から {speaker, name, speed} を返す。

    voices に曜日 (mon〜sun) が無い日は default_voice を使う。
    """
    default_speed = vcfg["speed"]
    weekday = WEEKDAYS[Date.fromisoformat(date[:10]).weekday()]  # date は slot_key (朝便は「日付-am」)
    voice = (vcfg.get("voices") or {}).get(weekday) or vcfg.get("default_voice")
    if voice is None:
        raise VoiceConfigError(f"config.yaml の voicevox に {weekday} の声も default_voice もありません")
    return {"speaker": voice["speaker"], "name": voice["name"], "speed": voice.get("speed", default_speed)}
