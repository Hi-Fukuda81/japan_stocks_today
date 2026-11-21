"""[3. tts] script.json の各セリフを VOICEVOX で wav にし、長さを manifest.json に記録する。"""

from __future__ import annotations

import json
import logging
import wave
from pathlib import Path

from src.config import DayPaths, load_config
from src.tts.voicevox import VoicevoxClient
from src.tts.voices import pick_voice

log = logging.getLogger(__name__)


def to_speech_text(text: str, replacements: dict[str, str]) -> str:
    """字幕の文から読み上げ用の文を作る (誤読しやすい語をかなに置き換える)。"""
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def plain_kana(kana: str) -> str:
    return kana.replace("'", "").replace("/", " ").replace("_", "")


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def synthesize(date: str, client: VoicevoxClient | None = None) -> Path:
    cfg = load_config()
    vcfg = cfg["voicevox"]
    voice = pick_voice(vcfg, date)
    log.info("今日の声: %s (speaker %d)", voice["name"], voice["speaker"])
    paths = DayPaths.for_date(date)
    script = json.loads(paths.script_json.read_text(encoding="utf-8"))
    client = client or VoicevoxClient(vcfg["url"])
    log.info("VOICEVOX Engine %s", client.wait_until_ready())
    added = client.register_words(cfg.get("user_dict") or {})
    if added:
        log.info("ユーザー辞書に %d 語を登録しました", added)

    paths.audio_dir.mkdir(parents=True, exist_ok=True)
    replacements = cfg.get("tts_replacements") or {}
    entries, readings = [], []
    for si, scene in enumerate(script["scenes"], start=1):
        for li, text in enumerate(scene["lines"], start=1):
            wav = paths.audio_dir / f"{si:02d}_{li:02d}.wav"
            speech = to_speech_text(text, replacements)
            wav.write_bytes(client.tts(speech, voice["speaker"], voice["speed"]))
            readings.append(f"{wav.name}  {text}\n            {plain_kana(client.kana(speech, voice['speaker']))}")
            entries.append({"scene_id": scene["id"], "visual": scene["visual"], "index": li, "text": text,
                            "speech": speech, "wav": wav.name, "duration": round(wav_duration(wav), 3)})
    # 誤読の確認用: 各セリフを VOICEVOX がどう読むかの一覧
    (paths.audio_dir / "readings.txt").write_text("\n".join(readings) + "\n", encoding="utf-8")
    manifest = {"speaker": voice["speaker"], "speaker_name": voice["name"], "speed": voice["speed"], "lines": entries}
    paths.audio_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(e["duration"] for e in entries)
    log.info("%d セリフ、合計 %.1f 秒の音声を作成しました", len(entries), total)
    return paths.audio_manifest
