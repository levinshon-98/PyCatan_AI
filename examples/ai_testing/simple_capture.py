"""
Simple Game State Capturer
---------------------------
Runs a game and prints the JSON at each major point.
WITHOUT starting a web server (to avoid port conflicts).
"""

import sys
from pathlib import Path
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from pycatan.visualizations.web_visualization import WebVisualization


# Monkey-patch to capture states WITHOUT starting server
original_update = WebVisualization.update_full_state
original_start_server = WebVisualization.start_server
captured_states = []

def capturing_update(self, game_state):
    """Capture state and print JSON."""
    original_update(self, game_state)
    
    if hasattr(self, 'current_game_state') and self.current_game_state:
        print("\n" + "="*80)
        print("GAME STATE JSON (This is what AI receives)")
        print("="*80)
        print(json.dumps(self.current_game_state, indent=2, ensure_ascii=False))
        print("="*80 + "\n")
        
        # Save to list
        captured_states.append(self.current_game_state.copy())

def no_start_server(self):
    """Don't start the server - just capture data."""
    print("[INFO] Web server disabled for capture mode")
    self.running = True  # Pretend it's running
    pass

# Apply monkey patches
WebVisualization.update_full_state = capturing_update
WebVisualization.start_server = no_start_server


def main():
    """Run game with input file."""
    import sys
    import os
    
    # Fix encoding for Windows console
    if sys.platform == 'win32':
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # Check if input file provided
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = 'examples/data/game_moves_3Players.txt'
    
    print(f"\nRunning game with inputs from: {input_file}")
    print("="*80)
    
    # Read inputs
    with open(input_file, 'r', encoding='utf-8') as f:
        inputs = f.read()
    
    # Feed to stdin
    from io import StringIO
    sys.stdin = StringIO(inputs)
    
    try:
        print("[INFO] Starting game in capture mode (web server disabled)")
        print("="*80)
        
        # Import after patching
        from pycatan import RealGame
        
        # Run the game - this will print JSON at each update
        game = RealGame()
        game.run()
        
    except (EOFError, KeyboardInterrupt):
        print("\n\nGame stopped")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print(f"Captured {len(captured_states)} states total")
    print("="*80)
    
    # Save last state
    if captured_states:
        output_file = 'examples/ai_testing/sample_states/captured_game.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(captured_states[-1], f, indent=2, ensure_ascii=False)
        print(f"Last state saved to: {output_file}")
    else:
        print("WARNING: No states were captured!")


if __name__ == '__main__':
    main()
