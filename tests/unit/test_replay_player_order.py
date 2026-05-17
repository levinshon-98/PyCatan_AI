import json
import tempfile
import unittest
from pathlib import Path

from examples.ai_testing.play_with_ai import infer_players_from_session
from examples.ai_testing.play_with_openrouter import _infer_session_player_names


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class ReplayPlayerOrderTests(unittest.TestCase):
    def test_replay_player_order_prefers_stored_run_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp) / "session_20260516_120000"
            _write_json(
                session_dir / "session_metadata.json",
                {
                    "run_settings": {
                        "players": [
                            {"slot": 1, "name": "Alice"},
                            {"slot": 2, "name": "Bob"},
                            {"slot": 3, "name": "Charlie"},
                        ]
                    }
                },
            )

            # Async spectator reactions can make the first response timestamps
            # differ from the real GameManager player slot order.
            _write_json(
                session_dir / "Alice" / "responses" / "response_1.json",
                {"timestamp": "2026-05-16T12:00:01", "player_name": "Alice"},
            )
            _write_json(
                session_dir / "Bob" / "responses" / "response_1.json",
                {"timestamp": "2026-05-16T12:00:03", "player_name": "Bob"},
            )
            _write_json(
                session_dir / "Charlie" / "responses" / "response_1.json",
                {"timestamp": "2026-05-16T12:00:02", "player_name": "Charlie"},
            )

            self.assertEqual(infer_players_from_session(session_dir), ["Alice", "Bob", "Charlie"])
            self.assertEqual(_infer_session_player_names(session_dir), ["Alice", "Bob", "Charlie"])


if __name__ == "__main__":
    unittest.main()
