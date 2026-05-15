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

    assert "Shon is an old friend" in hadar_background
    assert "they betrayed you" in hadar_background
    assert "you betrayed them" in shon_background
    assert "Shon betrayed Hadar" in ziv_background


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
    assert "strong legal Catan play" in background
