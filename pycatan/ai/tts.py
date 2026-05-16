"""TTS provider selection for AI table talk."""

from __future__ import annotations

import os

from pycatan.ai.config import normalize_chat_language
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


def _set_auto_env_default(name: str, value: str) -> None:
    auto_marker = f"{name}_AUTO"
    if os.environ.get(name) and os.environ.get(auto_marker) != "chat_language":
        return
    os.environ[name] = value
    os.environ[auto_marker] = "chat_language"


def apply_tts_language_defaults(chat_language: str) -> None:
    """Align provider language hints with the configured table-talk language."""
    language = normalize_chat_language(chat_language)
    if language == "hebrew":
        _set_auto_env_default(
            "GEMINI_TTS_PROMPT_TEMPLATE",
            "[casual, conversational, Israeli Hebrew pronunciation] {text}",
        )
        _set_auto_env_default("ELEVENLABS_TTS_LANGUAGE_CODE", "he")
        return

    _set_auto_env_default(
        "GEMINI_TTS_PROMPT_TEMPLATE",
        "[casual, conversational, natural English speech] {text}",
    )
    _set_auto_env_default("ELEVENLABS_TTS_LANGUAGE_CODE", "en")


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
