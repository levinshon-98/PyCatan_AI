"""
Test script for city building functionality.
"""
from pycatan import Game
from pycatan.card import ResCard

# Create game with 3 players
game = Game(num_of_players=3)
board = game.board

print("Testing City Building...")
print("=" * 60)

# Setup: Add a settlement for player 0
point = board.points[0][0]
print(f"\n1. Adding settlement at point [0][0] for player 0...")
status = game.add_settlement(player=0, point=point, is_starting=True)
print(f"   Result: {status}")

# Give player resources for city (3 Ore, 2 Wheat)
print(f"\n2. Giving player 0 resources for city (3 Ore, 2 Wheat)...")
needed_cards = [
    ResCard.Ore,
    ResCard.Ore,
    ResCard.Ore,
    ResCard.Wheat,
    ResCard.Wheat
]
game.players[0].add_cards(needed_cards)
print(f"   Player 0 cards: {[str(c) for c in game.players[0].cards]}")

# Try to build a city
print(f"\n3. Upgrading settlement to city at point [0][0]...")
status = game.add_city(point=point, player=0)
print(f"   Result: {status}")

# Check victory points
print(f"\n4. Checking player 0 victory points...")
vp = game.players[0].get_VP()
print(f"   Victory Points: {vp}")

# Check the building type
print(f"\n5. Checking building at point [0][0]...")
building = point.building
if building:
    print(f"   Building type: {building.type}")
    print(f"   Building owner: {building.owner}")
else:
    print(f"   No building found!")

print("\n" + "=" * 60)
print("Test complete!")
