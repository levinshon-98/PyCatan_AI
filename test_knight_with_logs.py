"""
Test Knight card with full logging - simulating real game scenario
"""
from pycatan.game_manager import GameManager
from pycatan.human_user import HumanUser
from pycatan.actions import GamePhase, Action, ActionType
from pycatan.card import DevCard

print("="*70)
print("Testing Knight Card - Full Logging")
print("="*70)

# Create game matching the game_moves file
users = [HumanUser("a", 0), HumanUser("b", 1), HumanUser("c", 2)]
gm = GameManager(users)
game = gm.game

# Setup game state
gm._is_running = True
gm._current_player_id = 1  # b's turn
gm._current_game_state.game_phase = GamePhase.NORMAL_PLAY
gm._current_game_state.current_player = 1
gm._current_game_state.dice_rolled = True

# Set robber to tile 19 (as you said)
from pycatan.board_definition import board_definition
tile_19_coords = board_definition.hex_id_to_game_coords(19)
print(f"\nSetting initial robber to tile 19 (coords: {tile_19_coords})")
game.board.robber = list(tile_19_coords)
print(f"Initial robber position: {game.board.robber}")

# Give b a Knight card
game.players[1].add_dev_card(DevCard.Knight)
print(f"Player b has Knight card: {DevCard.Knight in game.players[1].dev_cards}")

# Now simulate the command: use knight tile 5 steal a
print("\n" + "="*70)
print("SIMULATING: use knight tile 5 steal a")
print("="*70)

# Parse the command through HumanUser
user_b = users[1]
game_state = gm.get_full_state()

# Manually create the action like HumanUser would
tile_5_coords = board_definition.hex_id_to_game_coords(5)
print(f"\nTile 5 coordinates: {tile_5_coords}")

action = Action(ActionType.USE_DEV_CARD, 1, {
    'card_type': 'Knight',
    'tile_coords': tile_5_coords,
    'victim_id': 0  # steal from a
})

print(f"\nAction created: {action}")
print(f"Parameters: {action.parameters}")

print("\n" + "="*70)
print("EXECUTING ACTION...")
print("="*70 + "\n")

result = gm.execute_action(action)

print("\n" + "="*70)
print("RESULT:")
print("="*70)
print(f"Success: {result.success}")
if not result.success:
    print(f"Error: {result.error_message}")
print(f"\nFinal robber position: {game.board.robber}")
actual_tile = board_definition.game_coords_to_hex_id(game.board.robber[0], game.board.robber[1])
print(f"Robber is on tile: {actual_tile}")
