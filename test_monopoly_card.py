"""Test script for Monopoly card functionality."""

from pycatan import Game
from pycatan.card import ResCard, DevCard
from pycatan.statuses import Statuses

def test_monopoly_card():
    """Test Monopoly card - take all cards of one resource."""
    print("Testing Monopoly card functionality")
    print("=" * 60)
    
    # Create game with 3 players
    game = Game(num_of_players=3)
    board = game.board
    
    # Setup Phase - give players starting positions (minimal setup)
    print("\n1. Setting up game...")
    
    # Player 0
    game.add_settlement(player=0, point=board.points[0][0], is_starting=True)
    game.add_road(player=0, start=board.points[0][0], end=board.points[0][1], is_starting=True)
    game.add_settlement(player=0, point=board.points[1][2], is_starting=True)
    game.add_road(player=0, start=board.points[1][2], end=board.points[1][3], is_starting=True)
    
    # Player 1
    game.add_settlement(player=1, point=board.points[2][0], is_starting=True)
    game.add_road(player=1, start=board.points[2][0], end=board.points[2][1], is_starting=True)
    game.add_settlement(player=1, point=board.points[3][2], is_starting=True)
    game.add_road(player=1, start=board.points[3][2], end=board.points[3][3], is_starting=True)
    
    # Player 2
    game.add_settlement(player=2, point=board.points[4][0], is_starting=True)
    game.add_road(player=2, start=board.points[4][0], end=board.points[4][1], is_starting=True)
    game.add_settlement(player=2, point=board.points[5][2], is_starting=True)
    game.add_road(player=2, start=board.points[5][2], end=board.points[5][3], is_starting=True)
    
    print("✓ Setup phase complete")
    
    # Give players some wood cards
    print("\n2. Giving players wood cards...")
    game.players[0].add_cards([ResCard.Wood])  # Player 0: 1 wood
    game.players[1].add_cards([ResCard.Wood, ResCard.Wood, ResCard.Wood])  # Player 1: 3 wood
    game.players[2].add_cards([ResCard.Wood, ResCard.Wood])  # Player 2: 2 wood
    
    print(f"   Player 0: {game.players[0].cards.count(ResCard.Wood)} wood cards")
    print(f"   Player 1: {game.players[1].cards.count(ResCard.Wood)} wood cards")
    print(f"   Player 2: {game.players[2].cards.count(ResCard.Wood)} wood cards")
    print(f"   Total wood in game: {sum(p.cards.count(ResCard.Wood) for p in game.players)}")
    
    # Give Player 0 a Monopoly card
    print("\n3. Giving Player 0 a Monopoly card...")
    game.players[0].add_cards([DevCard.Monopoly])
    print(f"✓ Player 0 has {game.players[0].dev_cards.count(DevCard.Monopoly)} Monopoly card")
    
    # Player 0 uses Monopoly to take all wood
    print("\n4. Player 0 uses Monopoly card to take all wood...")
    status = game.use_dev_card(
        player=0,
        card=DevCard.Monopoly,
        args={'card_type': ResCard.Wood}
    )
    
    if status == Statuses.ALL_GOOD:
        print("✓ Monopoly card used successfully!")
    else:
        print(f"✗ Error: {status}")
        return False
    
    # Check results
    print("\n5. Checking results after Monopoly...")
    player0_wood = game.players[0].cards.count(ResCard.Wood)
    player1_wood = game.players[1].cards.count(ResCard.Wood)
    player2_wood = game.players[2].cards.count(ResCard.Wood)
    
    print(f"   Player 0: {player0_wood} wood cards (should be 6)")
    print(f"   Player 1: {player1_wood} wood cards (should be 0)")
    print(f"   Player 2: {player2_wood} wood cards (should be 0)")
    
    # Verify
    if player0_wood == 6 and player1_wood == 0 and player2_wood == 0:
        print("\n✅ TEST PASSED! Monopoly card works correctly!")
        print("   Player 0 successfully took all 5 wood cards from other players")
        print("   (1 + 3 + 2 = 6 total)")
        return True
    else:
        print("\n❌ TEST FAILED! Card counts don't match expected values")
        return False

if __name__ == "__main__":
    success = test_monopoly_card()
    exit(0 if success else 1)
