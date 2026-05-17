"""Unit tests for AIUser action translation."""

from dataclasses import dataclass

import pytest

from pycatan.ai.ai_user import AIUser
from pycatan.management.actions import Action, ActionType


@dataclass
class DummyAgent:
    player_name: str
    player_id: int
    player_color: str = ""
    recent_events: list = None

    def __post_init__(self):
        if self.recent_events is None:
            self.recent_events = []

    def add_event(self, event_type, message, data=None):
        event = {"type": event_type, "message": message}
        if data:
            event["data"] = data
        self.recent_events.append(event)


class DummyAIManager:
    def __init__(self):
        self.agents = {}
        self.chat = []

    def register_agent(self, name, user_id, color):
        self.agents[name] = DummyAgent(name, user_id, color)

    def get_agent(self, name):
        return self.agents.get(name)

    def _broadcast_chat(self, from_player, message):
        self.chat.append({"from": from_player, "message": message})


def make_ai_user():
    manager = DummyAIManager()
    manager.register_agent("Alice", 0, "red")
    manager.register_agent("Bob", 1, "blue")
    manager.register_agent("Charlie", 2, "green")
    return AIUser("Bob", 1, manager, "blue")


def test_steal_card_resolves_target_player_name_to_id():
    user = make_ai_user()

    action = user._decision_to_action(
        {
            "action_type": "steal_card",
            "parameters": {"target_player": "Charlie"},
        },
        ["STEAL_CARD"],
    )

    assert action.action_type == ActionType.STEAL_CARD
    assert action.parameters["target_player"] == 2


def test_steal_card_resolves_target_player_color_to_id():
    user = make_ai_user()

    action = user._decision_to_action(
        {
            "action_type": "steal_card",
            "parameters": {"target_player": "green"},
        },
        ["STEAL_CARD"],
    )

    assert action.parameters["target_player"] == 2


def test_steal_card_maps_unknown_target_player_to_invalid_id():
    user = make_ai_user()

    action = user._decision_to_action(
        {
            "action_type": "steal_card",
            "parameters": {"target_player": "Nobody"},
        },
        ["STEAL_CARD"],
    )

    assert action.parameters["target_player"] == -1


def test_trade_propose_resolves_target_player_name_to_id():
    user = make_ai_user()

    action = user._decision_to_action(
        {
            "action_type": "trade_propose",
            "parameters": {
                "target_player": "Charlie",
                "offer": {"sheep": 1},
                "request": {"wood": 1},
            },
        },
        ["TRADE_PROPOSE"],
    )

    assert action.action_type == ActionType.TRADE_PROPOSE
    assert action.parameters["target_player"] == 2
    assert action.parameters["offer"] == {"sheep": 1}
    assert action.parameters["request"] == {"wood": 1}


def test_trade_propose_accepts_target_alias():
    user = make_ai_user()

    action = user._decision_to_action(
        {
            "action_type": "trade_propose",
            "parameters": {
                "to": "green",
                "offer": {"sheep": 1},
                "request": {"wood": 1},
            },
        },
        ["TRADE_PROPOSE"],
    )

    assert action.parameters["target_player"] == 2


def test_trade_bank_give_receive_converts_to_engine_offer_request():
    user = make_ai_user()

    action = user._decision_to_action(
        {
            "action_type": "trade_bank",
            "parameters": {"give": "wheat", "receive": "ore"},
        },
        ["TRADE_BANK"],
    )

    assert action.action_type == ActionType.TRADE_BANK
    assert action.parameters == {"offer": {"wheat": 4}, "request": {"ore": 1}}


def test_robber_move_preserves_self_block_confirmation():
    user = make_ai_user()

    action = user._decision_to_action(
        {
            "action_type": "robber_move",
            "parameters": {"hex": 5, "confirm_self_block": True},
        },
        ["ROBBER_MOVE"],
    )

    assert action.action_type == ActionType.ROBBER_MOVE
    assert action.parameters["confirm_self_block"] is True


def test_empty_say_outloud_is_preserved_as_intentional_silence():
    user = make_ai_user()

    action = user._decision_to_action(
        {
            "action_type": "robber_move",
            "parameters": {"hex": 5, "confirm_self_block": True},
            "say_outloud": "",
        },
        ["ROBBER_MOVE"],
    )

    assert action.parameters["_ai_say_outloud"] == ""


def test_failed_action_is_added_to_agent_events():
    user = make_ai_user()
    action = user._decision_to_action(
        {
            "action_type": "steal_card",
            "parameters": {"target_player": "Charlie"},
        },
        ["STEAL_CARD"],
    )

    user.notify_action(action, success=False, message="Invalid target")

    event = user.ai_manager.get_agent("Bob").recent_events[-1]
    assert event["type"] == "action_failed"
    assert "Invalid target" in event["message"]
    assert event["data"]["action_type"] == "STEAL_CARD"


def test_success_notification_with_missing_action_is_ignored():
    user = make_ai_user()

    user.notify_action(None, success=True, message="You stole a Wood!")

    assert user.ai_manager.get_agent("Bob").recent_events == []


def test_success_notification_does_not_repeat_public_say_outloud():
    user = make_ai_user()
    action = Action(
        ActionType.TRADE_PROPOSE,
        1,
        {
            "offer": {"wheat": 2},
            "request": {"brick": 1},
            "target_player": 0,
            "_ai_say_outloud": "Anyone have brick?",
            "_ai_say_outloud_public": True,
        },
    )

    user.notify_action(action, success=True)

    assert user.ai_manager.chat == []


def test_success_notification_marks_say_outloud_public_after_broadcast():
    user = make_ai_user()
    action = Action(
        ActionType.ROBBER_MOVE,
        1,
        {
            "tile_coords": [0, 0],
            "_ai_say_outloud": "Sorry, this tile is too strong.",
        },
    )

    user.notify_action(action, success=True)
    user.notify_action(action, success=True)

    assert user.ai_manager.chat == [
        {"from": "Bob", "message": "Sorry, this tile is too strong."}
    ]
    assert action.parameters["_ai_say_outloud_public"] is True


def test_failed_notification_with_missing_action_is_recorded():
    user = make_ai_user()

    user.notify_action(None, success=False, message="Unexpected failure")

    event = user.ai_manager.get_agent("Bob").recent_events[-1]
    assert event["type"] == "action_failed"
    assert "Unexpected failure" in event["message"]
    assert event["data"]["parameters"] == {}


def test_failed_action_feedback_notes_when_say_outloud_was_public():
    user = make_ai_user()
    action = Action(
        ActionType.TRADE_PROPOSE,
        1,
        {
            "offer": {"wheat": 2},
            "request": {"brick": 1},
            "target_player": 0,
            "_ai_say_outloud_public": True,
        },
    )

    user.notify_action(action, success=False, message="Target has no brick")

    event = user.ai_manager.get_agent("Bob").recent_events[-1]
    assert "already said publicly" in event["message"]
    assert "not said publicly" not in event["message"]


def test_confirmation_required_feedback_is_not_wrapped_as_generic_failure():
    user = make_ai_user()
    action = Action(
        ActionType.ROBBER_MOVE,
        1,
        {
            "tile_coords": [1, 1],
            "_ai_say_outloud": "This tile is too strong.",
        },
    )
    message = "ARE YOU SURE?\nYou chose robber_move {\"hex\": 5}."

    user.notify_action(action, success=False, message=message)

    event = user.ai_manager.get_agent("Bob").recent_events[-1]
    assert event["type"] == "action_failed"
    assert event["message"] == message
    assert event["data"]["confirmation_required"] is True
    assert user.ai_manager.chat == []


def test_action_processing_error_is_added_to_agent_events():
    user = make_ai_user()

    user.notify_action_processing_error("missing required parameters: ['target_player']")

    event = user.ai_manager.get_agent("Bob").recent_events[-1]
    assert event["type"] == "action_failed"
    assert "could not be processed" in event["message"]
    assert "target_player" in event["data"]["error"]


def test_wait_for_response_maps_to_end_turn_action():
    user = make_ai_user()

    action = user._decision_to_action(
        {"action_type": "wait_for_response", "parameters": {}},
        ["END_TURN"],
    )

    assert action.action_type == ActionType.END_TURN


def test_unknown_action_type_is_not_silently_converted_to_end_turn():
    user = make_ai_user()

    with pytest.raises(ValueError, match="Unknown action type: find_best_nodes"):
        user._decision_to_action(
            {
                "action_type": "find_best_nodes",
                "parameters": {"min_pips": 10},
            },
            ["PLACE_STARTING_SETTLEMENT"],
        )
