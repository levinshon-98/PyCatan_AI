"""
Quick test to verify harbors are displayed in web visualization.
"""

from pycatan.core.game import Game
from pycatan.visualizations.web_visualization import WebVisualization
import time

def test_harbors():
    print("🧪 Testing Harbor Display in Web Visualization")
    print("=" * 60)
    
    # Create a simple game
    print("1. Creating game with 3 players...")
    game = Game(num_of_players=3)
    
    # Get full game state
    print("2. Getting game state...")
    game_state = game.get_full_state()
    
    # Check if harbors are in the state
    print(f"3. Checking harbors in board_state...")
    if hasattr(game_state.board_state, 'harbors'):
        harbors = game_state.board_state.harbors
        print(f"   ✓ Found {len(harbors)} harbors!")
        
        # Print first few harbors
        for i, harbor in enumerate(harbors[:3]):
            print(f"   Harbor {i+1}: {harbor}")
    else:
        print("   ✗ No harbors found in board_state!")
        return
    
    # Create web visualization
    print("\n4. Creating web visualization...")
    web_viz = WebVisualization(port=5000, auto_open=True)
    
    # Update with game state
    print("5. Updating visualization with game state...")
    web_viz.update_full_state(game_state)
    
    # Check converted state
    if web_viz.current_game_state and 'harbors' in web_viz.current_game_state:
        converted_harbors = web_viz.current_game_state['harbors']
        print(f"   ✓ Converted {len(converted_harbors)} harbors for web display!")
        
        # Print first few converted harbors
        for i, harbor in enumerate(converted_harbors[:3]):
            print(f"   Harbor {i+1}: type={harbor['type']}, ratio={harbor['ratio']}, points={harbor.get('point_one')}-{harbor.get('point_two')}")
    else:
        print("   ✗ No harbors in converted state!")
        return
    
    # Start the server
    print("\n6. Starting web server...")
    print("   → Open http://localhost:5000 to see the game board")
    print("   → Harbors should appear at the top of the board")
    print("   → Press Ctrl+C to stop the server")
    
    web_viz.start()
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n✓ Test completed!")

if __name__ == "__main__":
    test_harbors()
