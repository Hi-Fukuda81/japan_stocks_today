"""[6. upload] YouTube Data API v3 で動画を非公開で投稿する。

初回だけ対話的な認証が必要:  uv run python -m src.upload.youtube --auth
以後はリフレッシュトークンで無人実行できる (launchd から呼ばれる想定)。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.config import REPO_ROOT, DayPaths, load_config

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class UploadError(RuntimeError):
    pass


def _paths(cfg: dict) -> tuple[Path, Path]:
    ucfg = cfg["upload"]
    return REPO_ROOT / ucfg["client_secret"], REPO_ROOT / ucfg["token"]


def _save_token(creds, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    os.chmod(token_path, 0o600)


def get_credentials(cfg: dict, interactive: bool = False):
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    client_secret, token_path = _paths(cfg)
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES) if token_path.exists() else None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds, token_path)
            return creds
        except RefreshError as e:
            if not interactive:
                raise UploadError("YouTube のトークンを更新できません。`uv run python -m src.upload.youtube --auth` で"
                                  "再認証してください") from e
    if not interactive:
        raise UploadError("YouTube の認証がまだです。`uv run python -m src.upload.youtube --auth` を実行してください")
    if not client_secret.exists():
        raise UploadError(f"OAuth クライアントのファイルがありません: {client_secret}")
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES).run_local_server(port=0)
    _save_token(creds, token_path)
    return creds


def publish_at(date: str, hhmm: str | None, now: datetime | None = None) -> str | None:
    """予約公開の時刻 (UTC の ISO 8601)。指定がない、または既に過ぎている場合は None。"""
    if not hhmm:
        return None
    from zoneinfo import ZoneInfo

    hour, minute = (int(x) for x in hhmm.split(":"))
    target = datetime.fromisoformat(date).replace(hour=hour, minute=minute, tzinfo=ZoneInfo("Asia/Tokyo"))
    now = now or datetime.now(timezone.utc)
    if target <= now:
        return None
    return target.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_metadata(script: dict, description: str, cfg: dict, date: str | None = None,
                   now: datetime | None = None) -> dict:
    ucfg, ch = cfg["upload"], cfg["channel"]
    status = {
        "privacyStatus": ucfg["privacy"],
        "selfDeclaredMadeForKids": False,
        "containsSyntheticMedia": False,
    }
    scheduled = publish_at(date, ucfg.get("publish_at"), now) if date else None
    if scheduled:  # 予約公開は privacyStatus=private のときだけ指定できる
        status = {**status, "privacyStatus": "private", "publishAt": scheduled}
    return {
        "snippet": {
            "title": script["title"][:100],
            "description": description[:5000],
            "tags": list(ch.get("default_tags") or []),
            "categoryId": ucfg["category_id"],
            "defaultLanguage": "ja",
            "defaultAudioLanguage": "ja",
        },
        "status": status,
    }


def _upload_video(youtube, video: Path, body: dict) -> str:
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            log.info("アップロード中 %d%%", int(status.progress() * 100))
    return response["id"]


def _set_thumbnail(youtube, video_id: str, thumbnail: Path) -> bool:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    try:
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail))).execute()
        return True
    except HttpError as e:  # 電話番号の確認が済んでいないチャンネルではカスタムサムネイルが使えない
        log.warning("サムネイルを設定できませんでした (動画の投稿は完了): %s", e.reason if hasattr(e, "reason") else e)
        return False


def _voice_name(paths: DayPaths) -> str | None:
    """日替わりの声の比較用に、その日の声を投稿記録に残す。"""
    if not paths.audio_manifest.exists():
        return None
    return json.loads(paths.audio_manifest.read_text(encoding="utf-8")).get("speaker_name")


def upload(date: str, youtube=None) -> dict:
    cfg = load_config()
    paths = DayPaths.for_date(date)
    record_path = paths.root / "upload.json"
    if record_path.exists():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        log.info("投稿済みのためスキップします: %s", record.get("url"))
        return record
    for required in (paths.video, paths.script_json, paths.description_txt):
        if not required.exists():
            raise UploadError(f"投稿に必要なファイルがありません: {required}")

    script = json.loads(paths.script_json.read_text(encoding="utf-8"))
    body = build_metadata(script, paths.description_txt.read_text(encoding="utf-8"), cfg, date)
    if youtube is None:
        from googleapiclient.discovery import build

        youtube = build("youtube", "v3", credentials=get_credentials(cfg), cache_discovery=False)
    try:
        video_id = _upload_video(youtube, paths.video, body)
    except Exception as e:
        raise UploadError(f"YouTube への投稿に失敗しました: {e}") from e
    thumbnail_set = paths.thumbnail.exists() and _set_thumbnail(youtube, video_id, paths.thumbnail)
    record = {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "privacy": body["status"]["privacyStatus"],
        "publish_at": body["status"].get("publishAt"),
        "thumbnail_set": bool(thumbnail_set),
        "voice": _voice_name(paths),
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("投稿しました (%s): %s", record["privacy"], record["url"])
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="YouTube 投稿")
    parser.add_argument("--auth", action="store_true", help="ブラウザで認証してトークンを保存する")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.auth:
        get_credentials(load_config(), interactive=True)
        log.info("認証が完了しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
