"""
Generate AI Prompts from Current Game State
--------------------------------------------
Reads the current optimized game state and generates a complete JSON prompt
for each player in the exact format to send to LLM, including response schema.

Run this script DURING a game to see what prompts each AI would receive.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pycatan.ai.prompt_manager import PromptManager
from pycatan.ai.config import AIConfig
from pycatan.ai.prompt_templates import get_response_schema


def load_current_state():
    """Load the current optimized game state."""
    state_file = Path('examples/ai_testing/my_games/current_state_optimized.txt')
    
    if not state_file.exists():
        print("❌ No current game state found!")
        print(f"   Expected: {state_file}")
        print("\n💡 Start a game first:")
        print("   python examples/ai_testing/play_and_capture.py")
        return None
    
    with open(state_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find JSON after "JSON:" marker
    json_marker = content.find('JSON:')
    if json_marker != -1:
        json_start = content.find('{', json_marker)
    else:
        json_start = content.find('{')
    
    if json_start == -1:
        print("❌ Could not find JSON in state file!")
        return None
    
    json_str = content[json_start:].strip()
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return None


def get_player_colors():
    """Get color mappings for players (hardcoded for now)."""
    return {
        "a": "Red",
        "b": "Blue", 
        "c": "White",
        "d": "Orange"
    }


def generate_prompt_for_player(player_name, game_state, prompt_manager):
    """
    Generate a complete prompt for a specific player.
    
    Args:
        player_name: Name of the player (e.g., "a", "b", "c")
        game_state: Current game state (optimized format)
        prompt_manager: PromptManager instance
        
    Returns:
        Complete prompt dictionary
    """
    colors = get_player_colors()
    player_color = colors.get(player_name, "Unknown")
    
    # Get player index (0-based)
    players = game_state.get("players", {})
    player_names = list(players.keys())
    player_num = player_names.index(player_name) if player_name in player_names else 0
    
    # Get current phase and determine what action is needed
    meta = game_state.get("meta", {})
    phase = meta.get("phase", "UNKNOWN")
    current_player = meta.get("curr")
    
    # Determine what happened and what to do
    if phase == "SETUP_FIRST_ROUND":
        if current_player == player_name:
            what_happened = "It's your turn in the setup phase. Place your first settlement."
            available_actions = [
                {
                    "action": "place_settlement",
                    "description": "Place your starting settlement on an available node",
                    "example_parameters": {
                        "location": "20"
                    }
                }
            ]
        else:
            what_happened = f"It's {current_player}'s turn to place their first settlement."
            available_actions = None
    elif phase == "SETUP_SECOND_ROUND":
        if current_player == player_name:
            what_happened = "It's your turn in the second setup round. Place your second settlement."
            available_actions = [
                {
                    "action": "place_settlement",
                    "description": "Place your second starting settlement",
                    "example_parameters": {
                        "location": "25"
                    }
                }
            ]
        else:
            what_happened = f"It's {current_player}'s turn to place their second settlement."
            available_actions = None
    else:
        if current_player == player_name:
            what_happened = "It's your turn. Roll the dice to begin."
            available_actions = [
                {
                    "action": "roll_dice",
                    "description": "Roll the dice to produce resources",
                    "example_parameters": {}
                },
                {
                    "action": "build_road",
                    "description": "Build a road on a specific edge",
                    "example_parameters": {"location": "12"}
                },
                {
                    "action": "build_settlement",
                    "description": "Build a settlement on a specific node",
                    "example_parameters": {"location": "45"}
                },
                {
                    "action": "buy_development_card",
                    "description": "Buy a development card if you have resources",
                    "example_parameters": {}
                },
                {
                    "action": "wait_for_response",
                    "description": "Do nothing on the board, just chat or wait for trade responses",
                    "example_parameters": {}
                },
                {
                    "action": "end_turn",
                    "description": "End your turn when done",
                    "example_parameters": {}
                }
            ]
        else:
            what_happened = f"It's {current_player}'s turn."
            available_actions = None
    
    # Generate the prompt
    prompt = prompt_manager.create_prompt(
        player_num=player_num,
        player_name=player_name,
        player_color=player_color,
        game_state=game_state,
        what_happened=what_happened,
        available_actions=available_actions,
        custom_instructions=f"You are player '{player_name}' ({player_color}). Play strategically to win."
    )
    
    return prompt


def save_prompt_to_file(player_name, prompt, output_dir):
    """
    Save a prompt as JSON file with response schema header.
    
    Args:
        player_name: Name of the player
        prompt: Complete prompt dictionary
        output_dir: Directory to save to
    """
    output_file = output_dir / f"prompt_player_{player_name}.json"
    
    # Create complete LLM request with schema + prompt
    llm_request = {
        "response_schema": get_response_schema(),
        "system_instruction": "You are an expert Settlers of Catan player. Analyze the game state carefully and respond with your chosen action in the exact JSON format specified in response_schema.",
        "prompt": prompt
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(llm_request, f, indent=2, ensure_ascii=False)
    
    # Also create a human-readable version
    txt_file = output_dir / f"prompt_player_{player_name}.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write(f"AI AGENT PROMPT - PLAYER {player_name.upper()}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        
        f.write("📋 RESPONSE SCHEMA (Expected LLM Output Format)\n")
        f.write("-" * 80 + "\n")
        f.write(json.dumps(llm_request["response_schema"], indent=2, ensure_ascii=False))
        f.write("\n\n")
        
        f.write("="*80 + "\n")
        f.write("📨 PROMPT TO SEND TO LLM\n")
        f.write("="*80 + "\n\n")
        
        f.write(json.dumps(prompt, indent=2, ensure_ascii=False))
        f.write("\n\n")
        
        f.write("="*80 + "\n")
        f.write("END OF PROMPT\n")
        f.write("="*80 + "\n")


def main():
    """Main entry point - generate prompts for all players."""
    print("\n" + "="*80)
    print("🎮 AI PROMPT GENERATOR - Real Game State")
    print("="*80 + "\n")
    
    # Load current game state
    print("📖 Loading current game state...")
    game_state = load_current_state()
    
    if not game_state:
        return
    
    # Show basic info
    meta = game_state.get("meta", {})
    players = game_state.get("players", {})
    
    print(f"✓ Loaded game state")
    print(f"  Phase: {meta.get('phase')}")
    print(f"  Current Player: {meta.get('curr')}")
    print(f"  Players: {', '.join(players.keys())}")
    print()
    
    # Create prompt manager
    config = AIConfig()
    prompt_manager = PromptManager(config)
    
    # Create output directory
    output_dir = Path('examples/ai_testing/my_games/prompts')
    output_dir.mkdir(exist_ok=True, parents=True)
    
    print("📝 Generating prompts for each player...\n")
    
    # Generate prompt for each player
    for player_name in players.keys():
        print(f"  ⚙️  Generating prompt for player '{player_name}'...")
        
        try:
            prompt = generate_prompt_for_player(player_name, game_state, prompt_manager)
            save_prompt_to_file(player_name, prompt, output_dir)
            
            json_file = output_dir / f"prompt_player_{player_name}.json"
            txt_file = output_dir / f"prompt_player_{player_name}.txt"
            print(f"     ✓ JSON: {json_file}")
            print(f"     ✓ TXT:  {txt_file}")
            
        except Exception as e:
            print(f"     ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("✅ DONE! Prompts generated successfully")
    print("="*80)
    print(f"\n📁 Output location: {output_dir.absolute()}")
    print(f"\n💡 Files created per player:")
    print(f"   - prompt_player_X.json (Send this to LLM)")
    print(f"   - prompt_player_X.txt  (Human-readable)")
    
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    main()
