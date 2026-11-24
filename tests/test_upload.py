import json
from types import SimpleNamespace

import pytest

from src.config import DayPaths, load_config
from src.upload import youtube as yt


class FakeRequest:
    def __init__(self, result):
        self.result = result

    def next_chunk(self):
        return SimpleNamespace(progress=lambda: 1.0), self.result

    def execute(self):
        return self.result


class FakeYouTube:
    def __init__(self):
        self.inserted = None
        self.thumbnail_for = None

    def videos(self):
        outer = self

        class V:
            def insert(self, part, body, media_body):
                outer.inserted = body
                return FakeRequest({"id": "abc123"})
        return V()

    def thumbnails(self):
        outer = self

        class T:
            def set(self, videoId, media_body):
                outer.thumbnail_for = videoId
                return FakeRequest({})
        return T()


@pytest.fixture
def ready_day(monkeypatch, day_dir):
    (day_dir / "video.mp4").write_bytes(b"\x00" * 10)
    (day_dir / "description.txt").write_text("説明", encoding="utf-8")
    (day_dir / "thumbnail.png").write_bytes(b"\x89PNG")
    monkeypatch.setattr(yt.DayPaths, "for_date", classmethod(lambda cls, d: DayPaths(day_dir)))
    return day_dir


def test_build_metadata_without_date_uses_fallback_privacy(example_script):
    body = yt.build_metadata(example_script, "説明", load_config())
    assert body["status"] == {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                              "containsSyntheticMedia": False}
    assert body["snippet"]["title"] == example_script["title"]
    assert "日本株" in body["snippet"]["tags"]


def test_upload_writes_record_and_is_idempotent(ready_day):
    fake = FakeYouTube()
    record = yt.upload("2026-11-13", youtube=fake)
    assert record["video_id"] == "abc123" and record["thumbnail_set"] is True
    assert fake.thumbnail_for == "abc123"
    assert json.loads((ready_day / "upload.json").read_text(encoding="utf-8"))["url"] == "https://youtu.be/abc123"
    second = FakeYouTube()
    yt.upload("2026-11-13", youtube=second)
    assert second.inserted is None  # 2回目は投稿しない


def test_upload_requires_video(ready_day):
    (ready_day / "video.mp4").unlink()
    with pytest.raises(yt.UploadError, match="video.mp4"):
        yt.upload("2026-11-13", youtube=FakeYouTube())


def test_non_interactive_without_token_raises(monkeypatch, tmp_path):
    cfg = {**load_config(), "upload": {**load_config()["upload"], "token": str(tmp_path / "none.json")}}
    with pytest.raises(yt.UploadError, match="--auth"):
        yt.get_credentials(cfg, interactive=False)


def test_upload_record_includes_voice(ready_day):
    audio = ready_day / "audio"
    audio.mkdir(exist_ok=True)
    (audio / "manifest.json").write_text('{"speaker_name": "No.7", "lines": []}', encoding="utf-8")
    assert yt.upload("2026-11-18", youtube=FakeYouTube())["voice"] == "No.7"
