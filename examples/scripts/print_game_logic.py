
import sys
import os

# Add the current directory to the path
sys.path.append(os.getcwd())

from pycatan import Game
from pycatan.config.board_definition import board_definition

def print_game_expectations():
    print("Initializing Game...")
    game = Game()
    board = game.board
    
    print("\n" + "="*60)
    print("GAME LOGIC EXPECTATIONS (What the Python code thinks)")
    print("="*60 + "\n")
    
    print("Format: Hex [Row, Col] -> Connected Point Coordinates [Row, Col]")
    print("-" * 60)

    # Iterate through all tiles in the game board
    for r, row in enumerate(board.tiles):
        for i, tile in enumerate(row):
            # Get connected points according to Game Logic
            game_connected_points = tile.points
            
            # Get coordinates of connected points
            point_coords = []
            for p in game_connected_points:
                point_coords.append(list(p.position))
            
            # Sort for readability
            point_coords.sort()
            
            print(f"Hex [{r}, {i}] connects to Points: {point_coords}")

if __name__ == "__main__":
    print_game_expectations()
