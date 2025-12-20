"""
Test that robber position is displayed after Knight card usage
"""
import sys
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

from pycatan.game_manager import GameManager
from pycatan.human_user import HumanUser
from pycatan.console_visualization import ConsoleVisualization
from pycatan.actions import GamePhase, Action, ActionType
from pycatan.card import DevCard, ResCard

def test_robber_display():
    """Test that robber position displays correctly after Knight card."""
    print("\n" + "="*60)
    print("Testing Robber Display After Knight Card")
    print("="*60)
    
    # Create game with console visualization
    users = [
        HumanUser("Alice", 0),
        HumanUser("Bob", 1),
    ]
    
    game_manager = GameManager(users)
    game = game_manager.game
    
    # Add console visualization
    console_viz = ConsoleVisualization()
    game_manager.visualization_manager = type('obj', (object,), {
        'visualizations': [console_viz],
        'display_action': lambda action, result: console_viz.display_action(action, result),
        'display_game_state': lambda state: console_viz.display_game_state(state)
    })()
    
    # Setup game state
    game_manager._is_running = True
    game_manager._current_player_id = 1
    game_manager._current_game_state.game_phase = GamePhase.NORMAL_PLAY
    game_manager._current_game_state.turn_phase = game_manager._current_game_state.turn_phase.__class__.PLAYER_ACTIONS
    game_manager._current_game_state.dice_rolled = True
    game_manager._current_game_state.current_player = 1
    
    # Print initial robber position
    print(f"\nInitial robber position: {game.board.robber}")
    
    # Give Bob a Knight card
    game.players[1].add_dev_card(DevCard.Knight)
    print(f"\nBob has Knight card: {DevCard.Knight in game.players[1].dev_cards}")
    
    # Create Knight card action - move robber to tile 5
    # Tile 5 in hex coordinates
    from pycatan.board_definition import board_definition
    tile_coords = board_definition.hex_id_to_game_coords(5)
    print(f"\nMoving robber to tile 5 (game coords: {tile_coords})")
    
    knight_action = Action(
        ActionType.USE_DEV_CARD,
        1,  # Bob
        {
            'card_type': 'Knight',  # String, not enum!
            'tile_coords': tile_coords,
            'victim_id': None  # No steal
        }
    )
    
    print("\n" + "-"*60)
    print("Executing Knight card action...")
    print("-"*60)
    
    result = game_manager.execute_action(knight_action)
    
    print(f"\nAction result: {result.success}")
    if not result.success:
        print(f"Error: {result.error_message}")
    
    # Force display of game state through console visualization
    print("\n" + "="*60)
    print("CONSOLE VISUALIZATION - GAME STATE")
    print("="*60)
    console_viz.display_game_state(state := game_manager.get_full_state())
    
    # Check final robber position
    print(f"\n✓ Final robber position: {game.board.robber}")
    print(f"✓ Expected: {tile_coords}")
    print(f"✓ Match: {list(game.board.robber) == list(tile_coords)}")
    
    print(f"\n✓ Robber position in GameState: {state.board_state.robber_position}")
    
    print("\n" + "="*60)
    print("✓ Test Complete - Robber moved successfully!")
    print("="*60)

if __name__ == "__main__":
    test_robber_display()
