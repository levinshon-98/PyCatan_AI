"""
Test to see robber position before and after Knight card
"""
from pycatan.game_manager import GameManager
from pycatan.human_user import HumanUser
from pycatan.actions import GamePhase, Action, ActionType
from pycatan.card import DevCard

print("\n" + "="*60)
print("Testing Robber Movement with Knight Card")
print("="*60)

# Create game
users = [HumanUser("a", 0), HumanUser("b", 1), HumanUser("c", 2)]
gm = GameManager(users)
game = gm.game

# Setup game state
gm._is_running = True
gm._current_player_id = 1
gm._current_game_state.game_phase = GamePhase.NORMAL_PLAY
gm._current_game_state.current_player = 1
gm._current_game_state.dice_rolled = True

# Give b a Knight card
game.players[1].add_dev_card(DevCard.Knight)

# Show initial robber position
print(f"\nBEFORE Knight card:")
print(f"  Robber position: {game.board.robber}")

# Try to use knight - tile 5
from pycatan.board_definition import board_definition
tile_5_coords = board_definition.hex_id_to_game_coords(5)
print(f"\nTrying to move robber to tile 5")
print(f"  Tile 5 coordinates: {tile_5_coords}")

# Try WITHOUT steal first
print("\n--- Attempt 1: WITHOUT steal ---")
action1 = Action(ActionType.USE_DEV_CARD, 1, {
    'card_type': 'Knight',
    'tile_coords': tile_5_coords,
    'victim_id': None
})

result1 = gm.execute_action(action1)
print(f"Result: {result1.success}")
if not result1.success:
    print(f"Error: {result1.error_message}")

print(f"\nAFTER attempt:")
print(f"  Robber position: {game.board.robber}")
print(f"  Expected: {list(tile_5_coords)}")
print(f"  Match: {game.board.robber == list(tile_5_coords)}")

# Convert back to see what hex ID we're on
if game.board.robber:
    actual_hex = board_definition.game_coords_to_hex_id(game.board.robber[0], game.board.robber[1])
    print(f"  Robber is actually on tile: {actual_hex}")

print("\n" + "="*60)
