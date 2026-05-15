"""Prompt manager tests."""

from pycatan.ai.prompt_manager import PromptManager


def _game_state(*names):
    return {
        "meta": {"curr": names[0] if names else None, "phase": "NORMAL_PLAY"},
        "H": [],
        "N": [],
        "state": {"bld": [], "rds": []},
        "players": {name: {"vp": 0, "res": {}} for name in names},
    }


def test_three_player_relationship_background_is_coordinated():
    manager = PromptManager()
    state = _game_state("Hadar", "Shon", "Ziv")

    hadar_prompt = manager.create_prompt(
        player_num=0,
        player_name="Hadar",
        player_color="Red",
        game_state=state,
        what_happened="Game start",
        available_actions=[],
    )
    shon_prompt = manager.create_prompt(
        player_num=1,
        player_name="Shon",
        player_color="Blue",
        game_state=state,
        what_happened="Game start",
        available_actions=[],
    )
    ziv_prompt = manager.create_prompt(
        player_num=2,
        player_name="Ziv",
        player_color="White",
        game_state=state,
        what_happened="Game start",
        available_actions=[],
    )

    hadar_background = hadar_prompt["meta_data"]["relationship_background"]
    shon_background = shon_prompt["meta_data"]["relationship_background"]
    ziv_background = ziv_prompt["meta_data"]["relationship_background"]

    for background in [hadar_background, shon_background, ziv_background]:
        assert "Hadar" in background
        assert "Shon" in background
        assert "Ziv" in background
        assert "Ziv warned Hadar" in background
        assert "side trade from Shon" in background

    assert "Shon hurt your trust" in hadar_background
    assert "Hadar has reason to distrust you" in shon_background
    assert "you warned Hadar about Shon" in ziv_background


def test_relationship_background_has_fallback_for_two_players():
    manager = PromptManager()
    state = _game_state("Alice", "Bob")

    prompt = manager.create_prompt(
        player_num=0,
        player_name="Alice",
        player_color="Red",
        game_state=state,
        what_happened="Game start",
        available_actions=[],
    )

    background = prompt["meta_data"]["relationship_background"]
    assert "Bob" in background
    assert "Alice" in background
    assert "strong legal Catan play" in background


def test_relationship_background_includes_all_four_players():
    manager = PromptManager()
    state = _game_state("Alice", "Bob", "Charlie", "Diana")

    prompt = manager.create_prompt(
        player_num=3,
        player_name="Diana",
        player_color="Orange",
        game_state=state,
        what_happened="Game start",
        available_actions=[],
    )

    background = prompt["meta_data"]["relationship_background"]
    assert "Alice" in background
    assert "Bob" in background
    assert "Charlie" in background
    assert "Diana" in background
    assert "robber pressure" in background


def test_trade_context_summarizes_resolved_trades_and_keeps_open_trades_structured():
    manager = PromptManager()
    state = _game_state("Shon", "Ziv")

    prompt = manager.create_prompt(
        player_num=0,
        player_name="Shon",
        player_color="Blue",
        game_state=state,
        what_happened="Ziv is deciding.",
        available_actions=[],
        pending_trades=[
            {
                "trade_id": "trade_1",
                "from": "Shon",
                "to": "Ziv",
                "offer": {"wheat": 1},
                "request": {"brick": 1},
                "status": "rejected",
                "timestamp": 123.0,
                "responded_by": "Ziv",
                "resolved_at": 124.0,
            },
            {
                "trade_id": "trade_2",
                "from": "Ziv",
                "to": "Shon",
                "offer": {"sheep": 1},
                "request": {"wood": 1},
                "status": "accepted",
                "timestamp": 125.0,
                "responded_by": "Shon",
                "resolved_at": 126.0,
            },
            {
                "trade_id": "trade_3",
                "from": "Ziv",
                "to": "Shon",
                "offer": {"ore": 1},
                "request": {"wheat": 1},
                "status": "pending",
                "timestamp": 127.0,
            },
        ],
    )

    social = prompt["social_context"]
    assert social["trade_context"] == (
        "Recent trade history: You offered Ziv 1 wheat for 1 brick; Ziv rejected. "
        "Ziv offered you 1 sheep for 1 wood; you accepted."
    )
    assert social["pending_trades"] == [
        {
            "trade_id": "trade_3",
            "from": "Ziv",
            "to": "Shon",
            "offer": {"ore": 1},
            "request": {"wheat": 1},
            "status": "pending",
        }
    ]
