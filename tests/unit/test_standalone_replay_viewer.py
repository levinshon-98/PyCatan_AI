import json
import tempfile
import unittest
import wave
from pathlib import Path

from examples.ai_testing.replay_viewer import build_manifest, list_sessions, public_manifest, write_manifest_artifact


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_wav(path: Path, seconds: float = 0.1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(24000 * seconds)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24000)
        wav_file.writeframes(b"\x00\x00" * frames)


class StandaloneReplayViewerTests(unittest.TestCase):
    def test_build_manifest_from_session_responses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session_test"
            _write_json(
                session / "Dana" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:00:00",
                    "player_name": "Dana",
                    "type": "final",
                    "raw_content": "{}",
                    "parsed": {
                        "say_outloud": "I will build here.",
                        "action_type": "build_road",
                        "parameters": {"from": 1, "to": 2},
                    },
                },
            )
            _write_json(
                session / "Shon" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:00:10",
                    "player_name": "Shon",
                    "type": "final",
                    "raw_content": "{}",
                    "parsed": {"note_to_self": "Dana expands."},
                },
            )

            manifest = build_manifest(session, max_gap_seconds=2.5)

            self.assertEqual(manifest["stats"]["events"], 2)
            self.assertEqual(manifest["stats"]["actions"], 1)
            self.assertEqual(manifest["events"][0]["response_id"], "Dana:1")
            self.assertEqual(manifest["events"][0]["kind"], "action")
            self.assertEqual(manifest["events"][0]["timeline_gap_seconds"], 2.5)
            self.assertNotIn("_audio_by_id", public_manifest(manifest))

    def test_manifest_artifact_is_written_without_private_audio_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session_test"
            audio_path = session / "tts_cache" / "gemini" / "clip.wav"
            _write_wav(audio_path)
            manifest = {
                "session": {"name": "session_test", "path": str(session)},
                "stats": {"events": 0, "actions": 0, "speech": 0, "audio": 0},
                "events": [],
                "_audio_by_id": {"clip": audio_path},
            }

            artifact = write_manifest_artifact(session, manifest)
            saved = json.loads(artifact.read_text(encoding="utf-8"))

            self.assertTrue(artifact.exists())
            self.assertNotIn("_audio_by_id", saved)

    def test_build_manifest_uses_explicit_audio_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session_test"
            audio_path = session / "audio" / "dana_1.wav"
            _write_wav(audio_path, seconds=0.2)
            _write_json(
                session / "replay_audio_manifest.json",
                {"Dana:1": "audio/dana_1.wav"},
            )
            _write_json(
                session / "Dana" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:00:00",
                    "player_name": "Dana",
                    "type": "final",
                    "parsed": {
                        "say_outloud": "This clip is explicitly linked.",
                    },
                },
            )

            manifest = build_manifest(session)

            self.assertEqual(manifest["stats"]["audio"], 1)
            self.assertTrue(manifest["events"][0]["has_audio"])
            self.assertEqual(manifest["events"][0]["audio_url"], "/api/audio/Dana_1_0")
            self.assertIn("Dana_1_0", manifest["_audio_by_id"])

    def test_list_sessions_returns_latest_session_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs_dir = Path(tmp)
            session = logs_dir / "session_20260517_120000"
            _write_json(
                session / "session_metadata.json",
                {"start_time": "2026-05-17T12:00:00"},
            )
            _write_json(
                session / "Dana" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:00:01",
                    "player_name": "Dana",
                    "type": "final",
                    "parsed": {},
                },
            )

            sessions = list_sessions(logs_dir)

            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["name"], "session_20260517_120000")
            self.assertEqual(sessions[0]["responses"], 1)

    def test_build_manifest_adds_chat_only_messages_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session_test"
            _write_json(
                session / "Dana" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:00:00",
                    "player_name": "Dana",
                    "type": "final",
                    "parsed": {"say_outloud": "I already said this."},
                },
            )
            _write_json(
                session / "chat_history.json",
                {
                    "messages": [
                        {
                            "timestamp": "2026-05-17T12:00:01",
                            "from": "Dana",
                            "to": "all",
                            "message": "I already said this.",
                        },
                        {
                            "timestamp": "2026-05-17T12:00:02",
                            "from": "Shon",
                            "to": "Dana",
                            "message": "That was a reaction.",
                        },
                    ]
                },
            )

            manifest = build_manifest(session)

            self.assertEqual(manifest["stats"]["events"], 2)
            self.assertEqual(manifest["stats"]["chat"], 1)
            self.assertEqual(manifest["events"][1]["kind"], "chat")
            self.assertEqual(manifest["events"][1]["chat_to"], "Dana")

    def test_build_manifest_includes_board_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session_test"
            _write_json(
                session / "Dana" / "prompts" / "prompt_1.json",
                {
                    "prompt": {
                        "game_state": 'Board facts\\nJSON:\\n{"meta":{"robber":10},"H":["","W12","S5","D"]}'
                    }
                },
            )
            _write_json(
                session / "Dana" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:00:00",
                    "player_name": "Dana",
                    "type": "final",
                    "parsed": {"action_type": "place_starting_settlement", "parameters": {"node": 20}},
                },
            )

            manifest = build_manifest(session)

            self.assertIn("board", manifest)
            self.assertEqual(len(manifest["board"]["points"]), 54)
            self.assertEqual(manifest["board"]["initial_robber"], 10)
            self.assertEqual(manifest["board"]["hexes"][0]["type"], "wood")
            self.assertEqual(manifest["board"]["hexes"][0]["number"], 12)


if __name__ == "__main__":
    unittest.main()
