"""
Test Script for Optimized Prompt System
-----------------------------------------
Verifies that the updated prompt system works with the new optimized state format.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pycatan.ai.state_filter import StateFilter, PlayerPerspective
from pycatan.ai.prompt_manager import PromptManager

def load_optimized_state():
    """Load the optimized state from file."""
    state_file = Path('examples/ai_testing/my_games/current_state_optimized.txt')
    
    if not state_file.exists():
        # Try sample states folder
        state_file = Path('examples/ai_testing/sample_states/captured_game_optimized.txt')
        
    if not state_file.exists():
        print("❌ Optimized state file not found!")
        print(f"   Expected: {state_file}")
        return None
    
    with open(state_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Find "JSON:" marker and extract JSON after it
    json_marker = content.find('JSON:')
    if json_marker != -1:
        json_start = content.find('{', json_marker)
    else:
        # No marker, just find first {
        json_start = content.find('{')
        
    if json_start == -1:
        print("❌ Could not find JSON in file!")
        return None
    
    json_str = content[json_start:].strip()
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"   First 200 chars: {json_str[:200]}")
        return None


def test_state_filter():
    """Test the state filter with optimized format."""
    print("\n" + "="*80)
    print("TEST 1: State Filter with Optimized Format")
    print("="*80)
    
    # Load optimized state
    raw_state = load_optimized_state()
    if not raw_state:
        return False
    
    print("\n✓ Loaded optimized state")
    print(f"  Players: {list(raw_state.get('players', {}).keys())}")
    print(f"  Phase: {raw_state.get('meta', {}).get('phase')}")
    
    # Create filter for player 'a'
    perspective = PlayerPerspective(
        player_num=0,
        player_name="a",
        player_color="Blue"
    )
    state_filter = StateFilter(perspective)
    
    print("\n✓ Created state filter for player 'a'")
    
    # Filter the state
    try:
        filtered = state_filter.filter_game_state(raw_state)
        print("\n✓ Successfully filtered state!")
        
        # Show what we got
        print(f"\nFiltered sections:")
        for key in filtered.keys():
            print(f"  - {key}")
        
        # Show my info
        my_info = filtered.get("my_private_info", {})
        print(f"\nMy private info:")
        print(f"  Victory Points: {my_info.get('victory_points')}")
        print(f"  Resources: {my_info.get('resources')}")
        print(f"  Has Longest Road: {my_info.get('has_longest_road')}")
        
        # Show other players
        others = filtered.get("other_players", [])
        print(f"\nOther players: {len(others)}")
        for player in others:
            print(f"  - {player.get('name')}: {player.get('victory_points')} VP, {player.get('resource_count')} cards")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error filtering state: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_generation():
    """Test full prompt generation."""
    print("\n" + "="*80)
    print("TEST 2: Full Prompt Generation")
    print("="*80)
    
    # Load optimized state
    raw_state = load_optimized_state()
    if not raw_state:
        return False
    
    # Create prompt manager
    prompt_manager = PromptManager()
    
    print("\n✓ Created prompt manager")
    
    # Generate prompt
    try:
        prompt = prompt_manager.create_prompt(
            player_num=0,
            player_name="a",
            player_color="Blue",
            game_state=raw_state,
            what_happened="Game started. It's your turn to place your first settlement.",
            available_actions=[
                {
                    "action": "place_settlement",
                    "description": "Place your starting settlement",
                    "example_parameters": {"node_id": 20}
                }
            ],
            custom_instructions="You are a strategic Catan player."
        )
        
        print("\n✓ Successfully generated prompt!")
        
        # Show prompt structure
        print(f"\nPrompt sections:")
        for key in prompt.keys():
            print(f"  - {key}")
        
        # Show legend
        if "game_state_legend" in prompt:
            print("\n✓ Legend included in prompt")
            legend = prompt["game_state_legend"]
            print(f"  Legend length: {len(legend)} characters")
        
        # Show game state keys
        game_state = prompt.get("game_state", {})
        print(f"\nGame state sections:")
        for key in game_state.keys():
            print(f"  - {key}")
        
        # Check board state
        board = game_state.get("board_state", {})
        print(f"\nBoard state:")
        print(f"  H array length: {len(board.get('H', []))}")
        print(f"  N array length: {len(board.get('N', []))}")
        print(f"  Buildings: {len(board.get('buildings', []))}")
        print(f"  Roads: {len(board.get('roads', []))}")
        
        # Save prompt for inspection
        output_file = Path('examples/ai_testing/my_games/test_prompt_output.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(prompt, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Saved full prompt to: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error generating prompt: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("TESTING OPTIMIZED PROMPT SYSTEM")
    print("="*80)
    
    # Run tests
    test1_passed = test_state_filter()
    test2_passed = test_prompt_generation()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"State Filter:     {'✓ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Prompt Generation: {'✓ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED! The optimized prompt system is working!")
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
    
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
