"""Unit tests for TTS language defaults."""

import os

from pycatan.ai.tts import apply_tts_language_defaults


def test_english_chat_sets_english_tts_defaults(monkeypatch):
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE", raising=False)
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE_AUTO", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE_AUTO", raising=False)

    apply_tts_language_defaults("english")

    assert "natural English speech" in os.environ["GEMINI_TTS_PROMPT_TEMPLATE"]
    assert os.environ["ELEVENLABS_TTS_LANGUAGE_CODE"] == "en"


def test_hebrew_chat_sets_hebrew_tts_defaults(monkeypatch):
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE", raising=False)
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE_AUTO", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE_AUTO", raising=False)

    apply_tts_language_defaults("hebrew")

    assert "Israeli Hebrew pronunciation" in os.environ["GEMINI_TTS_PROMPT_TEMPLATE"]
    assert os.environ["ELEVENLABS_TTS_LANGUAGE_CODE"] == "he"


def test_tts_language_defaults_do_not_override_explicit_env(monkeypatch):
    monkeypatch.setenv("GEMINI_TTS_PROMPT_TEMPLATE", "custom {text}")
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE_AUTO", raising=False)
    monkeypatch.setenv("ELEVENLABS_TTS_LANGUAGE_CODE", "fr")
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE_AUTO", raising=False)

    apply_tts_language_defaults("english")

    assert os.environ["GEMINI_TTS_PROMPT_TEMPLATE"] == "custom {text}"
    assert os.environ["ELEVENLABS_TTS_LANGUAGE_CODE"] == "fr"


def test_auto_tts_language_defaults_can_switch(monkeypatch):
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE", raising=False)
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE_AUTO", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE_AUTO", raising=False)

    apply_tts_language_defaults("english")
    apply_tts_language_defaults("hebrew")

    assert "Israeli Hebrew pronunciation" in os.environ["GEMINI_TTS_PROMPT_TEMPLATE"]
    assert os.environ["ELEVENLABS_TTS_LANGUAGE_CODE"] == "he"
