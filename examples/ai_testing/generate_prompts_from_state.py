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
from pycatan.ai.prompt_templates import get_response_schema, get_spectator_response_schema


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


def load_full_state():
    """Load the full (non-optimized) game state with allowed_actions."""
    state_file = Path('examples/ai_testing/my_games/current_state.json')
    
    if not state_file.exists():
        print("❌ No current game state found!")
        return None
    
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('state', {})
    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ Error loading state: {e}")
        return None


def get_current_session_dir():
    """
    Get the current active session directory.
    
    Returns:
        Path object to session directory, or None if not found
    """
    session_file = Path('examples/ai_testing/my_games/current_session.txt')
    
    print(f"  🔍 Looking for session file: {session_file.absolute()}")
    
    if session_file.exists():
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                session_path = f.read().strip()
                session_dir = Path(session_path)
                print(f"  📂 Found session path: {session_dir}")
                if session_dir.exists():
                    print(f"  ✅ Session directory exists!")
                    return session_dir
                else:
                    print(f"  ⚠️  Session directory doesn't exist yet")
        except Exception as e:
            print(f"⚠️ Error reading session file: {e}")
    else:
        print(f"  ⚠️  Session file not found")
    
    return None


def generate_what_happened_message(full_state, optimized_state, current_player, for_spectator=False):
    """
    Generate a contextual message about what just happened in the game.
    Uses the actual game state to create specific descriptions.
    
    Args:
        full_state: Full game state with buildings, roads, etc.
        optimized_state: Optimized state with player info
        current_player: Name of player receiving this message
        for_spectator: If True, generate message for non-active player (3rd person)
        
    Returns:
        String describing what happened
    """
    if not full_state:
        return "It's your turn." if not for_spectator else "Waiting for other players."
    
    # Get phase info
    phase = full_state.get('current_phase', 'UNKNOWN')
    
    # Get buildings and roads from state
    settlements = full_state.get('settlements', [])
    roads = full_state.get('roads', [])
    
    # Get player info
    players_opt = optimized_state.get("players", {})
    meta = optimized_state.get("meta", {})
    curr_player = meta.get("curr")
    
    # Helper to get player name from ID
    player_names_list = list(players_opt.keys())
    
    def get_player_name(player_id):
        """Convert 0-based player ID to player name"""
        if 0 <= player_id < len(player_names_list):
            return player_names_list[player_id]
        return f"Player {player_id}"
    
    # SETUP PHASE LOGIC
    if 'SETUP' in phase:
        # Check if current player has a settlement but no road
        current_player_settlements = [s for s in settlements if get_player_name(s['player'] - 1) == curr_player]
        current_player_roads = [r for r in roads if get_player_name(r['player'] - 1) == curr_player]
        
        if 'FIRST_ROUND' in phase:
            if current_player_settlements and not current_player_roads:
                # Just placed first settlement, need road
                last_settlement = current_player_settlements[-1]
                node = last_settlement.get('vertex', '?')
                
                if for_spectator:
                    return f"Player {curr_player} placed their first settlement at node {node} and is now choosing where to place their starting road."
                else:
                    return f"You placed your first settlement at node {node}. Now place a road connecting to it."
                    
            elif not current_player_settlements:
                # Need to place first settlement
                if for_spectator:
                    return f"Player {curr_player} is placing their first settlement."
                else:
                    return "It's your turn in the setup phase. Place your first settlement on a strategic location."
            else:
                # Both placed
                if for_spectator:
                    return f"Player {curr_player} completed their first settlement and road placement."
                else:
                    return "You completed your first settlement and road."
                
        elif 'SECOND_ROUND' in phase:
            # Count settlements for current player
            settlement_count = len(current_player_settlements)
            if settlement_count == 1:
                # Need second settlement
                if for_spectator:
                    return f"Player {curr_player} is placing their second settlement."
                else:
                    return "It's your turn in the second setup round. Place your second settlement."
                    
            elif settlement_count == 2 and len(current_player_roads) == 1:
                # Just placed second settlement, need second road
                last_settlement = current_player_settlements[-1]
                node = last_settlement.get('vertex', '?')
                
                if for_spectator:
                    return f"Player {curr_player} placed their second settlement at node {node} and is placing their second road."
                else:
                    return f"You placed your second settlement at node {node}. Now place your second starting road."
            else:
                if for_spectator:
                    return f"Player {curr_player} is completing their second settlement and road."
                else:
                    return "Complete your second settlement and road placement."
    
    # NORMAL PLAY LOGIC
    elif 'NORMAL' in phase:
        dice = full_state.get('dice_result')
        allowed = full_state.get('allowed_actions', [])
        
        # Check for special situations
        if 'DISCARD_CARDS' in allowed:
            player_data = full_state.get('players', [])
            if player_data and not for_spectator:
                for p in player_data:
                    if p.get('name') == current_player or p.get('id') == current_player:
                        card_count = p.get('total_cards', 0)
                        discard_count = card_count // 2
                        return f"A 7 was rolled! You have {card_count} cards and must discard {discard_count} of them."
            
            if for_spectator:
                return f"A 7 was rolled. Players with more than 7 cards must discard. Waiting for player {curr_player}."
            else:
                return "A 7 was rolled and you have more than 7 cards. You must discard half of them."
        
        elif 'ROBBER_MOVE' in allowed:
            if for_spectator:
                return f"Player {curr_player} rolled a 7 and is moving the robber to a new hex."
            else:
                return "You rolled a 7! Move the robber to a new hex to block resources and potentially steal from opponents."
        
        elif 'STEAL_CARD' in allowed:
            # Try to find which players are adjacent to robber
            robber_hex = full_state.get('robber_position')
            if for_spectator:
                return f"Player {curr_player} moved the robber to hex {robber_hex} and is choosing who to steal from."
            else:
                return f"You moved the robber to hex {robber_hex}. Now steal a resource card from an adjacent player."
        
        elif dice:
            # Check if resources were distributed
            if dice == 7:
                if for_spectator:
                    return f"A 7 was rolled by player {curr_player}. The robber is activated."
                else:
                    return "A 7 was rolled! The robber is activated."
            else:
                total = sum(dice) if isinstance(dice, (list, tuple)) else dice
                if for_spectator:
                    return f"Player {curr_player} rolled {total}. Resources were distributed. Waiting for their turn."
                else:
                    return f"The dice rolled {total}. Resources were distributed to settlements on numbered hexes. Take your actions."
        
        elif 'ROLL_DICE' in allowed:
            # Beginning of turn
            if for_spectator:
                return f"Player {curr_player} is about to roll the dice."
            else:
                return "It's your turn. Roll the dice to produce resources and begin your turn."
        
        else:
            # Mid-turn, player can build/trade/etc
            if for_spectator:
                return f"Player {curr_player} is taking their turn. They can build, trade, or use development cards."
            else:
                settlements_count = len([s for s in settlements if get_player_name(s['player'] - 1) == curr_player])
                roads_count = len([r for r in roads if get_player_name(r['player'] - 1) == curr_player])
                
                if settlements_count > 2 or roads_count > 2:
                    return f"Continue your turn. You have {settlements_count} settlements and {roads_count} roads. Build, trade, or end your turn."
                else:
                    return "Continue your turn. You can build, trade with others or the bank, buy development cards, or end your turn."
    
    # DEFAULT
    if for_spectator:
        return f"It's player {curr_player}'s turn. Watch and wait, or negotiate trades."
    else:
        return "It's your turn."


def get_player_colors():
    """Get color mappings for players (hardcoded for now)."""
    return {
        "a": "Red",
        "b": "Blue", 
        "c": "White",
        "d": "Orange"
    }


def convert_allowed_actions_to_prompt_format(allowed_actions_list):
    """
    Convert GameManager's allowed_actions (ActionType enum names)
    into the format needed for AI prompts.
    
    Args:
        allowed_actions_list: List of ActionType enum names (e.g., ["PLACE_STARTING_ROAD", "END_TURN"])
        
    Returns:
        List of action dictionaries with action, description, and example_parameters
    """
    # Map ActionType enum names to prompt-friendly format
    action_map = {
        "PLACE_STARTING_SETTLEMENT": {
            "action": "place_settlement",
            "description": "Place your starting settlement on an available node",
            "example_parameters": {"location": "20"}
        },
        "PLACE_STARTING_ROAD": {
            "action": "build_road",
            "description": "Place your starting road connecting to your settlement",
            "example_parameters": {"from": "20", "to": "21"}
        },
        "BUILD_SETTLEMENT": {
            "action": "build_settlement",
            "description": "Build a settlement on an available node (costs: wood, brick, wheat, sheep)",
            "example_parameters": {"location": "25"}
        },
        "BUILD_CITY": {
            "action": "build_city",
            "description": "Upgrade a settlement to a city (costs: 3 ore, 2 wheat)",
            "example_parameters": {"location": "20"}
        },
        "BUILD_ROAD": {
            "action": "build_road",
            "description": "Build a road on an available edge (costs: wood, brick)",
            "example_parameters": {"from": "20", "to": "21"}
        },
        "ROLL_DICE": {
            "action": "roll_dice",
            "description": "Roll the dice to produce resources",
            "example_parameters": {}
        },
        "BUY_DEV_CARD": {
            "action": "buy_development_card",
            "description": "Buy a development card (costs: ore, sheep, wheat)",
            "example_parameters": {}
        },
        "USE_DEV_CARD": {
            "action": "use_development_card",
            "description": "Play a development card from your hand",
            "example_parameters": {"card_type": "KNIGHT"}
        },
        "TRADE_PROPOSE": {
            "action": "propose_trade",
            "description": "Propose a trade with another player",
            "example_parameters": {"offer": ["wood"], "request": ["brick"], "target_player": "b"}
        },
        "TRADE_BANK": {
            "action": "trade_with_bank",
            "description": "Trade resources with the bank (4:1 or use ports for better rates)",
            "example_parameters": {"offer": ["wood", "wood", "wood", "wood"], "request": ["brick"]}
        },
        "ROBBER_MOVE": {
            "action": "move_robber",
            "description": "Move the robber to a new hex (after rolling 7)",
            "example_parameters": {"hex_id": "5"}
        },
        "STEAL_CARD": {
            "action": "steal_from_player",
            "description": "Steal a resource card from a player adjacent to the robber",
            "example_parameters": {"target_player": "b"}
        },
        "DISCARD_CARDS": {
            "action": "discard_cards",
            "description": "Discard half your cards (when 7 is rolled and you have > 7 cards)",
            "example_parameters": {"cards": ["wood", "brick"]}
        },
        "END_TURN": {
            "action": "end_turn",
            "description": "End your turn",
            "example_parameters": {}
        }
    }
    
    converted_actions = []
    for action_name in allowed_actions_list:
        if action_name in action_map:
            converted_actions.append(action_map[action_name])
        else:
            # Unknown action - add a generic entry
            converted_actions.append({
                "action": action_name.lower(),
                "description": f"Perform action: {action_name}",
                "example_parameters": {}
            })
    
    # Always add wait_for_response as an option
    converted_actions.append({
        "action": "wait_for_response",
        "description": "Do nothing on the board, just chat or wait for other players",
        "example_parameters": {}
    })
    
    return converted_actions


def generate_prompt_for_player(player_name, game_state, prompt_manager, full_state=None):
    """
    Generate a complete prompt for a specific player.
    
    Args:
        player_name: Name of the player (e.g., "a", "b", "c")
        game_state: Current game state (optimized format)
        prompt_manager: PromptManager instance
        full_state: Full state with allowed_actions (optional)
        
    Returns:
        Complete prompt dictionary
    """
    # Get player index (0-based)
    players = game_state.get("players", {})
    player_names = list(players.keys())
    player_num = player_names.index(player_name) if player_name in player_names else 0
    
    # Get current phase and current player
    meta = game_state.get("meta", {})
    phase = meta.get("phase", "UNKNOWN")
    current_player = meta.get("curr")
    
    # Check if this is the current player's turn
    is_my_turn = (current_player == player_name)
    
    # Get allowed_actions from full_state if available
    allowed_actions_raw = []
    if full_state and 'allowed_actions' in full_state:
        allowed_actions_raw = full_state.get('allowed_actions', [])
    
    # Determine what happened and what to do
    if is_my_turn:
        # This player's turn - use allowed_actions from GameManager
        if allowed_actions_raw:
            # Convert GameManager's ActionType names to prompt format
            available_actions = convert_allowed_actions_to_prompt_format(allowed_actions_raw)
            
            # Generate contextual message based on actual game state
            what_happened = generate_what_happened_message(full_state, game_state, player_name, for_spectator=False)
            
        else:
            # Fallback: no allowed_actions available, make a generic message
            what_happened = "It's your turn."
            available_actions = [{
                "action": "wait_for_response",
                "description": "Wait for game state update",
                "example_parameters": {}
            }]
    else:
        # Not this player's turn - they are spectating
        what_happened = generate_what_happened_message(full_state, game_state, player_name, for_spectator=True)
        available_actions = None  # No actions when not your turn
    
    # Generate the prompt
    prompt = prompt_manager.create_prompt(
        player_num=player_num,
        player_name=player_name,
        player_color="",  # Color not needed
        game_state=game_state,
        what_happened=what_happened,
        available_actions=available_actions,
        custom_instructions=f"You are player '{player_name}'. Play strategically to win."
    )
    
    return prompt


def save_prompt_to_file(player_name, prompt, output_dir, is_active_player=True):
    """
    Save a prompt as JSON file with response schema header.
    
    Args:
        player_name: Name of the player
        prompt: Complete prompt dictionary
        output_dir: Directory to save to
        is_active_player: Whether this player is currently active (affects schema)
    """
    output_file = output_dir / f"prompt_player_{player_name}.json"
    
    # Select appropriate schema
    schema = get_response_schema() if is_active_player else get_spectator_response_schema()
    
    # Create complete LLM request with schema + prompt
    llm_request = {
        "response_schema": schema,
        "system_instruction": "You are an expert Settlers of Catan player. Analyze the game state carefully and respond in the exact JSON format specified in response_schema." if is_active_player else "You are observing the game while waiting for your turn. Track what's happening, plan your strategy, and you can communicate with other players.",
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
    
    # Load current game state (optimized version for AI)
    print("📖 Loading current game state...")
    game_state = load_current_state()
    
    if not game_state:
        return
    
    # Load full state (with allowed_actions)
    print("📖 Loading full state (with allowed_actions)...")
    full_state = load_full_state()
    
    # Show basic info
    meta = game_state.get("meta", {})
    players = game_state.get("players", {})
    
    print(f"✓ Loaded game state")
    print(f"  Phase: {meta.get('phase')}")
    print(f"  Current Player: {meta.get('curr')}")
    print(f"  Players: {', '.join(players.keys())}")
    
    if full_state and 'allowed_actions' in full_state:
        print(f"  Allowed Actions: {', '.join(full_state['allowed_actions'])}")
    else:
        print("  ⚠️  Warning: No allowed_actions in state (using fallback logic)")
    print()
    
    # Create prompt manager
    config = AIConfig()
    prompt_manager = PromptManager(config)
    
    # Get current session directory and create prompts subdirectory
    session_dir = get_current_session_dir()
    if session_dir:
        output_dir = session_dir / 'prompts'
        output_dir.mkdir(exist_ok=True, parents=True)
    else:
        # Fallback to old location if no session
        output_dir = Path('examples/ai_testing/my_games/prompts')
        output_dir.mkdir(exist_ok=True, parents=True)
    
    print("📝 Generating prompts for each player...\n")
    
    # Generate prompt for each player
    for player_name in players.keys():
        print(f"  ⚙️  Generating prompt for player '{player_name}'...")
        
        try:
            is_active = (player_name == meta.get("curr"))
            prompt = generate_prompt_for_player(player_name, game_state, prompt_manager, full_state)
            save_prompt_to_file(player_name, prompt, output_dir, is_active_player=is_active)
            
            json_file = output_dir / f"prompt_player_{player_name}.json"
            txt_file = output_dir / f"prompt_player_{player_name}.txt"
            status = "🎯 ACTIVE" if is_active else "👁️  WATCHING"
            print(f"     {status}")
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
