"""Quick test to check dice logging"""

from pycatan import Game, GameManager, HumanUser, WebVisualization, ConsoleVisualization
from pycatan.actions import ActionType, Action

# Create a simple game
users = [HumanUser("Alice"), HumanUser("Bob"), HumanUser("Charlie")]
viz = ConsoleVisualization(use_colors=False)
manager = GameManager(users, [viz])

# Start game
manager.start_game()

# Create a roll dice action
action = Action(
    action_type=ActionType.ROLL_DICE,
    player_id=0,
    parameters={}
)

# Execute it
result = manager.execute_action(action)

print("\n=== Action Parameters After Execution ===")
print(f"Parameters: {action.parameters}")
print(f"Dice: {action.parameters.get('dice', 'NOT FOUND')}")
print(f"Total: {action.parameters.get('total', 'NOT FOUND')}")
