"""
Test Knight card implementation
"""
from pycatan import Game
from pycatan.card import DevCard, ResCard
from pycatan.actions import GamePhase

def test_knight_card_basic():
    """Test basic Knight card usage."""
    print("\n" + "="*60)
    print("Testing Knight Card Implementation")
    print("="*60)
    
    # Create a simple game
    game = Game(num_of_players=3)
    game.game_phase = GamePhase.NORMAL_PLAY
    
    # Give player 0 a Knight card
    game.players[0].add_dev_card(DevCard.Knight)
    
    print("\n✓ Game setup complete")
    print(f"  - Player 0 has {len(game.players[0].dev_cards)} dev card(s)")
    print(f"  - Initial robber position: {game.board.robber}")
    
    # Test Knight card usage
    print("\n🧪 Testing Knight card usage...")
    
    # Use Knight card on tile [2, 1], no victim
    args = {
        'robber_pos': [2, 1],
        'victim': None
    }
    
    print(f"  - Player 0 uses Knight card on tile [2, 1]")
    
    status = game.use_dev_card(0, DevCard.Knight, args)
    
    from pycatan.statuses import Statuses
    if status == Statuses.ALL_GOOD:
        print("  ✓ Knight card used successfully!")
        print(f"  - New robber position: {game.board.robber}")
        print(f"  - Player 0 now has {game.players[0].knight_cards} knight(s)")
        
        # Check Largest Army
        if game.largest_army is not None:
            print(f"  - Largest Army: Player {game.largest_army} ({game.players[game.largest_army].knight_cards} knights)")
        
        # Test with 3 knights to get Largest Army
        print("\n🧪 Testing Largest Army achievement...")
        game.players[0].add_dev_card(DevCard.Knight)
        game.players[0].add_dev_card(DevCard.Knight)
        
        # Use second knight
        args['robber_pos'] = [1, 0]
        status = game.use_dev_card(0, DevCard.Knight, args)
        print(f"  - After 2nd knight: {game.players[0].knight_cards} knights")
        
        # Use third knight
        args['robber_pos'] = [2, 0]
        status = game.use_dev_card(0, DevCard.Knight, args)
        print(f"  - After 3rd knight: {game.players[0].knight_cards} knights")
        
        if game.largest_army == 0:
            print(f"  ✓ Player 0 got Largest Army! (+2 VP)")
        
    else:
        print(f"  ✗ Failed with status: {status}")
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)

if __name__ == "__main__":
    test_knight_card_basic()
