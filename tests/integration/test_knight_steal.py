"""
Test Knight card with stolen card display
"""
from pycatan import Game
from pycatan.core.card import DevCard, ResCard
from pycatan.config.board_definition import board_definition
from pycatan.management.actions import GamePhase
from pycatan.core.statuses import Statuses

def test_knight_with_steal():
    """Test that Knight card shows which card was stolen."""
    print("\n" + "="*60)
    print("Testing Knight Card with Card Steal")
    print("="*60)
    
    # Create game with 3 players
    game = Game(num_of_players=3)
    game.game_phase = GamePhase.NORMAL_PLAY
    
    # Give player 0 a Knight card
    game.players[0].add_dev_card(DevCard.Knight)
    
    # Give player 1 some resource cards
    game.players[1].add_cards([ResCard.Wheat, ResCard.Wood, ResCard.Brick])
    
    # Add a settlement for player 1 at a point adjacent to tile 5
    # This allows player 0 to steal from player 1
    # Tile 5 is at game coords (1,1)
    
    # Get a point adjacent to tile (1,1)
    tile = game.board.tiles[1][1]
    if tile.points:
        settlement_point = tile.points[0]
        # Use game.add_settlement instead of player.add_settlement
        game.add_settlement(player=1, point=settlement_point, is_starting=True)
        print(f"\n✓ Game setup complete")
        print(f"  - Player 0: {len(game.players[0].dev_cards)} Knight card")
        print(f"  - Player 1: {len(game.players[1].cards)} resource cards, 1 settlement")
        print(f"  - Player 1's cards: {[card.value for card in game.players[1].cards]}")
        
        # Test using Knight card on tile 5 and stealing from player 1
        print(f"\n🧪 Testing Knight card with steal...")
        
        args = {
            'robber_pos': [1, 1],
            'victim': 1
        }
        
        print(f"📢 Using Knight card to move robber to tile 5 and steal from Player 1")
        
        # Record player 1's card count before
        cards_before = len(game.players[1].cards)
        
        # Execute
        status = game.use_dev_card(0, DevCard.Knight, args)
        
        if status == Statuses.ALL_GOOD:
            cards_after = len(game.players[1].cards)
            stolen = cards_before - cards_after
            
            print(f"\n✅ Knight card used successfully!")
            print(f"  - Robber moved to tile 5 (coords [1, 1])")
            print(f"  - Player 1 had {cards_before} cards, now has {cards_after}")
            print(f"  - {stolen} card was stolen")
            print(f"  - Player 0 knights: {game.players[0].knight_cards}")
            
            # Check if stolen card info is in args
            if 'stolen_card' in args:
                card = args['stolen_card']
                print(f"\n✨ Stolen card: {card.value}")
                print(f"   Message should show: '🎯 Player 0 stole {card.value} from Player 1!'")
            else:
                print(f"\n⚠️ No stolen card info found in args")
        else:
            print(f"❌ Failed with status: {status}")
    else:
        print("❌ Could not find points on tile")
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)

if __name__ == "__main__":
    test_knight_with_steal()
