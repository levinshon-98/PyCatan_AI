from pycatan.ai.agent_tools import AgentTools


def test_inspect_hex_returns_tile_and_adjacent_buildings():
    game_state = {
        "meta": {"robber": 19},
        "H": [
            "",
            "W12",
            "S5",
            "W4",
            "S8",
            "B6",
            "W3",
        ],
        "N": [
            None,
            [[2], [1]],
            [[1, 3], [1]],
            [[2], [2, 1]],
            [[5], [2]],
            [[4, 6, 13], [3, 2]],
            [[5, 7], [3]],
            [[6], [3]],
            [[9], [4]],
            [[8, 10], [4, 1]],
            [[9, 11, 20], [5, 4, 1]],
            [[10, 12, 3], [5, 2, 1]],
            [[11, 13, 22], [6, 5, 2]],
            [[12, 14, 5], [6, 3, 2]],
            [[13], [7, 6, 3]],
            [[16], [7, 3]],
            [[15], [7]],
            [[18], [8]],
            [[17, 19, 8], [8, 4]],
            [[18, 20], [9, 8, 4]],
            [[19, 21, 10], [9, 5, 4]],
            [[20, 22], [10, 9, 5]],
            [[21], [10, 6, 5]],
        ],
        "state": {
            "bld": [[12, "Jimmy", "S"], [20, "Gemma", "S"]],
            "rds": [],
        },
    }

    result = AgentTools(game_state).inspect_hex(5, reasoning="verify robber target")

    assert result["exists"] is True
    assert result["resource"] == "Brick"
    assert result["number"] == 6
    assert result["pips"] == 5
    assert result["robber_here"] is False
    assert result["adjacent_nodes"] == [10, 11, 12, 20, 21, 22]
    assert result["adjacent_buildings"] == [
        {"node_id": 12, "owner": "Jimmy", "building_type": "settlement"},
        {"node_id": 20, "owner": "Gemma", "building_type": "settlement"},
    ]
    assert result["llm_reasoning"] == "verify robber target"


def test_inspect_hex_is_registered_and_dispatchable():
    tools = AgentTools({"H": ["", "D"], "N": [None], "state": {}})

    schema_names = [tool["name"] for tool in tools.get_tools_schema()]
    assert "inspect_hex" in schema_names

    result = tools.execute_tool(
        "inspect_hex",
        {"hex_id": 1, "reasoning": "check desert"},
    )
    assert result["resource"] == "Desert"
    assert result["number"] == 0
