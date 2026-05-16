"""Relationship context compaction tests."""

import json

from pycatan.ai.agent_state import AgentState
from pycatan.ai.config import AIConfig
from pycatan.ai.llm_client import LLMResponse
from pycatan.ai.memory_compactor import MemoryCompactor
from pycatan.ai.schemas import (
    ResponseType,
    SchemaVersion,
    get_schema_description,
    get_schema_for_response_type,
)


class _FakeLLMClient:
    def generate(self, *args, **kwargs):
        return LLMResponse(
            success=True,
            content=json.dumps({
                "compacted_memory": "Prefer ore expansion; Shon may be racing city upgrades.",
                "recent_notes_to_keep": ["Recent note A", "Recent note B"],
                "relationship_updates": [
                    "Shon refused a fair trade, making future promises less credible.",
                ],
                "discarded_as_irrelevant": [],
            }),
        )


def test_player_response_schemas_do_not_ask_for_relationship_update():
    for version in [SchemaVersion.V1, SchemaVersion.V2]:
        for response_type in [ResponseType.ACTIVE_TURN, ResponseType.OBSERVING]:
            schema = get_schema_for_response_type(response_type, version)
            assert "relationship_update" not in schema["properties"]
            assert "relationship_update" not in schema["propertyOrdering"]
            assert "relationship_update" not in get_schema_description(response_type, version)


def test_memory_compactor_extracts_relationship_updates():
    agent = AgentState(player_name="Hadar", player_id=0, player_color="Red")
    agent.memory_history = [
        {"note": "Shon refused my fair trade after promising to help."},
        {"note": "Recent note A"},
        {"note": "Recent note B"},
    ]

    result = MemoryCompactor(AIConfig()).compact(
        agent=agent,
        game_state={
            "meta": {"curr": "Hadar", "phase": "NORMAL_PLAY"},
            "H": [],
            "N": [],
            "state": {"bld": [], "rds": []},
            "players": {"Hadar": {"vp": 0, "res": {}}, "Shon": {"vp": 0, "res": {}}},
        },
        chat_history=[
            {"from": "Shon", "message": "I'll help next time, promise."},
        ],
        llm_client=_FakeLLMClient(),
    )

    assert result is not None
    assert result["relationship_updates"] == [
        "Shon refused a fair trade, making future promises less credible.",
    ]
    assert "relationship_updates" in result["prompt"]["output_requirements"]["schema"]
    assert "existing_relationship_updates" in result["prompt"]["memory_input"]


def test_memory_compactor_filters_repeated_relationship_updates():
    compactor = MemoryCompactor(AIConfig())

    updates = compactor._clean_relationship_updates(
        [
            "Shon refused a fair trade.",
            "Shon refused a fair trade.",
            "Hadar backed my warning.",
        ],
        [{"note": "Shon refused a fair trade."}],
    )

    assert updates == ["Hadar backed my warning."]
