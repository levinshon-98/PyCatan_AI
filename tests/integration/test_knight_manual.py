"""
Manual test for Knight card - no emoji issues
"""
import sys
import os

# Force UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

from pycatan.management.game_manager import GameManager
from pycatan.players.human_user import HumanUser
from pycatan.visualizations.console_visualization import ConsoleVisualization
from pycatan.management.actions import GamePhase
from pycatan.core.card import DevCard, ResCard

def main():
    print("="*60)
    print("Testing Knight Card - Manual Game")
    print("="*60)
    
    # Create game
    users = [HumanUser(f"Player{i}", i) for i in range(3)]
    game_manager = GameManager(users)
    
    # Add console viz
    viz = ConsoleVisualization()
    game_manager.visualization_manager = type('obj', (object,), {
        'visualizations': [viz],
        'display_action': lambda a, r: viz.display_action(a, r),
        'display_game_state': lambda s: viz.display_game_state(s)
    })()
    
    print("\nEnter commands (or 'help' for list):")
    print("Type 'quit' to exit\n")
    
    # Read from the moves file
    moves_file = "pycatan/game_moves_3Players.txt"
    with open(moves_file, 'r') as f:
        lines = [line.strip() for line in f.readlines()]
    
    # Execute moves
    move_index = 0
    while move_index < len(lines):
        cmd = lines[move_index]
        move_index += 1
        
        # Skip empty lines
        if not cmd:
            continue
            
        print(f"> {cmd}")
        
        # Check if it's the knight command we're testing
        if cmd.startswith("use knight"):
            print(f"\n>>> BEFORE Knight card:")
            print(f"    Robber position: {game_manager.game.board.robber}")
            
        # Process the command (simplified - just for testing)
        if cmd == "quit":
            break
            
    print("\n" + "="*60)
    print("Test Complete")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
