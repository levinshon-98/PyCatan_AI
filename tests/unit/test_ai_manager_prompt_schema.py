"""Unit tests for AIManager prompt/schema shaping."""

from pycatan.ai.ai_manager import AIManager


def test_active_turn_schema_limits_action_type_to_allowed_actions(tmp_path):
    manager = AIManager(
        session_dir=tmp_path,
        send_to_llm=False,
        manual_actions=False,
    )
    manager.register_agent("Gemma", 0, "red")
    agent = manager.get_agent("Gemma")

    _, schema = manager._create_prompt(
        agent=agent,
        game_state={
            "meta": {"curr": "Gemma", "phase": "SETUP_FIRST_ROUND"},
            "H": ["", "W12"],
            "N": [None, [[2], [1]], [[1], [1]]],
            "state": {"bld": [], "rds": []},
            "players": {"Gemma": {"vp": 0, "res": {}}},
        },
        what_happened="Current required action: Place your starting settlement.",
        allowed_actions=["PLACE_STARTING_SETTLEMENT"],
        is_active_turn=True,
    )

    action_type = schema["properties"]["action"]["properties"]["type"]
    assert action_type["enum"] == ["place_starting_settlement"]
    assert "Tool names are not valid actions" in action_type["description"]
