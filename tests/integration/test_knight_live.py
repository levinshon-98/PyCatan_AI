"""
Test Knight card in a live game scenario
"""
import sys
import os

# Disable emoji errors for Windows console
os.environ['PYTHONIOENCODING'] = 'utf-8'

from pycatan.management.game_manager import GameManager
from pycatan.players.human_user import HumanUser
from pycatan.management.actions import GamePhase, Action, ActionType
from pycatan.core.card import DevCard, ResCard

def test_knight_live():
    """Test Knight card purchase and usage."""
    print("\n" + "="*60)
    print("Testing Knight Card - Live Scenario")
    print("="*60)
    
    # Create game
    users = [
        HumanUser("Alice", 0),
        HumanUser("Bob", 1),
        HumanUser("Charlie", 2)
    ]
    
    game_manager = GameManager(users)
    game = game_manager.game
    
    # Start the game
    game_manager._is_running = True
    game_manager._current_player_id = 1  # Bob's turn
    
    # Setup game state
    game.game_phase = GamePhase.NORMAL_PLAY
    game_manager._current_game_state.game_phase = GamePhase.NORMAL_PLAY
    game_manager._current_game_state.turn_phase = game_manager._current_game_state.turn_phase.__class__.PLAYER_ACTIONS
    game_manager._current_game_state.dice_rolled = True
    
    # Give Bob resources to buy dev card
    game.players[1].add_cards([ResCard.Ore, ResCard.Sheep, ResCard.Wheat])
    
    print("\nStep 1: Bob buys a dev card")
    print(f"  - Bob's cards before: {len(game.players[1].cards)} resource cards")
    print(f"  - Bob's dev cards before: {len(game.players[1].dev_cards)}")
    
    # Buy dev card
    buy_action = Action(ActionType.BUY_DEV_CARD, 1, {})
    result = game_manager.execute_action(buy_action)
    
    print(f"  - Buy result: {result.success}")
    if result.success:
        print(f"  - Bob's cards after: {len(game.players[1].cards)} resource cards")
        print(f"  - Bob's dev cards after: {len(game.players[1].dev_cards)}")
        print(f"  - Dev cards: {[card.name for card in game.players[1].dev_cards]}")
    else:
        print(f"  - Error: {result.error_message if hasattr(result, 'error_message') else 'Unknown'}")
        return
    
    # Check if Bob got a Knight
    has_knight = any(card == DevCard.Knight for card in game.players[1].dev_cards)
    print(f"  - Has Knight: {has_knight}")
    
    if not has_knight:
        print("\n  Bob didn't get a Knight card. Adding one manually for testing...")
        game.players[1].add_dev_card(DevCard.Knight)
    
    print("\nStep 2: Bob tries to use Knight card")
    print(f"  - Current robber position: {game.board.robber}")
    
    # Try to use Knight on tile 5
    from pycatan.config.board_definition import board_definition
    tile_coords = board_definition.hex_id_to_game_coords(5)
    
    print(f"  - Tile 5 = {tile_coords}")
    
    knight_action = Action(
        ActionType.USE_DEV_CARD,
        1,
        {
            'card_type': 'Knight',
            'tile_coords': tile_coords,
            'victim_id': None
        }
    )
    
    print(f"  - Executing Knight action...")
    result = game_manager.execute_action(knight_action)
    
    print(f"\nStep 3: Results")
    print(f"  - Success: {result.success if result else 'No result'}")
    if result and not result.success:
        print(f"  - Error: {result.error_message if hasattr(result, 'error_message') else 'Unknown'}")
        print(f"  - Error code: {result.error_code if hasattr(result, 'error_code') else 'Unknown'}")
    
    print(f"  - Robber position after: {game.board.robber}")
    print(f"  - Bob's dev cards after: {[card.name for card in game.players[1].dev_cards]}")
    print(f"  - Bob's knight count: {game.players[1].knight_cards}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    test_knight_live()
