"""
Test script to verify Largest Army is displayed correctly in web and console visualizations.
"""

from pycatan import Game
from pycatan.visualizations.console_visualization import ConsoleVisualization
from pycatan.visualizations.web_visualization import WebVisualization
import time

def main():
    print("🎲 Creating test game with Knight cards...")
    
    # Create game with 3 players
    game = Game(num_of_players=3)
    
    # Setup visualizations
    console_viz = ConsoleVisualization(use_colors=True)
    web_viz = WebVisualization(port=5001, auto_open=False)
    
    # Simulate playing knights
    print("\n📝 Simulating Knight card usage...")
    
    # Player 0 plays 2 knights
    game.players[0].knight_cards = 2
    print(f"Player 0 has {game.players[0].knight_cards} knights")
    
    # Player 1 plays 4 knights (should get Largest Army)
    game.players[1].knight_cards = 4
    game.largest_army = 1  # Player 1 has largest army
    print(f"Player 1 has {game.players[1].knight_cards} knights - should have Largest Army!")
    
    # Player 2 plays 1 knight
    game.players[2].knight_cards = 1
    print(f"Player 2 has {game.players[2].knight_cards} knights")
    
    # Get game state
    print("\n🔄 Getting game state...")
    state = game.get_full_state()
    
    # Display in console
    print("\n" + "="*60)
    print("CONSOLE VISUALIZATION:")
    print("="*60)
    console_viz.display_game_state(state)
    
    # Start web server
    print("\n" + "="*60)
    print("WEB VISUALIZATION:")
    print("="*60)
    print("Starting web visualization on http://localhost:5001")
    print("Open your browser to see Largest Army displayed!")
    
    web_viz.start_server()
    web_viz.update_full_state(state)
    
    print("\n✨ Check the web interface to see:")
    print("   - Player 1 should have: ⚔️ Largest Army (+2 VP)")
    print("   - All players should show their knight count")
    print("\nPress Ctrl+C to exit...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        web_viz.stop_server()

if __name__ == "__main__":
    main()
