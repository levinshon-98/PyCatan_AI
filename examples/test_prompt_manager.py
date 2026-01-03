"""
Test Prompt Management System

This script tests the prompt generation pipeline:
1. Load a sample game state
2. Create a prompt manager
3. Generate prompts for different scenarios
4. Verify the output structure
"""

import json
import sys
from pathlib import Path
from pprint import pprint

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pycatan.ai.config import AIConfig
from pycatan.ai.prompt_manager import PromptManager
from pycatan.ai.prompt_templates import ActionTemplates


def load_sample_game_state():
    """Load the sample captured game state."""
    sample_path = project_root / "examples" / "ai_testing" / "sample_states" / "captured_game.json"
    
    if not sample_path.exists():
        print(f"✗ Sample game state not found: {sample_path}")
        return None
    
    with open(sample_path, 'r') as f:
        return json.load(f)


def test_basic_prompt_generation():
    """Test 1: Generate a basic prompt."""
    print("\n" + "="*80)
    print("TEST 1: Basic Prompt Generation")
    print("="*80)
    
    # Create prompt manager
    config = AIConfig()
    manager = PromptManager(config)
    
    # Load game state
    game_state = load_sample_game_state()
    if not game_state:
        return False
    
    print(f"✓ Loaded game state with {len(game_state.get('hexes', []))} hexes")
    
    # Create a simple prompt
    prompt = manager.create_prompt(
        player_num=1,
        player_name="Test Agent",
        player_color="Blue",
        game_state=game_state,
        what_happened="The game has started. Place your starting settlement.",
        available_actions=ActionTemplates.get_actions_for_phase("setup")
    )
    
    print("\n✓ Generated prompt with sections:")
    for section in prompt.keys():
        print(f"  - {section}")
    
    # Verify structure
    assert "meta_data" in prompt, "Missing meta_data section"
    assert "task_context" in prompt, "Missing task_context section"
    assert "game_state" in prompt, "Missing game_state section"
    assert "constraints" in prompt, "Missing constraints section"
    
    print("\n✓ Prompt structure is valid")
    
    return True


def test_filtered_game_state():
    """Test 2: Verify game state filtering."""
    print("\n" + "="*80)
    print("TEST 2: Game State Filtering")
    print("="*80)
    
    config = AIConfig()
    manager = PromptManager(config)
    
    game_state = load_sample_game_state()
    if not game_state:
        return False
    
    # Generate prompt
    prompt = manager.create_prompt(
        player_num=1,
        player_name="Test Agent",
        player_color="Blue",
        game_state=game_state,
        what_happened="Your turn to play."
    )
    
    # Check filtered state structure
    filtered_state = prompt["game_state"]
    
    print("\n✓ Filtered game state contains:")
    for key in filtered_state.keys():
        print(f"  - {key}")
    
    # Verify key sections exist
    assert "my_private_info" in filtered_state, "Missing my_private_info"
    assert "board_state" in filtered_state, "Missing board_state"
    assert "other_players" in filtered_state, "Missing other_players"
    assert "strategic_context" in filtered_state, "Missing strategic_context"
    
    print("\n✓ My private info:")
    pprint(filtered_state["my_private_info"], width=100, compact=True)
    
    print("\n✓ Strategic context:")
    pprint(filtered_state["strategic_context"], width=100, compact=True)
    
    return True


def test_action_filtering():
    """Test 3: Filter actions by resources."""
    print("\n" + "="*80)
    print("TEST 3: Action Filtering by Resources")
    print("="*80)
    
    manager = PromptManager()
    
    # Get all actions
    all_actions = ActionTemplates.get_all_actions()
    print(f"\n✓ Total available actions: {len(all_actions)}")
    
    # Test with different resource scenarios
    scenarios = [
        {
            "name": "Poor (no resources)",
            "resources": {"wood": 0, "brick": 0, "sheep": 0, "wheat": 0, "ore": 0}
        },
        {
            "name": "Can build road",
            "resources": {"wood": 1, "brick": 1, "sheep": 0, "wheat": 0, "ore": 0}
        },
        {
            "name": "Can build settlement",
            "resources": {"wood": 1, "brick": 1, "sheep": 1, "wheat": 1, "ore": 0}
        },
        {
            "name": "Rich (can do anything)",
            "resources": {"wood": 5, "brick": 5, "sheep": 5, "wheat": 5, "ore": 5}
        }
    ]
    
    for scenario in scenarios:
        affordable = manager.filter_actions_by_resources(all_actions, scenario["resources"])
        print(f"\n{scenario['name']}: {len(affordable)} affordable actions")
        for action in affordable:
            if action["type"] in ["BUILD_ROAD", "BUILD_SETTLEMENT", "BUILD_CITY", "BUY_DEV_CARD"]:
                print(f"  - {action['type']}")
    
    return True


def test_chat_context():
    """Test 4: Include chat history in prompt."""
    print("\n" + "="*80)
    print("TEST 4: Chat History Integration")
    print("="*80)
    
    manager = PromptManager()
    game_state = load_sample_game_state()
    
    if not game_state:
        return False
    
    # Add chat history
    chat_history = [
        {"sender": "Red", "content": "I need wood desperately!"},
        {"sender": "Green", "content": "I'll trade you wood for ore."},
        {"sender": "Red", "content": "Deal! I'll give you 2 ore for 2 wood."}
    ]
    
    prompt = manager.create_prompt(
        player_num=1,
        player_name="Test Agent",
        player_color="Blue",
        game_state=game_state,
        what_happened="Red and Green are negotiating a trade.",
        chat_history=chat_history
    )
    
    # Check social context
    assert "social_context" in prompt, "Missing social_context"
    
    print("\n✓ Social context included:")
    pprint(prompt["social_context"], width=100)
    
    return True


def test_custom_instructions():
    """Test 5: Custom instructions per agent."""
    print("\n" + "="*80)
    print("TEST 5: Custom Agent Instructions")
    print("="*80)
    
    config = AIConfig()
    config.agent.custom_instructions = "You are an aggressive trader. Always seek to maximize trades."
    
    manager = PromptManager(config)
    game_state = load_sample_game_state()
    
    if not game_state:
        return False
    
    prompt = manager.create_prompt(
        player_num=1,
        player_name="Aggressive Trader",
        player_color="Blue",
        game_state=game_state,
        what_happened="Your turn."
    )
    
    print("\n✓ Meta data with custom instructions:")
    pprint(prompt["meta_data"], width=100)
    
    assert "aggressive trader" in prompt["meta_data"]["role"].lower()
    print("\n✓ Custom instructions applied successfully")
    
    return True


def test_prompt_json_serialization():
    """Test 6: Ensure prompt can be serialized to JSON."""
    print("\n" + "="*80)
    print("TEST 6: JSON Serialization")
    print("="*80)
    
    manager = PromptManager()
    game_state = load_sample_game_state()
    
    if not game_state:
        return False
    
    prompt = manager.create_prompt(
        player_num=1,
        player_name="Test Agent",
        player_color="Blue",
        game_state=game_state,
        what_happened="Test event.",
        available_actions=ActionTemplates.get_all_actions()
    )
    
    try:
        # Try to serialize to JSON
        json_str = json.dumps(prompt, indent=2)
        print(f"\n✓ Prompt serialized successfully ({len(json_str)} characters)")
        
        # Try to deserialize
        reconstructed = json.loads(json_str)
        print("✓ Prompt deserialized successfully")
        
        # Save to file for inspection
        output_path = project_root / "logs" / "sample_prompt.json"
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(json_str)
        
        print(f"✓ Saved sample prompt to: {output_path}")
        
    except Exception as e:
        print(f"✗ Serialization failed: {e}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("🧪 PROMPT MANAGEMENT SYSTEM - TEST SUITE")
    print("="*80)
    
    tests = [
        ("Basic Prompt Generation", test_basic_prompt_generation),
        ("Game State Filtering", test_filtered_game_state),
        ("Action Filtering", test_action_filtering),
        ("Chat History Integration", test_chat_context),
        ("Custom Instructions", test_custom_instructions),
        ("JSON Serialization", test_prompt_json_serialization)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        print("\n📋 Next Steps:")
        print("  - Check logs/sample_prompt.json to see generated prompt")
        print("  - Ready to proceed to Response Parser (Phase 1.3)")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
