"""
Test script for Agent Tools

This script demonstrates how the 3 agent tools work and validates
that they provide useful information for the AI.
"""

from pycatan.ai.agent_tools import AgentTools
import json


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_calculate_building_costs():
    """Test the building costs calculator."""
    print_section("TOOL 1: Calculate Building Costs")
    
    tools = AgentTools()
    
    # Test 1: Can afford settlement
    print("Test 1: Check if we can build a settlement")
    print("Resources: wood=1, brick=1, wheat=1, sheep=1")
    result = tools.calculate_building_costs(
        "settlement",
        {"wood": 1, "brick": 1, "wheat": 1, "sheep": 1}
    )
    print(json.dumps(result, indent=2))
    
    # Test 2: Missing resources
    print("\n\nTest 2: Missing brick for settlement")
    print("Resources: wood=1, brick=0, wheat=2, sheep=1")
    result = tools.calculate_building_costs(
        "settlement",
        {"wood": 1, "brick": 0, "wheat": 2, "sheep": 1}
    )
    print(json.dumps(result, indent=2))
    
    # Test 3: City costs
    print("\n\nTest 3: Check city costs")
    print("Resources: wheat=3, ore=2")
    result = tools.calculate_building_costs(
        "city",
        {"wheat": 3, "ore": 2}
    )
    print(json.dumps(result, indent=2))
    
    # Test 4: Development card
    print("\n\nTest 4: Can afford development card")
    print("Resources: wheat=1, sheep=1, ore=1")
    result = tools.calculate_building_costs(
        "development_card",
        {"wheat": 1, "sheep": 1, "ore": 1}
    )
    print(json.dumps(result, indent=2))


def test_evaluate_node_value():
    """Test the node value evaluator."""
    print_section("TOOL 2: Evaluate Node Value")
    
    tools = AgentTools()
    
    # Test 1: Excellent position (6, 8, 5)
    print("Test 1: Excellent position - diverse and high probability")
    print("Tiles: wheat(6), wood(8), brick(5)")
    result = tools.evaluate_node_value([
        {"resource": "wheat", "number": 6},
        {"resource": "wood", "number": 8},
        {"resource": "brick", "number": 5}
    ])
    print(json.dumps(result, indent=2))
    
    # Test 2: Poor position (2, 12)
    print("\n\nTest 2: Poor position - low probability numbers")
    print("Tiles: ore(2), sheep(12)")
    result = tools.evaluate_node_value([
        {"resource": "ore", "number": 2},
        {"resource": "sheep", "number": 12}
    ])
    print(json.dumps(result, indent=2))
    
    # Test 3: With harbor
    print("\n\nTest 3: Decent position with 3:1 harbor")
    print("Tiles: wood(9), wheat(10), Harbor: 3:1")
    result = tools.evaluate_node_value(
        [
            {"resource": "wood", "number": 9},
            {"resource": "wheat", "number": 10}
        ],
        include_harbor=True,
        harbor_type="3:1"
    )
    print(json.dumps(result, indent=2))
    
    # Test 4: With specialized harbor
    print("\n\nTest 4: Ore heavy position with ore harbor")
    print("Tiles: ore(6), ore(8), wheat(4), Harbor: ore")
    result = tools.evaluate_node_value(
        [
            {"resource": "ore", "number": 6},
            {"resource": "ore", "number": 8},
            {"resource": "wheat", "number": 4}
        ],
        include_harbor=True,
        harbor_type="ore"
    )
    print(json.dumps(result, indent=2))


def test_check_winning_path():
    """Test the winning path analyzer."""
    print_section("TOOL 3: Check Winning Path")
    
    tools = AgentTools()
    
    # Test 1: Close to winning
    print("Test 1: Close to winning (8 VP)")
    print("VP: 8, Settlements: 2, Cities: 2, Longest Road: Yes")
    result = tools.check_winning_path(
        current_vp=8,
        settlements=2,
        cities=2,
        longest_road_owned=True
    )
    print(json.dumps(result, indent=2))
    
    # Test 2: Early game
    print("\n\nTest 2: Early game (4 VP)")
    print("VP: 4, Settlements: 4, Cities: 0")
    result = tools.check_winning_path(
        current_vp=4,
        settlements=4,
        cities=0
    )
    print(json.dumps(result, indent=2))
    
    # Test 3: With special cards
    print("\n\nTest 3: Mid-game with Largest Army")
    print("VP: 6, Settlements: 3, Cities: 1, Largest Army: Yes")
    result = tools.check_winning_path(
        current_vp=6,
        settlements=3,
        cities=1,
        largest_army_owned=True
    )
    print(json.dumps(result, indent=2))
    
    # Test 4: Already won
    print("\n\nTest 4: Already won!")
    print("VP: 10, Settlements: 2, Cities: 3, Both special cards")
    result = tools.check_winning_path(
        current_vp=10,
        settlements=2,
        cities=3,
        longest_road_owned=True,
        largest_army_owned=True
    )
    print(json.dumps(result, indent=2))


def test_tool_schema():
    """Test tool schema generation for LLM."""
    print_section("Tool Schema for LLM Function Calling")
    
    tools = AgentTools()
    schema = tools.get_tools_schema()
    
    print("Generated schema for 3 tools:")
    print(json.dumps(schema, indent=2))


def test_tool_dispatcher():
    """Test the tool dispatcher/executor."""
    print_section("Tool Dispatcher/Executor")
    
    tools = AgentTools()
    
    print("Test: Execute tool by name")
    print("Tool: calculate_building_costs")
    print("Parameters: building_type='settlement', current_resources={'wood': 1, 'brick': 1, 'wheat': 0, 'sheep': 1}")
    
    result = tools.execute_tool(
        "calculate_building_costs",
        {
            "building_type": "settlement",
            "current_resources": {"wood": 1, "brick": 1, "wheat": 0, "sheep": 1}
        }
    )
    print(json.dumps(result, indent=2))


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  AGENT TOOLS - TEST SUITE")
    print("  Testing 3 helper tools for LLM AI Agents")
    print("="*60)
    
    try:
        test_calculate_building_costs()
        test_evaluate_node_value()
        test_check_winning_path()
        test_tool_schema()
        test_tool_dispatcher()
        
        print("\n" + "="*60)
        print("  ✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
