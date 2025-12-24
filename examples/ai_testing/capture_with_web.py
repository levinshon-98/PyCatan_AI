"""
Capture Game State WITH Web Visualizer
---------------------------------------
Runs a game with predefined inputs, captures the JSON data,
AND displays it in the web browser so you can see the board visually.
"""

import sys
from pathlib import Path
import os
import json
import time
import threading

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pycatan.visualizations.web_visualization import WebVisualization

# Capture states
captured_states = []
update_counter = 0

original_update = WebVisualization.update_full_state

def capturing_update(self, game_state):
    """Capture and save all states."""
    global update_counter
    original_update(self, game_state)
    
    if hasattr(self, 'current_game_state') and self.current_game_state:
        update_counter += 1
        state_copy = json.loads(json.dumps(self.current_game_state))
        captured_states.append(state_copy)
        
        # Print just a notification (not the full JSON to keep output clean)
        print(f"[State #{update_counter} captured]", end=' ', flush=True)

# Apply patch
WebVisualization.update_full_state = capturing_update


def save_captured_states():
    """Save all captured states to files."""
    if not captured_states:
        print("\n\nNo states were captured!")
        return False
    
    # Create output directory
    output_dir = Path('examples/ai_testing/captured_states')
    output_dir.mkdir(exist_ok=True)
    
    # Save first state
    first_state = captured_states[0]
    first_file = output_dir / 'state_001_initial.json'
    with open(first_file, 'w', encoding='utf-8') as f:
        json.dump(first_state, f, indent=2, ensure_ascii=False)
    
    # Save last state
    last_state = captured_states[-1]
    last_file = output_dir / f'state_{len(captured_states):03d}_final.json'
    with open(last_file, 'w', encoding='utf-8') as f:
        json.dump(last_state, f, indent=2, ensure_ascii=False)
    
    # Also save to sample_states for compatibility
    sample_file = Path('examples/ai_testing/sample_states/captured_game.json')
    sample_file.parent.mkdir(exist_ok=True)
    with open(sample_file, 'w', encoding='utf-8') as f:
        json.dump(last_state, f, indent=2, ensure_ascii=False)
    
    print(f"\n\n{'='*80}")
    print(f"Captured {len(captured_states)} states total")
    print("="*80)
    print(f"\nSaved states:")
    print(f"  - First: {first_file}")
    print(f"  - Last:  {last_file}")
    print(f"  - Main:  {sample_file}")
    
    # Print summary of last state
    print("\n" + "="*80)
    print("FINAL GAME STATE SUMMARY")
    print("="*80)
    
    print(f"\nBoard:")
    print(f"  Hexes: {len(last_state.get('hexes', []))}")
    print(f"  Points: {len(last_state.get('points', []))} (with adjacency info)")
    print(f"  Settlements: {len(last_state.get('settlements', []))}")
    print(f"  Cities: {len(last_state.get('cities', []))}")
    print(f"  Roads: {len(last_state.get('roads', []))}")
    
    print(f"\nPlayers:")
    for player in last_state.get('players', []):
        print(f"  Player {player.get('id')}: {player.get('name')}")
        print(f"    VP: {player.get('victory_points', 0)}, Resources: {len(player.get('cards_list', []))}")
    
    print(f"\nGame Info:")
    print(f"  Current Player: {last_state.get('current_player')}")
    print(f"  Phase: {last_state.get('current_phase')}")
    
    print("\n" + "="*80)
    
    return True


def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = 'examples/data/game_moves_3Players.txt'
    
    print(f"\nRunning game with: {input_file}")
    print("Web Visualizer will open in browser...")
    print("States are being captured in the background...")
    print("="*80 + "\n")
    
    # Read inputs
    with open(input_file, 'r', encoding='utf-8') as f:
        inputs = f.read()
    
    from io import StringIO
    sys.stdin = StringIO(inputs)
    
    try:
        from pycatan import RealGame
        game = RealGame()
        
        # The game will run with web server active
        game.run()
        
    except (EOFError, KeyboardInterrupt):
        print("\n\nGame stopped by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
    
    # Save captured states
    if save_captured_states():
        print("\n" + "="*80)
        print("SUCCESS!")
        print("="*80)
        print("\nThe web visualizer should still be open in your browser.")
        print("You can see the final board state there.")
        print("\nThe complete JSON (with points and adjacency info) is saved in:")
        print("  examples/ai_testing/sample_states/captured_game.json")
        print("\nTo see the full JSON, run:")
        print("  Get-Content examples/ai_testing/sample_states/captured_game.json")
        print("="*80)
    
    # Keep the script alive so web server stays up
    print("\n\nPress Ctrl+C to stop the web server and exit...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")


if __name__ == '__main__':
    main()
