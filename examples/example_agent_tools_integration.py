"""
Example: Using Agent Tools with AIManager

This example shows how to integrate the 3 agent tools
with the AIManager for enhanced AI decision-making.
"""

from pycatan.ai import AIManager, AgentTools
import json


def example_1_tools_standalone():
    """Example 1: Using tools standalone (without AIManager)."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Using Tools Standalone")
    print("="*60)
    
    tools = AgentTools()
    
    # Scenario: AI has some resources and needs to decide what to build
    my_resources = {
        "wood": 2,
        "brick": 1,
        "wheat": 1,
        "sheep": 0,
        "ore": 1
    }
    
    print("\n📦 My Resources:", my_resources)
    
    # Check what I can afford
    print("\n💰 Can I afford a settlement?")
    result = tools.calculate_building_costs("settlement", my_resources)
    print(json.dumps(result, indent=2))
    
    print("\n💰 Can I afford a road?")
    result = tools.calculate_building_costs("road", my_resources)
    print(json.dumps(result, indent=2))
    
    print("\n💰 Can I afford a city?")
    result = tools.calculate_building_costs("city", my_resources)
    print(json.dumps(result, indent=2))


def example_2_evaluate_positions():
    """Example 2: Compare multiple settlement positions."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Evaluating Settlement Positions")
    print("="*60)
    
    tools = AgentTools()
    
    # Three potential positions to compare
    positions = [
        {
            "name": "Position A (coastal with harbor)",
            "tiles": [
                {"resource": "wood", "number": 9},
                {"resource": "wheat", "number": 10}
            ],
            "harbor": True,
            "harbor_type": "3:1"
        },
        {
            "name": "Position B (inland high-value)",
            "tiles": [
                {"resource": "wheat", "number": 6},
                {"resource": "wood", "number": 8},
                {"resource": "brick", "number": 5}
            ],
            "harbor": False
        },
        {
            "name": "Position C (ore-focused with harbor)",
            "tiles": [
                {"resource": "ore", "number": 6},
                {"resource": "ore", "number": 8},
                {"resource": "wheat", "number": 4}
            ],
            "harbor": True,
            "harbor_type": "ore"
        }
    ]
    
    print("\n📍 Comparing 3 positions:\n")
    
    results = []
    for pos in positions:
        result = tools.evaluate_node_value(
            pos["tiles"],
            pos["harbor"],
            pos.get("harbor_type")
        )
        results.append({
            "name": pos["name"],
            "score": result["overall_score"],
            "details": result
        })
        
        print(f"\n{pos['name']}:")
        print(f"  Score: {result['overall_score']}")
        print(f"  Pips: {result['total_pip_value']}")
        print(f"  Diversity: {result['resource_diversity']} resources")
        print(f"  Resources: {result['resources']}")
        if result['has_harbor']:
            print(f"  Harbor: {result.get('harbor_type', 'generic')}")
    
    # Find best position
    best = max(results, key=lambda x: x["score"])
    print(f"\n🏆 BEST POSITION: {best['name']} (Score: {best['score']})")


def example_3_winning_strategy():
    """Example 3: Plan path to victory."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Planning Path to Victory")
    print("="*60)
    
    tools = AgentTools()
    
    # Scenario: Mid-game situation
    print("\n📊 Current Situation:")
    print("  Victory Points: 7")
    print("  Settlements: 3")
    print("  Cities: 1")
    print("  Longest Road: Yes (2 VP)")
    print("  Largest Army: No")
    
    result = tools.check_winning_path(
        current_vp=7,
        settlements=3,
        cities=1,
        longest_road_owned=True,
        largest_army_owned=False
    )
    
    print(f"\n🎯 Need {result['vp_needed']} more VP to win!")
    
    print("\n📈 Paths to Victory:")
    for i, path in enumerate(result['paths_to_victory'], 1):
        print(f"  {i}. {path}")
    
    print("\n💡 Recommendations:")
    for rec in result['recommendations']:
        print(f"  • {rec}")


def example_4_integrated_decision():
    """Example 4: Complete decision-making scenario."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Integrated Decision Making")
    print("="*60)
    
    tools = AgentTools()
    
    # Full scenario: AI needs to decide its strategy
    game_state = {
        "my_resources": {
            "wood": 2,
            "brick": 2,
            "wheat": 3,
            "sheep": 1,
            "ore": 2
        },
        "my_vp": 6,
        "settlements": 3,
        "cities": 1,
        "longest_road": False,
        "largest_army": False
    }
    
    print("\n🎮 Current Game State:")
    print(f"  Resources: {game_state['my_resources']}")
    print(f"  VP: {game_state['my_vp']}")
    print(f"  Buildings: {game_state['settlements']} settlements, {game_state['cities']} cities")
    
    print("\n\n🤔 AI Decision Process:\n")
    
    # Step 1: Check winning path
    print("1️⃣ Checking winning strategy...")
    winning = tools.check_winning_path(
        game_state['my_vp'],
        game_state['settlements'],
        game_state['cities'],
        game_state['longest_road'],
        game_state['largest_army']
    )
    print(f"   Need {winning['vp_needed']} VP to win")
    print(f"   Top recommendation: {winning['recommendations'][0]}")
    
    # Step 2: Check if can afford recommended action
    print("\n2️⃣ Checking what I can afford...")
    
    # Cities seem like a good path
    city = tools.calculate_building_costs("city", game_state['my_resources'])
    print(f"   City: {'✅ Can afford!' if city['can_afford'] else '❌ Cannot afford'}")
    if not city['can_afford']:
        print(f"   Missing: {city['missing']}")
    
    # Check settlement
    settlement = tools.calculate_building_costs("settlement", game_state['my_resources'])
    print(f"   Settlement: {'✅ Can afford!' if settlement['can_afford'] else '❌ Cannot afford'}")
    
    # Check dev card
    dev = tools.calculate_building_costs("development_card", game_state['my_resources'])
    print(f"   Dev Card: {'✅ Can afford!' if dev['can_afford'] else '❌ Cannot afford'}")
    
    # Step 3: Make decision
    print("\n3️⃣ Final Decision:")
    if city['can_afford']:
        print("   🏛️ BUILD CITY - Gets 2 VP, moves me to 8 VP (only 2 VP from winning!)")
    elif settlement['can_afford']:
        print("   🏠 BUILD SETTLEMENT - Gets 1 VP, steady progress")
    elif dev['can_afford']:
        print("   🎴 BUY DEVELOPMENT CARD - Could get VP card or knights for Largest Army")
    else:
        print("   💰 TRADE or WAIT - Need to get more resources first")
    
    print("\n" + "="*60)


def example_5_tool_schema_for_llm():
    """Example 5: Get tool schemas for LLM integration."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Tool Schemas for LLM")
    print("="*60)
    
    tools = AgentTools()
    
    # Get schemas that can be sent to LLM APIs
    schemas = tools.get_tools_schema()
    
    print("\n📋 Generated schemas for 3 tools:")
    print(f"   Total tools: {len(schemas)}")
    
    for tool in schemas:
        print(f"\n   • {tool['name']}")
        print(f"     Description: {tool['description']}")
        print(f"     Parameters: {list(tool['parameters']['properties'].keys())}")
    
    print("\n💡 These schemas can be passed to:")
    print("   - OpenAI GPT-4 (function calling)")
    print("   - Anthropic Claude (tool use)")
    print("   - Google Gemini (function declarations)")
    print("   - Or included in system prompt as tool descriptions")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("  AGENT TOOLS INTEGRATION EXAMPLES")
    print("  Demonstrating 3 helper tools for AI agents")
    print("="*60)
    
    example_1_tools_standalone()
    example_2_evaluate_positions()
    example_3_winning_strategy()
    example_4_integrated_decision()
    example_5_tool_schema_for_llm()
    
    print("\n" + "="*60)
    print("  ✅ ALL EXAMPLES COMPLETED")
    print("="*60)
    print("\nNext steps:")
    print("  1. Integrate tools with AIManager.process_agent_turn()")
    print("  2. Update prompts to mention available tools")
    print("  3. Parse tool calls from LLM responses")
    print("  4. Log tool usage in AILogger")
    print()


if __name__ == "__main__":
    main()
