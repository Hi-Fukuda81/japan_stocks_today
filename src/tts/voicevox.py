"""VOICEVOX Engine の HTTP API ラッパー。"""

from __future__ import annotations

import logging
import time
import unicodedata

import requests

log = logging.getLogger(__name__)


class VoicevoxError(RuntimeError):
    pass


class VoicevoxClient:
    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        try:
            res = requests.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
            res.raise_for_status()
            return res
        except requests.RequestException as e:
            raise VoicevoxError(f"VOICEVOX {method} {path} に失敗しました: {e}") from e

    def version(self) -> str:
        return self._request("GET", "/version").json()

    def wait_until_ready(self, max_wait_sec: float = 60.0, interval: float = 2.0) -> str:
        deadline = time.monotonic() + max_wait_sec
        while True:
            try:
                return self.version()
            except VoicevoxError:
                if time.monotonic() >= deadline:
                    raise VoicevoxError(f"VOICEVOX Engine が {max_wait_sec:.0f} 秒以内に応答しません ({self.base_url})")
                time.sleep(interval)

    def kana(self, text: str, speaker: int) -> str:
        """VOICEVOX が実際に読む音 (AquesTalk 風記法)。誤読の確認用。"""
        return self._request("POST", "/audio_query", params={"text": text, "speaker": speaker}).json()["kana"]

    def tts(self, text: str, speaker: int, speed: float) -> bytes:
        query = self._request("POST", "/audio_query", params={"text": text, "speaker": speaker}).json()
        query = {**query, "speedScale": speed}
        return self._request("POST", "/synthesis", params={"speaker": speaker}, json=query).content

    def register_words(self, words: dict[str, str]) -> int:
        """未登録の語だけユーザー辞書に登録し、登録した数を返す。"""
        existing = {
            unicodedata.normalize("NFKC", w["surface"]) for w in self._request("GET", "/user_dict").json().values()
        }
        added = 0
        for surface, pronunciation in words.items():
            if unicodedata.normalize("NFKC", surface) in existing:
                continue
            self._request("POST", "/user_dict_word", params={
                "surface": surface, "pronunciation": pronunciation, "accent_type": 0, "word_type": "PROPER_NOUN",
            })
            added += 1
        return added
