"""TTS provider selection for AI table talk."""

from __future__ import annotations

import os

from pycatan.ai.tts_elevenlabs import ElevenLabsTTS
from pycatan.ai.tts_gemini import GeminiTTS


class NoopTTS:
    def describe(self) -> str:
        return "disabled"

    def speak(self, player_name: str, text: str) -> None:
        return

    def speak_blocking(self, player_name: str, text: str) -> None:
        return

    def prepare_blocking(self, player_name: str, text: str) -> None:
        return

    def close(self) -> None:
        return


def create_tts_from_env():
    provider = (
        os.environ.get("TTS_PROVIDER")
        or os.environ.get("AI_TTS_PROVIDER")
        or "off"
    ).strip().lower()

    if provider in {"off", "none", "false", "0", "disabled", ""}:
        return NoopTTS()
    if provider in {"elevenlabs", "eleven", "11labs"}:
        return ElevenLabsTTS.from_env()
    if provider in {"gemini", "google", "google-gemini"}:
        return GeminiTTS.from_env()

    print(f"[TTS] Unknown TTS_PROVIDER={provider!r}; disabling TTS.")
    return NoopTTS()
