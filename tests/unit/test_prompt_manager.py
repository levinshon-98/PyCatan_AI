"""Prompt manager tests."""

from pycatan.ai.config import AIConfig, HEBREW_RESOURCE_TERMS_INSTRUCTION
from pycatan.ai.prompt_manager import PromptManager
from pycatan.ai.schemas import ResponseType, SchemaVersion, get_schema_for_response_type


def _game_state(*names):
    return {
        "meta": {"curr": names[0] if names else None, "phase": "NORMAL_PLAY"},
        "H": [],
        "N": [],
        "state": {"bld": [], "rds": []},
        "players": {name: {"vp": 0, "res": {}} for name in names},
    }


def test_three_player_relationship_context_is_coordinated():
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

    hadar_background = hadar_prompt["meta_data"]["relationship_context"]
    shon_background = shon_prompt["meta_data"]["relationship_context"]
    ziv_background = ziv_prompt["meta_data"]["relationship_context"]

    for background in [hadar_background, shon_background, ziv_background]:
        assert "Hadar" in background
        assert "Shon" in background
        assert "Ziv" in background
        assert "Ziv warned Hadar" in background
        assert "side trade from Shon" in background

    assert "Shon hurt your trust" in hadar_background
    assert "Hadar has reason to distrust you" in shon_background
    assert "you warned Hadar about Shon" in ziv_background


def test_relationship_context_has_fallback_for_two_players():
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

    background = prompt["meta_data"]["relationship_context"]
    assert "Bob" in background
    assert "Alice" in background
    assert "strong legal Catan play" in background


def test_relationship_context_includes_all_four_players():
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

    background = prompt["meta_data"]["relationship_context"]
    assert "Alice" in background
    assert "Bob" in background
    assert "Charlie" in background
    assert "Diana" in background
    assert "robber pressure" in background


def test_relationship_context_includes_recent_updates():
    manager = PromptManager()
    state = _game_state("Alice", "Bob", "Charlie")

    prompt = manager.create_prompt(
        player_num=0,
        player_name="Alice",
        player_color="Red",
        game_state=state,
        what_happened="Game start",
        available_actions=[],
        relationship_updates=[
            {"note": "Bob mocked my blocked ore and refused a fair trade."},
        ],
    )

    context = prompt["meta_data"]["relationship_context"]
    assert "Recent relationship shifts" in context
    assert "Bob mocked my blocked ore" in context


def test_relationship_context_can_be_disabled():
    config = AIConfig()
    config.agent.relationship_context_mode = "off"
    manager = PromptManager(config)
    state = _game_state("Gemini", "Claude", "GPT")

    prompt = manager.create_prompt(
        player_num=0,
        player_name="Gemini",
        player_color="Red",
        game_state=state,
        what_happened="Game start",
        available_actions=[],
    )

    assert "relationship_context" not in prompt["meta_data"]


def test_ai_model_relationship_context_is_short_and_named():
    config = AIConfig()
    config.agent.relationship_context_mode = "ai_models"
    manager = PromptManager(config)
    state = _game_state("Gemini", "Claude", "GPT")

    prompt = manager.create_prompt(
        player_num=1,
        player_name="Claude",
        player_color="Blue",
        game_state=state,
        what_happened="Game start",
        available_actions=[],
    )

    context = prompt["meta_data"]["relationship_context"]
    assert "Gemini represents Gemini" in context
    assert "Claude represents Claude" in context
    assert "GPT represents GPT" in context
    assert "Your angle: you are Claude" in context
    assert "charming dealmaker" not in context
    assert len(context) < 320


def test_prompt_includes_five_point_game_context():
    manager = PromptManager()
    state = _game_state("Hadar", "Shon")
    state["meta"]["vp_to_win"] = 5

    prompt = manager.create_prompt(
        player_num=0,
        player_name="Hadar",
        player_color="Red",
        game_state=state,
        what_happened="Game start",
        available_actions=[],
    )

    assert prompt["meta_data"]["game_context"] == (
        "CONTEXT: You are playing Catan to 5 victory points. "
        "The first player to reach 5 VP wins."
    )


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


def test_hebrew_chat_prompt_requires_exact_resource_terms():
    config = AIConfig()
    config.agent.chat_language = "hebrew"
    manager = PromptManager(config)
    state = _game_state("Hadar", "Shon")

    prompt = manager.create_prompt(
        player_num=0,
        player_name="Hadar",
        player_color="Red",
        game_state=state,
        what_happened="Your turn.",
        available_actions=[{"type": "end_turn", "example_parameters": "{}"}],
    )

    instructions = prompt["task_context"]["instructions"]
    assert "לא כמו קריין" in instructions
    assert HEBREW_RESOURCE_TERMS_INSTRUCTION in instructions
    assert "brick=טיט" in instructions
    assert "ore=אבן" in instructions
    assert "sheep=כבשה" in instructions
    assert "wheat=חיטה" in instructions


def test_robber_prompt_guides_agents_to_inspect_hex():
    manager = PromptManager()
    state = _game_state("Hadar", "Shon")

    prompt = manager.create_prompt(
        player_num=0,
        player_name="Hadar",
        player_color="Red",
        game_state=state,
        what_happened="You rolled a 7.",
        available_actions=[{"type": "robber_move", "example_parameters": '{"hex": X}'}],
    )

    instructions = prompt["task_context"]["instructions"]
    assert "For robber placement, use inspect_hex" in instructions
    assert "adjacent buildings" in instructions


def test_hebrew_chat_schema_requires_exact_resource_terms():
    schema = get_schema_for_response_type(
        ResponseType.ACTIVE_TURN,
        SchemaVersion.V2,
        chat_language="hebrew",
    )

    description = schema["properties"]["say_outloud"]["description"]
    assert "לא כמו קריין" in description
    assert HEBREW_RESOURCE_TERMS_INSTRUCTION in description
