import json
import tempfile
import unittest
from pathlib import Path

from examples.ai_testing.play_with_ai import (
    ReplayAIUser,
    group_replay_decisions,
    list_replay_marker_options,
    load_replay_decisions,
)
from pycatan.management.actions import Action, ActionType


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class _FakeAIManager:
    def __init__(self) -> None:
        self.broadcasts = []

    def register_agent(self, name: str, user_id: int, color: str = "") -> None:
        pass

    def _broadcast_chat(self, from_player: str, message: str, speak: bool = True) -> None:
        self.broadcasts.append((from_player, message, speak))


class ReplayResponseTimelineTests(unittest.TestCase):
    def test_replay_loads_action_and_speech_only_responses_in_one_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp) / "session_20260517_120000"
            _write_json(
                session_dir / "Dana" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:00:05",
                    "player_name": "Dana",
                    "raw_content": "{}",
                    "parsed": {
                        "action_type": "build_road",
                        "parameters": {"from": 1, "to": 2},
                        "say_outloud": "I am taking the road first.",
                    },
                },
            )
            _write_json(
                session_dir / "Shon" / "responses" / "response_1.json",
                {
                    "request_number": 1,
                    "timestamp": "2026-05-17T12:00:10",
                    "player_name": "Shon",
                    "raw_content": "{}",
                    "parsed": {
                        "note_to_self": "Dana is expanding.",
                        "say_outloud": "Noted.",
                    },
                },
            )

            responses = load_replay_decisions(session_dir)

            self.assertEqual([item["player_name"] for item in responses], ["Dana", "Shon"])
            self.assertTrue(responses[0]["has_action"])
            self.assertFalse(responses[1]["has_action"])
            self.assertTrue(responses[1]["has_speech"])
            self.assertEqual(list(group_replay_decisions(responses)), ["Dana"])

            markers = list_replay_marker_options(session_dir)
            self.assertEqual(markers[0]["kind"], "action")
            self.assertEqual(markers[1]["kind"], "speech")

    def test_replay_action_chat_respects_skip_chat(self) -> None:
        ai_manager = _FakeAIManager()
        user = ReplayAIUser(
            "Dana",
            0,
            ai_manager,
            replay_chat=False,
            replay_speak=False,
        )
        action = Action(
            ActionType.END_TURN,
            0,
            {"_ai_replay": True, "_ai_say_outloud": "Recorded chat"},
        )

        user.notify_action(action, success=True)

        self.assertEqual(ai_manager.broadcasts, [])
        self.assertTrue(action.parameters["_ai_say_outloud_public"])

    def test_replay_action_chat_uses_replay_speak_flag(self) -> None:
        ai_manager = _FakeAIManager()
        user = ReplayAIUser(
            "Dana",
            0,
            ai_manager,
            replay_chat=True,
            replay_speak=False,
        )
        action = Action(
            ActionType.END_TURN,
            0,
            {"_ai_replay": True, "_ai_say_outloud": "Recorded chat"},
        )

        user.notify_action(action, success=True)

        self.assertEqual(ai_manager.broadcasts, [("Dana", "Recorded chat", False)])
        self.assertTrue(action.parameters["_ai_say_outloud_public"])


if __name__ == "__main__":
    unittest.main()
