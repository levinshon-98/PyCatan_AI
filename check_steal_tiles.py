"""
Check which tiles have player a's settlements nearby
"""
from pycatan.game_manager import GameManager
from pycatan.human_user import HumanUser
from pycatan.actions import GamePhase
from pycatan.board_definition import board_definition

# Create game
users = [HumanUser("a", 0), HumanUser("b", 1), HumanUser("c", 2)]
gm = GameManager(users)
game = gm.game

# From your game_moves file, player a built settlements at points 10, 14, 36
# Let's check which tiles are near these points

print("Checking which tiles are adjacent to player a's buildings:\n")

# Check all tiles
for row_idx, tile_row in enumerate(game.board.tiles):
    for tile_idx, tile in enumerate(tile_row):
        if tile:
            # Get connected points
            points = game.board.get_connected_points(row_idx, tile_idx)
            
            # Check if any point has player 0's building
            has_player_a = False
            for p in points:
                if p and p.building and p.building.owner == 0:
                    has_player_a = True
                    break
            
            if has_player_a:
                hex_id = board_definition.game_coords_to_hex_id(row_idx, tile_idx)
                print(f"  Tile {hex_id} at [{row_idx}, {tile_idx}] - player a has building nearby")

print("\n✓ Use knight with one of these tiles to steal from player a")
