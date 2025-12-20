"""
Test Knight card with invalid steal attempt
"""
from pycatan.management.game_manager import GameManager
from pycatan.players.human_user import HumanUser
from pycatan.management.actions import GamePhase, Action, ActionType
from pycatan.core.card import DevCard

print("Knight Card Test - Invalid Steal")
print("="*50)

# Create simple game
users = [HumanUser("Alice", 0), HumanUser("Bob", 1)]
gm = GameManager(users)
game = gm.game

# Setup
gm._is_running = True
gm._current_player_id = 1
gm._current_game_state.game_phase = GamePhase.NORMAL_PLAY
gm._current_game_state.current_player = 1
gm._current_game_state.dice_rolled = True

# Give Bob a Knight card
game.players[1].add_dev_card(DevCard.Knight)

print(f"Initial robber: {game.board.robber}")

# Execute Knight - move to tile 5 and try to steal from Alice
# (who has no settlements there)
from pycatan.config.board_definition import board_definition
coords = board_definition.hex_id_to_game_coords(5)
print(f"Moving to tile 5 (coords: {coords})")
print(f"Trying to steal from Alice (who has no settlements there)")

action = Action(ActionType.USE_DEV_CARD, 1, {
    'card_type': 'Knight',
    'tile_coords': coords,
    'victim_id': 0  # Try to steal from Alice
})

print("\nExecuting Knight card...")
result = gm.execute_action(action)

print(f"\nResult: {result.success}")
if not result.success:
    print(f"Error: {result.error_message}")
    print("\nThis is EXPECTED - Alice has no settlements near tile 5!")
print(f"Robber position: {game.board.robber}")
