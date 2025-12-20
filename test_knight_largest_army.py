"""
Test Knight card usage with real game to verify Largest Army detection.
Simulates using 4+ Knights to trigger Largest Army achievement.
"""

from pycatan import Game, Statuses
from pycatan.card import DevCard, ResCard
from pycatan.console_visualization import ConsoleVisualization
from pycatan.web_visualization import WebVisualization
import time

def main():
    print("🎴 Testing Knight Cards and Largest Army")
    print("="*60)
    
    # Create game
    game = Game(num_of_players=3)
    board = game.board
    
    # Setup visualizations
    console_viz = ConsoleVisualization(use_colors=True)
    web_viz = WebVisualization(port=5002, auto_open=False)
    
    # Quick setup phase
    print("\n📍 Setting up starting positions...")
    game.add_settlement(0, board.points[0][0], is_starting=True)
    game.add_road(0, board.points[0][0], board.points[0][1], is_starting=True)
    game.add_settlement(1, board.points[1][0], is_starting=True)
    game.add_road(1, board.points[1][0], board.points[1][1], is_starting=True)
    game.add_settlement(2, board.points[2][0], is_starting=True)
    game.add_road(2, board.points[2][0], board.points[2][1], is_starting=True)
    
    # Give Player 0 several Knight cards
    print("\n🎴 Giving Player 0 Knight cards...")
    for _ in range(5):
        game.players[0].dev_cards.append(DevCard.Knight)
    
    print(f"Player 0 now has {len(game.players[0].dev_cards)} dev cards")
    
    # Use Knights one by one
    print("\n⚔️ Using Knights...")
    
    for i in range(4):
        print(f"\n--- Using Knight #{i+1} ---")
        
        # Use knight (move robber to tile 1, no victim)
        result = game.use_dev_card(
            player=0,
            card=DevCard.Knight,
            args={'robber_pos': [0, 0], 'victim': None}
        )
        
        print(f"Result: {result}")
        print(f"Knights played: {game.players[0].knight_cards}")
        print(f"Largest Army holder: {game.largest_army}")
        
        if i == 2:  # After 3rd knight
            if game.largest_army == 0:
                print("✅ Player 0 got Largest Army after 3 knights!")
            else:
                print("❌ Expected Largest Army after 3 knights")
        
        time.sleep(0.5)
    
    # Display final state
    print("\n" + "="*60)
    print("FINAL GAME STATE")
    print("="*60)
    
    state = game.get_full_state()
    
    # Console display
    console_viz.display_game_state(state)
    
    # Web display
    print("\n🌐 Starting web visualization on http://localhost:5002")
    web_viz.start_server()
    web_viz.update_full_state(state)
    
    print("\n✨ Check the web interface:")
    print("   - Player 0 should show: ⚔️ Largest Army (+2 VP)")
    print("   - Player 0 should show: 🗡️ Knights: 4")
    print("   - Victory points should include +2 for Largest Army")
    print("\nPress Ctrl+C to exit...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        web_viz.stop_server()

if __name__ == "__main__":
    main()
