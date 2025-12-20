"""
Quick test for Road Building card functionality
"""
from pycatan import Game
from pycatan.core.card import DevCard
from pycatan.management.game_manager import GameManager
from pycatan.players.human_user import HumanUser
from pycatan.management.actions import ActionType

# Create a simple game
game = Game(num_of_players=3)
users = [
    HumanUser("Alice", 0),
    HumanUser("Bob", 1),
    HumanUser("Charlie", 2)
]

# Create GameManager
gm = GameManager(users)
gm.game = game

# Give player 0 a Road Building card for testing
game.players[0].add_dev_card(DevCard.Road)

print(f"Player 0 has {len(game.players[0].dev_cards)} dev cards")
print(f"Dev cards: {game.players[0].dev_cards}")

# Test parsing the command
user = users[0]
game_state = gm.get_full_state()

# Test 1: Just "use road" without roads - should fail with helpful message
print("\n=== Test 1: use road (without roads) ===")
try:
    action = user._parse_input("use road", game_state)
    print(f"Action created: {action}")
except Exception as e:
    print(f"Expected error: {e}")

# Test 2: Full command with both roads
print("\n=== Test 2: use road rd 10 11 rd 12 13 ===")
try:
    action = user._parse_input("use road rd 10 11 rd 12 13", game_state)
    print(f"Action type: {action.action_type}")
    print(f"Card type: {action.parameters.get('card_type')}")
    print(f"Has road_one_coords: {'road_one_coords' in action.parameters}")
    print(f"Has road_two_coords: {'road_two_coords' in action.parameters}")
    if 'road_one_coords' in action.parameters:
        print(f"Road 1 coords: {action.parameters['road_one_coords']}")
    if 'road_two_coords' in action.parameters:
        print(f"Road 2 coords: {action.parameters['road_two_coords']}")
except Exception as e:
    print(f"Error: {e}")

print("\n✅ Parsing test complete!")
