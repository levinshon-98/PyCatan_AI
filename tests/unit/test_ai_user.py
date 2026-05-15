"""Unit tests for AIUser action translation."""

from dataclasses import dataclass

import pytest

from pycatan.ai.ai_user import AIUser
from pycatan.management.actions import ActionType


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

    def register_agent(self, name, user_id, color):
        self.agents[name] = DummyAgent(name, user_id, color)

    def get_agent(self, name):
        return self.agents.get(name)


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
