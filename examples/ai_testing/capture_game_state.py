"""
Capture Game State from Real Game
----------------------------------
This script runs a real game with predefined inputs and captures the JSON
data that is sent to the Web Visualizer. This is exactly what an AI would see.

Usage:
    python capture_game_state.py [--input-file INPUT_FILE] [--output-file OUTPUT_FILE]
"""

import sys
import json
import time
from pathlib import Path
from io import StringIO

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pycatan.visualizations.web_visualization import WebVisualization
from pycatan.management.game_manager import GameManager
from pycatan.players.human_user import HumanUser


class StateCapturingWebViz(WebVisualization):
    """
    Extended WebVisualization that captures all state updates.
    """
    
    def __init__(self, *args, **kwargs):
        # Don't start the server automatically
        kwargs['auto_open'] = False
        super().__init__(*args, **kwargs)
        
        self.captured_states = []
        self.captured_actions = []
        self.turn_states = {}  # Maps turn number to state
        
    def update_full_state(self, game_state):
        """Override to capture state updates."""
        # Call parent to do the conversion
        super().update_full_state(game_state)
        
        # Capture the converted state
        if self.current_game_state:
            state_copy = json.loads(json.dumps(self.current_game_state))
            self.captured_states.append(state_copy)
            
            # Store by turn number if available
            turn_num = state_copy.get('turn_number', len(self.captured_states))
            self.turn_states[turn_num] = state_copy
            
            print(f"\n📸 Captured state for turn {turn_num}")
            
    def display_action(self, action, result):
        """Override to capture actions."""
        super().display_action(action, result)
        
        action_data = {
            'action_type': str(action.action_type) if hasattr(action, 'action_type') else 'unknown',
            'player_id': action.player_id if hasattr(action, 'player_id') else None,
            'success': result.success if hasattr(result, 'success') else None,
            'timestamp': str(action.timestamp) if hasattr(action, 'timestamp') else None
        }
        self.captured_actions.append(action_data)
    
    def get_latest_state(self):
        """Get the most recent captured state."""
        return self.captured_states[-1] if self.captured_states else None
    
    def get_state_at_turn(self, turn_number):
        """Get state at a specific turn."""
        return self.turn_states.get(turn_number)
    
    def print_latest_state(self):
        """Print the latest state as formatted JSON."""
        latest = self.get_latest_state()
        if latest:
            print("\n" + "="*80)
            print("📊 LATEST GAME STATE JSON")
            print("="*80)
            print(json.dumps(latest, indent=2, ensure_ascii=False))
            print("="*80)
            
            # Print summary
            self._print_summary(latest)
    
    def _print_summary(self, state_data):
        """Print a human-readable summary."""
        print("\n" + "="*80)
        print("📈 SUMMARY")
        print("="*80)
        print(f"Current Player: {state_data.get('current_player', 0)}")
        print(f"Game Phase: {state_data.get('current_phase', 'UNKNOWN')}")
        print(f"Robber Position: {state_data.get('robber_position', 'Unknown')}")
        
        if state_data.get('dice_result'):
            print(f"Last Dice Roll: {state_data['dice_result']}")
        
        print(f"\nBoard:")
        print(f"  - Hexes: {len(state_data.get('hexes', []))}")
        print(f"  - Settlements: {len(state_data.get('settlements', []))}")
        print(f"  - Cities: {len(state_data.get('cities', []))}")
        print(f"  - Roads: {len(state_data.get('roads', []))}")
        
        print(f"\nPlayers: {len(state_data.get('players', []))}")
        for player in state_data.get('players', []):
            print(f"  Player {player.get('id', '?')}: {player.get('name', 'Unknown')}")
            print(f"    - Victory Points: {player.get('victory_points', 0)}")
            print(f"    - Resources: {len(player.get('cards', []))}")
            print(f"    - Dev Cards: {len(player.get('dev_cards', []))}")
            if player.get('has_longest_road'):
                print(f"    - Has Longest Road!")
            if player.get('has_largest_army'):
                print(f"    - Has Largest Army!")
        print("="*80)
    
    def save_state_to_file(self, filepath, turn_number=None):
        """Save a specific state to JSON file."""
        if turn_number is not None:
            state = self.get_state_at_turn(turn_number)
            if not state:
                print(f"❌ No state captured for turn {turn_number}")
                return False
        else:
            state = self.get_latest_state()
            
        if not state:
            print("❌ No state to save")
            return False
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        print(f"✅ State saved to: {filepath}")
        return True


def run_game_with_inputs(input_lines):
    """
    Run a game with predefined inputs and capture states.
    
    Args:
        input_lines: List of input strings to feed to the game
        
    Returns:
        StateCapturingWebViz: The visualizer with captured states
    """
    # Create input stream from the lines
    input_stream = StringIO('\n'.join(input_lines))
    
    # Temporarily redirect stdin
    original_stdin = sys.stdin
    sys.stdin = input_stream
    
    try:
        # Create capturing visualizer
        viz = StateCapturingWebViz(port=5555, auto_open=False)
        
        # Create game manager with visualization
        # We'll create simple users - the input will come from our stream
        users = []  # Will be populated by game manager from input
        
        print("\n🎮 Starting game with captured inputs...")
        print(f"   Total input lines: {len(input_lines)}")
        print("="*80)
        
        # Start game - this will consume the inputs
        game_manager = GameManager(users=None, visualizations=[viz])
        
        # The game will read from our input stream
        game_manager.start_game()
        
        print("\n✅ Game completed!")
        print(f"📸 Captured {len(viz.captured_states)} states")
        
        return viz
        
    except EOFError:
        print("\n⚠️  Input ended - game may be incomplete")
        return viz
    except Exception as e:
        print(f"\n❌ Error running game: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Restore stdin
        sys.stdin = original_stdin


def main():
    """Main function to capture game states."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Capture game state from real game')
    parser.add_argument('--input-file', type=str, 
                       default='examples/data/game_moves_3Players.txt',
                       help='Path to file with game inputs')
    parser.add_argument('--output-file', type=str,
                       help='Path to save captured state JSON')
    parser.add_argument('--turn', type=int,
                       help='Capture state at specific turn number')
    parser.add_argument('--all-turns', action='store_true',
                       help='Save all turn states to separate files')
    
    args = parser.parse_args()
    
    # Read input file
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        input_lines = [line.strip() for line in f if line.strip()]
    
    print(f"📂 Loaded inputs from: {input_file}")
    print(f"   Lines: {len(input_lines)}")
    
    # Run game and capture states
    viz = run_game_with_inputs(input_lines)
    
    if not viz:
        print("❌ Failed to capture game states")
        return
    
    # Print latest state
    viz.print_latest_state()
    
    # Save states
    if args.all_turns:
        output_dir = Path('examples/ai_testing/captured_states')
        output_dir.mkdir(exist_ok=True)
        
        print(f"\n💾 Saving all turn states to: {output_dir}")
        for turn_num, state in viz.turn_states.items():
            output_file = output_dir / f"turn_{turn_num:03d}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            print(f"   ✅ Saved turn {turn_num}")
        
    elif args.output_file:
        viz.save_state_to_file(args.output_file, args.turn)
    
    else:
        # Default: save latest state
        output_file = Path('examples/ai_testing/sample_states/captured_game.json')
        viz.save_state_to_file(str(output_file))
    
    print("\n" + "="*80)
    print("✨ CAPTURE COMPLETE")
    print("="*80)
    print("You now have the exact JSON that would be sent to an AI agent!")
    print("Use visualize_game_state.py to view it in the browser.")
    print("="*80)


if __name__ == '__main__':
    main()
