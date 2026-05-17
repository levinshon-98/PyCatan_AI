import json
import tempfile
import unittest
import wave
from pathlib import Path

from examples.ai_testing.replay_viewer import (
    build_mobile_email_html,
    build_mobile_email_text,
    build_manifest,
    list_sessions,
    public_manifest,
    public_sessions,
    read_public_config,
    _owner_notification_template_params,
    write_manifest_artifact,
    write_public_config,
)


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

    def test_public_config_filters_and_decorates_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs_dir = Path(tmp)
            for name in ("session_alpha", "session_beta"):
                _write_json(
                    logs_dir / name / "Dana" / "responses" / "response_1.json",
                    {
                        "request_number": 1,
                        "timestamp": "2026-05-17T12:00:00",
                        "player_name": "Dana",
                        "type": "final",
                        "parsed": {},
                    },
                )

            write_public_config(
                {
                    "sessions": [
                        {"name": "session_alpha", "enabled": False, "title": "Hidden"},
                        {"name": "session_beta", "enabled": True, "title": "Public game", "description": "Demo replay"},
                    ]
                },
                logs_dir=logs_dir,
            )

            config = read_public_config(logs_dir)
            exposed = public_sessions(list_sessions(logs_dir), config)

            self.assertEqual([session["name"] for session in exposed], ["session_beta"])
            self.assertEqual(exposed[0]["title"], "Public game")
            self.assertEqual(exposed[0]["description"], "Demo replay")

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
                        "game_state": (
                            'Board facts\\nJSON:\\n'
                            '{"meta":{"robber":10,"dice":[3,4],"dice_total":7},'
                            '"H":["","W12","S5","D"],'
                            '"state":{"bld":[[20,"Dana","S"]],"rds":[[[1,2],"Dana"]]},'
                            '"players":{"Dana":{"vp":1,"res":{"W":2,"B":1,"Wh":3},'
                            '"dev":{"hidden_count":1,"r":["K"]},"stat":["LR","LA"]}}}'
                        )
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
            self.assertEqual(manifest["events"][0]["state_before"]["players"]["Dana"]["resources"]["wood"], 2)
            self.assertEqual(manifest["events"][0]["state_before"]["players"]["Dana"]["resources"]["brick"], 1)
            self.assertEqual(manifest["events"][0]["state_before"]["players"]["Dana"]["resources"]["wheat"], 3)
            self.assertEqual(manifest["events"][0]["state_before"]["players"]["Dana"]["dev"]["r"], ["K"])
            self.assertEqual(manifest["events"][0]["state_before"]["players"]["Dana"]["stat"], ["LR", "LA"])
            self.assertEqual(manifest["events"][0]["state_before"]["meta"]["dice_total"], 7)
            self.assertEqual(manifest["events"][0]["state_before"]["state"]["buildings"][0]["node"], 20)

    def test_build_manifest_chains_continued_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "session_parent"
            child = Path(tmp) / "session_child"
            _write_json(
                parent / "Dana" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:00:00",
                    "player_name": "Dana",
                    "type": "final",
                    "parsed": {"action_type": "roll_dice", "parameters": {}},
                },
            )
            _write_json(
                parent / "Dana" / "responses" / "response_2.json",
                {
                    "request_number": 2,
                    "timestamp": "2026-05-17T12:01:00",
                    "player_name": "Dana",
                    "type": "final",
                    "parsed": {"action_type": "end_turn", "parameters": {}},
                },
            )
            _write_json(
                child / "session_metadata.json",
                {
                    "run_settings": {"run_mode": "resume_session", "replay": {"session": str(parent), "through": "Dana:1"}},
                    "replay": {"source_session": str(parent), "replay_through": "Dana:1"},
                },
            )
            _write_json(
                child / "chat_history.json",
                {
                    "messages": [
                        {
                            "timestamp": "2026-05-17T12:01:30",
                            "from": "Dana",
                            "to": "all",
                            "message": "Replayed source chat should not appear.",
                        }
                    ]
                },
            )
            _write_json(
                parent / "Dana" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:00:00",
                    "player_name": "Dana",
                    "type": "final",
                    "parsed": {
                        "action_type": "roll_dice",
                        "parameters": {},
                        "say_outloud": "Replayed source chat should not appear.",
                    },
                },
            )
            _write_json(
                child / "Shon" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:02:00",
                    "player_name": "Shon",
                    "type": "final",
                    "parsed": {"action_type": "roll_dice", "parameters": {}},
                },
            )

            manifest = build_manifest(child)

            self.assertTrue(manifest["session"]["continuation"]["is_continuation"])
            self.assertEqual(manifest["stats"]["events"], 2)
            self.assertEqual([event["response_id"] for event in manifest["events"]], ["Dana:1", "Shon:1"])
            self.assertEqual(manifest["events"][0]["timeline_role"], "source")
            self.assertEqual(manifest["events"][1]["timeline_role"], "current")
            self.assertNotIn("chat:0", [event["response_id"] for event in manifest["events"]])

    def test_mobile_email_includes_context_and_links(self) -> None:
        record = {
            "email": "viewer@example.com",
            "session": "session_20260517_222029",
            "page": "https://example.com/?session=session_20260517_222029",
        }

        html_body = build_mobile_email_html(record)
        text_body = build_mobile_email_text(record)

        self.assertIn("experimental replay interface", html_body)
        self.assertIn("https://example.com/?session=session_20260517_222029", html_body)
        self.assertIn("session_20260517_222029", html_body)
        self.assertIn("https://www.linkedin.com/in/shon-levin/", html_body)
        self.assertIn("Catan games played by AI agents", text_body)

    def test_owner_notification_includes_recipient_and_session(self) -> None:
        record = {
            "email": "viewer@example.com",
            "session": "session_20260517_222029",
            "page": "https://example.com/?session=session_20260517_222029",
            "created_at": "2026-05-17T23:59:00",
        }

        params = _owner_notification_template_params(record)

        self.assertEqual(params["to"], "levinshon@gmail.com")
        self.assertIn("viewer@example.com", params["title"])
        self.assertIn("viewer@example.com", params["data"])
        self.assertIn("session_20260517_222029", params["data"])
        self.assertIn("https://example.com/?session=session_20260517_222029", params["message"])


if __name__ == "__main__":
    unittest.main()
