"""Unit tests for TTS language defaults."""

import os

from pycatan.ai.tts import apply_tts_language_defaults


def test_english_chat_sets_english_tts_defaults(monkeypatch):
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE", raising=False)
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE_AUTO", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE_AUTO", raising=False)
    for slot in range(1, 5):
        monkeypatch.delenv(f"GEMINI_TTS_VOICE_PLAYER_{slot}", raising=False)
        monkeypatch.delenv(f"GEMINI_TTS_VOICE_PLAYER_{slot}_AUTO", raising=False)

    apply_tts_language_defaults("english")

    assert "natural English speech" in os.environ["GEMINI_TTS_PROMPT_TEMPLATE"]
    assert os.environ["ELEVENLABS_TTS_LANGUAGE_CODE"] == "en"
    assert os.environ["GEMINI_TTS_VOICE_PLAYER_1"] == "Achernar"
    assert os.environ["GEMINI_TTS_VOICE_PLAYER_2"] == "Achird"
    assert os.environ["GEMINI_TTS_VOICE_PLAYER_3"] == "Alnilam"
    assert os.environ["GEMINI_TTS_VOICE_PLAYER_4"] == "Kore"


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
    monkeypatch.setenv("GEMINI_TTS_VOICE_PLAYER_1", "Puck")
    monkeypatch.delenv("GEMINI_TTS_VOICE_PLAYER_1_AUTO", raising=False)

    apply_tts_language_defaults("english")

    assert os.environ["GEMINI_TTS_PROMPT_TEMPLATE"] == "custom {text}"
    assert os.environ["ELEVENLABS_TTS_LANGUAGE_CODE"] == "fr"
    assert os.environ["GEMINI_TTS_VOICE_PLAYER_1"] == "Puck"


def test_known_tts_language_defaults_can_replace_legacy_explicit_values(monkeypatch):
    monkeypatch.setenv(
        "GEMINI_TTS_PROMPT_TEMPLATE",
        "[casual, conversational, Israeli Hebrew pronunciation] {text}",
    )
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE_AUTO", raising=False)
    monkeypatch.setenv("ELEVENLABS_TTS_LANGUAGE_CODE", "he")
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE_AUTO", raising=False)

    apply_tts_language_defaults("english")

    assert "natural English speech" in os.environ["GEMINI_TTS_PROMPT_TEMPLATE"]
    assert os.environ["ELEVENLABS_TTS_LANGUAGE_CODE"] == "en"


def test_auto_tts_language_defaults_can_switch(monkeypatch):
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE", raising=False)
    monkeypatch.delenv("GEMINI_TTS_PROMPT_TEMPLATE_AUTO", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_LANGUAGE_CODE_AUTO", raising=False)

    apply_tts_language_defaults("english")
    apply_tts_language_defaults("hebrew")

    assert "Israeli Hebrew pronunciation" in os.environ["GEMINI_TTS_PROMPT_TEMPLATE"]
    assert os.environ["ELEVENLABS_TTS_LANGUAGE_CODE"] == "he"
