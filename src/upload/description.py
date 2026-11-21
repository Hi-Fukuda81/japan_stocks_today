"""YouTube 概要欄のテキストを作る (要約・タイムスタンプ・出典・免責・VOICEVOX クレジット)。"""

from __future__ import annotations

SCENE_LABELS = {
    "01_opening": "オープニング",
    "02_overview": "提出書類の内訳",
    "03_holdings": "大量保有報告書",
    "04_events": "公開買付・臨時報告書",
    "05_usdjpy": "ドル円",
    "06_jgb": "国債金利",
    "07_ending": "まとめ",
}


def timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_description(script: dict, timeline: dict, cfg: dict, speaker_name: str) -> str:
    chapters = [f"{timestamp(s['start'])} {SCENE_LABELS.get(s['scene_id'], s['scene_id'])}"
                for s in timeline["scenes"]]
    channel = cfg["channel"]
    sections = [
        script["description_summary"],
        "■ 目次\n" + "\n".join(chapters),
        "■ データ出典\n" + "\n".join(f"・{c}" for c in channel["data_credits"]),
        "■ 免責事項\n" + channel["disclaimer"],
        f"■ クレジット\nVOICEVOX:{speaker_name}",
    ]
    return "\n\n".join(sections) + "\n"
