"""
Optional ElevenLabs text-to-speech for AI table talk.

This module is intentionally environment-driven so local runs can switch
voices/models without code changes.
"""

from __future__ import annotations

import atexit
import hashlib
import io
import os
import queue
import re
import sys
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
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


def _pcm_sample_rate(output_format: str) -> Optional[int]:
    match = re.match(r"pcm_(\d+)$", output_format or "")
    return int(match.group(1)) if match else None


def _pcm_to_wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()


def _default_cache_dir() -> Path:
    return Path(
        os.environ.get("AI_TTS_CACHE_DIR")
        or os.environ.get("PYCATAN_TTS_CACHE_DIR")
        or Path("examples") / "ai_testing" / "my_games" / "tts_cache"
    )


@dataclass
class ElevenLabsTTSConfig:
    enabled: bool
    api_key: str
    default_voice_id: str
    model_id: str = "eleven_v3"
    output_format: str = "pcm_16000"
    play_audio: bool = True
    verify_ssl: bool = True
    timeout_seconds: float = 30.0
    queue_max_size: int = 20
    stability: Optional[float] = None
    similarity_boost: Optional[float] = None
    style: Optional[float] = None
    use_speaker_boost: Optional[bool] = None
    language_code: Optional[str] = None
    cache_enabled: bool = True
    cache_dir: Path = _default_cache_dir()


class ElevenLabsTTS:
    """Small async ElevenLabs TTS client for chat messages."""

    def __init__(self, config: ElevenLabsTTSConfig):
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
                name="ElevenLabsTTS",
                daemon=True,
            )
            self._worker.start()
            atexit.register(self.close)

    @classmethod
    def from_env(cls) -> "ElevenLabsTTS":
        api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        default_voice_id = (
            os.environ.get("ELEVENLABS_TTS_DEFAULT_VOICE_ID")
            or os.environ.get("ELEVENLABS_DEFAULT_VOICE_ID")
            or ""
        ).strip()
        use_speaker_boost = os.environ.get("ELEVENLABS_TTS_USE_SPEAKER_BOOST")

        config = ElevenLabsTTSConfig(
            enabled=_env_bool("ELEVENLABS_TTS_ENABLED", False),
            api_key=api_key,
            default_voice_id=default_voice_id,
            model_id=(
                os.environ.get("ELEVENLABS_TTS_MODEL_ID")
                or os.environ.get("ELEVENLABS_MODEL_ID")
                or "eleven_v3"
            ).strip(),
            output_format=os.environ.get("ELEVENLABS_TTS_OUTPUT_FORMAT", "pcm_16000").strip(),
            play_audio=_env_bool("ELEVENLABS_TTS_PLAY_AUDIO", True),
            verify_ssl=_env_bool("ELEVENLABS_TTS_VERIFY_SSL", True),
            timeout_seconds=_env_float("ELEVENLABS_TTS_TIMEOUT_SECONDS", 30.0),
            queue_max_size=_env_int("ELEVENLABS_TTS_QUEUE_MAX_SIZE", 20),
            stability=cls._optional_float("ELEVENLABS_TTS_STABILITY"),
            similarity_boost=cls._optional_float("ELEVENLABS_TTS_SIMILARITY_BOOST"),
            style=cls._optional_float("ELEVENLABS_TTS_STYLE"),
            use_speaker_boost=(
                _env_bool("ELEVENLABS_TTS_USE_SPEAKER_BOOST", False)
                if use_speaker_boost is not None
                else None
            ),
            language_code=os.environ.get("ELEVENLABS_TTS_LANGUAGE_CODE") or None,
            cache_enabled=_env_bool("AI_TTS_CACHE_ENABLED", True),
            cache_dir=_default_cache_dir(),
        )
        return cls(config)

    @staticmethod
    def _optional_float(name: str) -> Optional[float]:
        value = os.environ.get(name)
        if value is None or value.strip() == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _is_configured(self) -> bool:
        return bool(self.config.api_key and self.config.default_voice_id)

    def describe(self) -> str:
        if not self.enabled:
            return "disabled"
        if not self._is_configured():
            return "enabled but missing ELEVENLABS_API_KEY or ELEVENLABS_DEFAULT_VOICE_ID"
        return f"enabled ({self.config.model_id}, {self.config.output_format})"

    def speak(self, player_name: str, text: str) -> None:
        """Queue a message for synthesis. Never raises into the game loop."""
        if not self.enabled:
            return

        if not self._is_configured():
            if not self._warned_unconfigured:
                print("[TTS] ElevenLabs is enabled but API key/default voice is missing.")
                self._warned_unconfigured = True
            return

        text = (text or "").strip()
        if not text:
            return

        try:
            self._queue.put_nowait((player_name, text))
        except queue.Full:
            print("[TTS] ElevenLabs queue is full; skipping latest chat audio.")

    def close(self) -> None:
        if not self._worker or not self._worker.is_alive():
            return
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        self._worker.join(timeout=5)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                break

            player_name, text = item
            try:
                audio = self._audio_for_message(player_name, text)
                if self.config.play_audio and audio:
                    self._play_audio(audio)
            except Exception as exc:
                print(f"[TTS] ElevenLabs error: {exc}")
            finally:
                self._queue.task_done()

    def speak_blocking(self, player_name: str, text: str) -> None:
        """Synthesize/play a message immediately, using the cache when possible."""
        if not self.enabled or not self._is_configured():
            return
        text = (text or "").strip()
        if not text:
            return
        try:
            audio = self._audio_for_message(player_name, text)
            if self.config.play_audio and audio:
                self._play_audio(audio)
        except Exception as exc:
            print(f"[TTS] ElevenLabs error: {exc}")

    def prepare_blocking(self, player_name: str, text: str) -> None:
        """Ensure audio exists in cache, but do not play it."""
        if not self.enabled or not self._is_configured():
            return
        text = (text or "").strip()
        if not text:
            return
        try:
            self._audio_for_message(player_name, text)
        except Exception as exc:
            print(f"[TTS] ElevenLabs prepare error: {exc}")

    def _voice_id_for_player(self, player_name: str) -> str:
        suffix = _clean_player_env_name(player_name)
        return (
            os.environ.get(f"ELEVENLABS_TTS_VOICE_{suffix}")
            or os.environ.get(f"ELEVENLABS_VOICE_{suffix}")
            or self.config.default_voice_id
        ).strip()

    def _synthesize(self, player_name: str, text: str) -> bytes:
        voice_id = self._voice_id_for_player(player_name)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        params = {"output_format": self.config.output_format}
        body = {
            "text": text,
            "model_id": self.config.model_id,
        }

        voice_settings = {}
        if self.config.stability is not None:
            voice_settings["stability"] = self.config.stability
        if self.config.similarity_boost is not None:
            voice_settings["similarity_boost"] = self.config.similarity_boost
        if self.config.style is not None:
            voice_settings["style"] = self.config.style
        if self.config.use_speaker_boost is not None:
            voice_settings["use_speaker_boost"] = self.config.use_speaker_boost
        if voice_settings:
            body["voice_settings"] = voice_settings
        if self.config.language_code:
            body["language_code"] = self.config.language_code

        response = requests.post(
            url,
            params=params,
            headers={
                "xi-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "Accept": "application/octet-stream",
            },
            json=body,
            verify=self.config.verify_ssl,
            timeout=self.config.timeout_seconds,
        )
        if response.status_code >= 400:
            detail = response.text[:300].replace("\n", " ")
            raise RuntimeError(f"HTTP {response.status_code}: {detail}")

        return response.content

    def _cache_path(self, player_name: str, text: str) -> Path:
        voice_id = self._voice_id_for_player(player_name)
        cache_key = "\n".join([
            "elevenlabs",
            self.config.model_id,
            voice_id,
            self.config.output_format,
            str(self.config.stability),
            str(self.config.similarity_boost),
            str(self.config.style),
            str(self.config.use_speaker_boost),
            str(self.config.language_code),
            text,
        ])
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        sample_rate = _pcm_sample_rate(self.config.output_format)
        extension = "wav" if sample_rate else "bin"
        return Path(self.config.cache_dir) / "elevenlabs" / f"{digest}.{extension}"

    def _audio_for_message(self, player_name: str, text: str) -> bytes:
        cache_path = self._cache_path(player_name, text)
        if self.config.cache_enabled and cache_path.exists():
            return cache_path.read_bytes()

        audio = self._synthesize(player_name, text)
        sample_rate = _pcm_sample_rate(self.config.output_format)
        if sample_rate:
            audio = _pcm_to_wav_bytes(audio, sample_rate)

        if self.config.cache_enabled:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(audio)

        return audio

    def _play_audio(self, audio: bytes) -> None:
        if sys.platform == "win32":
            import winsound

            winsound.PlaySound(audio, winsound.SND_MEMORY)
            return

        if not self._warned_playback:
            print("[TTS] Audio playback is currently implemented for Windows only.")
            self._warned_playback = True
