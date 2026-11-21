"""セリフごとの wav をタイムラインどおりに無音を挟んで1本の wav にする。"""

from __future__ import annotations

import wave
from pathlib import Path


def concat_wavs(timeline: dict, audio_dir: Path, out: Path) -> None:
    params = None
    frames: list[bytes] = []
    cursor = 0  # 書き込んだフレーム数
    for line in timeline["lines"]:
        with wave.open(str(audio_dir / line["wav"]), "rb") as w:
            if params is None:
                params = w.getparams()
            elif (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (
                params.framerate, params.nchannels, params.sampwidth):
                raise RuntimeError(f"wav の形式が揃っていません: {line['wav']}")
            data = w.readframes(w.getnframes())
        bytes_per_frame = params.nchannels * params.sampwidth
        start = round(line["speech_start"] * params.framerate)
        frames.append(b"\x00" * max(0, start - cursor) * bytes_per_frame)
        frames.append(data)
        cursor = max(cursor, start) + len(data) // bytes_per_frame
    end = round(timeline["total"] * params.framerate)
    frames.append(b"\x00" * max(0, end - cursor) * params.nchannels * params.sampwidth)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(params.nchannels)
        w.setsampwidth(params.sampwidth)
        w.setframerate(params.framerate)
        w.writeframes(b"".join(frames))
