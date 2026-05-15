"""
Optional Gemini text-to-speech for AI table talk.

Gemini TTS returns raw 24 kHz PCM audio, which we wrap as WAV for Windows
playback.
"""

from __future__ import annotations

import atexit
import base64
import io
import os
import queue
import re
import sys
import threading
import wave
from dataclasses import dataclass
from typing import Optional

import requests


TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _clean_player_env_name(player_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", player_name or "").strip("_")
    return cleaned.upper()


def _pcm_to_wav_bytes(pcm: bytes, sample_rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()


@dataclass
class GeminiTTSConfig:
    enabled: bool
    api_key: str
    model_id: str = "gemini-2.5-flash-preview-tts"
    voice_name: str = "Kore"
    prompt_template: str = "[casual, conversational] {text}"
    play_audio: bool = True
    verify_ssl: bool = True
    timeout_seconds: float = 30.0
    queue_max_size: int = 20


class GeminiTTS:
    """Small async Gemini TTS client for chat messages."""

    def __init__(self, config: GeminiTTSConfig):
        self.config = config
        self.enabled = config.enabled
        self._queue: "queue.Queue[tuple[str, str] | None]" = queue.Queue(
            maxsize=max(1, config.queue_max_size)
        )
        self._warned_unconfigured = False
        self._warned_playback = False
        self._worker: Optional[threading.Thread] = None

        if self.enabled and self._is_configured():
            if not self.config.verify_ssl:
                requests.packages.urllib3.disable_warnings(
                    requests.packages.urllib3.exceptions.InsecureRequestWarning
                )
            self._worker = threading.Thread(
                target=self._run,
                name="GeminiTTS",
                daemon=True,
            )
            self._worker.start()
            atexit.register(self.close)

    @classmethod
    def from_env(cls) -> "GeminiTTS":
        config = GeminiTTSConfig(
            enabled=_env_bool("GEMINI_TTS_ENABLED", True),
            api_key=(
                os.environ.get("GEMINI_TTS_API_KEY")
                or os.environ.get("GEMINI_API_KEY")
                or ""
            ).strip(),
            model_id=os.environ.get(
                "GEMINI_TTS_MODEL_ID",
                "gemini-2.5-flash-preview-tts",
            ).strip(),
            voice_name=os.environ.get("GEMINI_TTS_VOICE_NAME", "Kore").strip(),
            prompt_template=os.environ.get(
                "GEMINI_TTS_PROMPT_TEMPLATE",
                "[casual, conversational] {text}",
            ),
            play_audio=_env_bool("GEMINI_TTS_PLAY_AUDIO", True),
            verify_ssl=_env_bool("GEMINI_TTS_VERIFY_SSL", True),
            timeout_seconds=_env_float("GEMINI_TTS_TIMEOUT_SECONDS", 30.0),
            queue_max_size=_env_int("GEMINI_TTS_QUEUE_MAX_SIZE", 20),
        )
        return cls(config)

    def _is_configured(self) -> bool:
        return bool(self.config.api_key and self.config.voice_name)

    def describe(self) -> str:
        if not self.enabled:
            return "disabled"
        if not self._is_configured():
            return "enabled but missing GEMINI_API_KEY or GEMINI_TTS_VOICE_NAME"
        return f"enabled ({self.config.model_id}, voice={self.config.voice_name})"

    def speak(self, player_name: str, text: str) -> None:
        """Queue a message for synthesis. Never raises into the game loop."""
        if not self.enabled:
            return

        if not self._is_configured():
            if not self._warned_unconfigured:
                print("[TTS] Gemini is enabled but API key/voice is missing.")
                self._warned_unconfigured = True
            return

        text = (text or "").strip()
        if not text:
            return

        try:
            self._queue.put_nowait((player_name, text))
        except queue.Full:
            print("[TTS] Gemini queue is full; skipping latest chat audio.")

    def close(self) -> None:
        if not self._worker or not self._worker.is_alive():
            return
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                break

            player_name, text = item
            try:
                audio = self._synthesize(player_name, text)
                if self.config.play_audio and audio:
                    self._play_audio(audio)
            except Exception as exc:
                print(f"[TTS] Gemini error: {exc}")
            finally:
                self._queue.task_done()

    def _voice_name_for_player(self, player_name: str) -> str:
        suffix = _clean_player_env_name(player_name)
        return (
            os.environ.get(f"GEMINI_TTS_VOICE_{suffix}")
            or self.config.voice_name
        ).strip()

    def _synthesize(self, player_name: str, text: str) -> bytes:
        voice_name = self._voice_name_for_player(player_name)
        prompt = self.config.prompt_template.format(
            player=player_name,
            text=text.replace('"', "'"),
        )
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model_id}:generateContent",
            headers={
                "x-goog-api-key": self.config.api_key,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": voice_name
                            }
                        }
                    }
                },
            },
            verify=self.config.verify_ssl,
            timeout=self.config.timeout_seconds,
        )
        if response.status_code >= 400:
            detail = response.text[:300].replace("\n", " ")
            raise RuntimeError(f"HTTP {response.status_code}: {detail}")

        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("No audio candidates returned")

        parts = candidates[0].get("content", {}).get("parts") or []
        inline_data = parts[0].get("inlineData") if parts else None
        if not inline_data or not inline_data.get("data"):
            raise RuntimeError("No inline audio data returned")

        return base64.b64decode(inline_data["data"])

    def _play_audio(self, pcm_audio: bytes) -> None:
        wav_audio = _pcm_to_wav_bytes(pcm_audio, sample_rate=24000)

        if sys.platform == "win32":
            import winsound

            winsound.PlaySound(wav_audio, winsound.SND_MEMORY)
            return

        if not self._warned_playback:
            print("[TTS] Audio playback is currently implemented for Windows only.")
            self._warned_playback = True
