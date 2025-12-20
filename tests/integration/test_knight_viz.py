"""
Test Knight card with visualization logs
"""
from pycatan import Game
from pycatan.core.card import DevCard, ResCard
from pycatan.config.board_definition import board_definition
from pycatan.management.actions import GamePhase
from pycatan.core.statuses import Statuses
from pycatan.management.game_manager import GameManager
from pycatan.players.human_user import HumanUser
from pycatan.visualizations.console_visualization import ConsoleVisualization

def test_knight_with_visualizations():
    """Test that Knight card logs appear in visualizations."""
    print("\n" + "="*60)
    print("Testing Knight Card with Visualization Logs")
    print("="*60)
    
    # Create users
    users = [HumanUser("Alice", 0), HumanUser("Bob", 1), HumanUser("Charlie", 2)]
    
    # Create console visualization
    console_viz = ConsoleVisualization()
    
    # Create game manager
    gm = GameManager(users=users)
    
    # Setup visualization manager
    from pycatan.visualizations.visualization import VisualizationManager
    gm.visualization_manager = VisualizationManager()
    gm.visualization_manager.add_visualization(console_viz)
    
    # Setup game manually
    gm.game.game_phase = GamePhase.NORMAL_PLAY
    
    # Give player 0 (Alice) a Knight card
    gm.game.players[0].add_dev_card(DevCard.Knight)
    
    # Give player 1 (Bob) some resource cards
    gm.game.players[1].add_cards([ResCard.Wheat, ResCard.Wood, ResCard.Brick])
    
    # Add a settlement for player 1 at a point adjacent to tile 5
    tile = gm.game.board.tiles[1][1]  # Tile 5 is at (1,1)
    if tile.points:
        settlement_point = tile.points[0]
        gm.game.add_settlement(player=1, point=settlement_point, is_starting=True)
        
        print(f"\n✓ Game setup complete")
        print(f"  - Alice has {len(gm.game.players[0].dev_cards)} Knight card")
        print(f"  - Bob has {len(gm.game.players[1].cards)} resource cards")
        
        # Create Knight action directly
        from pycatan.management.actions import Action, ActionType
        
        knight_action = Action(
            action_type=ActionType.USE_DEV_CARD,
            player_id=0,
            parameters={
                'card_type': DevCard.Knight,
                'tile_id': 5,
                'victim_name': 'Bob'
            }
        )
        
        print(f"\n🧪 Executing Knight card action...")
        print(f"   This should send logs to the visualization\n")
        
        # Execute through GameManager
        result = gm._use_knight_card(knight_action)
        
        if result.success:
            print(f"\n✅ Knight card executed successfully!")
            print(f"   Logs should have been displayed above with:")
            print(f"   1. ⚔️ Knight card used message")
            print(f"   2. 🎯 Card stolen message (with card type)")
        else:
            print(f"❌ Failed: {result.error_message}")
    else:
        print("❌ Could not find points on tile")
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)

if __name__ == "__main__":
    test_knight_with_visualizations()
