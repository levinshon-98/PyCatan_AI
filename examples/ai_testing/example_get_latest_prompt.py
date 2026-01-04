"""
Example: Get Latest Prompt for a Player
-----------------------------------------
This script demonstrates how to retrieve the most recent prompt
for a specific player from the current game session.

Usage:
    python examples/ai_testing/example_get_latest_prompt.py [player_name]
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.ai_testing.generate_prompts_from_state import (
    get_latest_prompt,
    get_current_session_dir
)


def main():
    """Main entry point."""
    print("\n" + "="*80)
    print("📨 GET LATEST PROMPT FOR PLAYER")
    print("="*80 + "\n")
    
    # Get player name from command line or use default
    if len(sys.argv) > 1:
        player_name = sys.argv[1]
    else:
        # Try to detect from current session
        session_dir = get_current_session_dir()
        if session_dir:
            # List available players
            players = [d.name for d in session_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
            if players:
                print(f"Available players: {', '.join(players)}")
                player_name = players[0]
                print(f"Using first player: {player_name}\n")
            else:
                print("❌ No players found in session!")
                print("\n💡 Usage: python example_get_latest_prompt.py [player_name]")
                return
        else:
            print("❌ No active session found!")
            print("\n💡 Start a game first:")
            print("   python examples/ai_testing/play_and_capture.py")
            return
    
    # Get the latest prompt
    print(f"🔍 Looking for latest prompt for player: {player_name}")
    prompt_file, prompt_data = get_latest_prompt(player_name)
    
    if prompt_file is None:
        print(f"\n❌ No prompts found for player '{player_name}'")
        return
    
    print(f"\n✅ Found latest prompt!")
    print(f"📁 File: {prompt_file}")
    print(f"📊 Size: {prompt_file.stat().st_size:,} bytes")
    
    # Show some info about the prompt
    if prompt_data:
        print("\n" + "-"*80)
        print("📋 PROMPT SUMMARY")
        print("-"*80)
        
        # Check structure
        if 'prompt' in prompt_data:
            prompt = prompt_data['prompt']
            
            # Show game state info if available
            if 'game_state' in prompt:
                game_state = prompt['game_state']
                if 'meta' in game_state:
                    meta = game_state['meta']
                    print(f"Turn: {meta.get('turn', '?')}")
                    print(f"Phase: {meta.get('phase', '?')}")
                    print(f"Current Player: {meta.get('curr', '?')}")
                
                if 'players' in game_state:
                    players = game_state['players']
                    print(f"Players in game: {', '.join(players.keys())}")
            
            # Show task context
            if 'task_context' in prompt:
                task = prompt['task_context']
                what_happened = task.get('what_just_happened', '')
                if what_happened:
                    print(f"\nWhat happened: {what_happened[:100]}...")
        
        print("\n" + "-"*80)
        
        # Show how to use this prompt
        print("\n💡 TO USE THIS PROMPT:")
        print("   1. Read the JSON file:")
        print(f"      with open('{prompt_file}', 'r') as f:")
        print(f"          llm_request = json.load(f)")
        print("   ")
        print("   2. Send to LLM:")
        print("      response = llm_client.send(llm_request)")
        print("   ")
        print("   3. The response will be in the format specified in 'response_schema'")
    
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    main()
