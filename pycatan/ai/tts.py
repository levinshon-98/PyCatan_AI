"""TTS provider selection for AI table talk."""

from __future__ import annotations

import os

from typing import Optional, Set

from pycatan.ai.config import normalize_chat_language
from pycatan.ai.tts_elevenlabs import ElevenLabsTTS
from pycatan.ai.tts_gemini import GeminiTTS


GEMINI_TTS_PROMPTS = {
    "english": "[casual, conversational, natural English speech] {text}",
    "hebrew": "[casual, conversational, Israeli Hebrew pronunciation] {text}",
}

# Gemini voices are language-capable; the prompt controls English/Hebrew
# pronunciation. Slots keep voice identity stable even when player names change.
GEMINI_TTS_SLOT_VOICES = {
    1: "Achernar",  # female
    2: "Achird",  # male
    3: "Alnilam",  # male
    4: "Kore",  # female
}


class NoopTTS:
    def describe(self) -> str:
        return "disabled"

    def speak(self, player_name: str, text: str) -> None:
        return

    def speak_blocking(self, player_name: str, text: str) -> None:
        return

    def prepare_blocking(self, player_name: str, text: str) -> None:
        return

    def stop(self) -> None:
        return

    def close(self) -> None:
        return


def _set_auto_env_default(
    name: str,
    value: str,
    replace_values: Optional[Set[str]] = None,
) -> None:
    auto_marker = f"{name}_AUTO"
    current = os.environ.get(name)
    if current and os.environ.get(auto_marker) != "chat_language":
        if not replace_values or current not in replace_values:
            return
    os.environ[name] = value
    os.environ[auto_marker] = "chat_language"


def apply_tts_language_defaults(chat_language: str) -> None:
    """Align provider language hints with the configured table-talk language."""
    language = normalize_chat_language(chat_language)
    known_prompts = set(GEMINI_TTS_PROMPTS.values())
    if language == "hebrew":
        _set_auto_env_default(
            "GEMINI_TTS_PROMPT_TEMPLATE",
            GEMINI_TTS_PROMPTS["hebrew"],
            replace_values=known_prompts,
        )
        _set_auto_env_default("ELEVENLABS_TTS_LANGUAGE_CODE", "he", {"en", "he"})
        _set_gemini_slot_voice_defaults()
        return

    _set_auto_env_default(
        "GEMINI_TTS_PROMPT_TEMPLATE",
        GEMINI_TTS_PROMPTS["english"],
        replace_values=known_prompts,
    )
    _set_auto_env_default("ELEVENLABS_TTS_LANGUAGE_CODE", "en", {"en", "he"})
    _set_gemini_slot_voice_defaults()


def _set_gemini_slot_voice_defaults() -> None:
    for slot, voice_name in GEMINI_TTS_SLOT_VOICES.items():
        _set_auto_env_default(
            f"GEMINI_TTS_VOICE_PLAYER_{slot}",
            voice_name,
            replace_values=set(GEMINI_TTS_SLOT_VOICES.values()),
        )


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
