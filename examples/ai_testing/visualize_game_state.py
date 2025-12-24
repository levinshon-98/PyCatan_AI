"""
Visualize Game State for AI Testing
------------------------------------
This script creates a specific game state and displays it using Web Visualizer.
It also prints all the JSON data that would be sent to an AI agent.

Usage:
    python visualize_game_state.py [--state-file STATE_FILE]
    
    If STATE_FILE is not provided, uses a default test state.
"""

import sys
import json
import time
import threading
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pycatan.core.game import Game
from pycatan.management.actions import GameState, PlayerState, BoardState, GamePhase, TurnPhase
from pycatan.visualizations.web_visualization import WebVisualization
from pycatan.core.card import ResCard, DevCard
from pycatan.core.building import Building


class GameStateCapture:
    """Captures and displays all JSON data sent to Web Visualizer."""
    
    def __init__(self, web_viz):
        self.web_viz = web_viz
        self.captured_states = []
        self.captured_events = []
        
    def capture_state_update(self, game_state):
        """Capture and print game state JSON."""
        print("\n" + "="*80)
        print("📊 GAME STATE JSON (This is what the AI would receive)")
        print("="*80)
        
        # Convert to web format (same as what web visualizer does)
        web_format = self.web_viz._convert_game_state(game_state)
        
        # Print formatted JSON
        json_str = json.dumps(web_format, indent=2, ensure_ascii=False)
        print(json_str)
        
        print("\n" + "="*80)
        print("📈 SUMMARY")
        print("="*80)
        self._print_summary(web_format)
        
        self.captured_states.append(web_format)
        return web_format
        
    def _print_summary(self, state_data):
        """Print a human-readable summary of the game state."""
        print(f"Current Player: {state_data.get('current_player', 0)}")
        print(f"Game Phase: {state_data.get('current_phase', 'UNKNOWN')}")
        print(f"Robber Position: {state_data.get('robber_position', 'Unknown')}")
        
        if state_data.get('dice_result'):
            print(f"Last Dice Roll: {state_data['dice_result']}")
        
        print(f"\nBoard:")
        print(f"  - Hexes: {len(state_data.get('hexes', []))}")
        print(f"  - Settlements: {len(state_data.get('settlements', []))}")
        print(f"  - Cities: {len(state_data.get('cities', []))}")
        print(f"  - Roads: {len(state_data.get('roads', []))}")
        
        print(f"\nPlayers: {len(state_data.get('players', []))}")
        for player in state_data.get('players', []):
            print(f"  Player {player.get('id', '?')}: {player.get('name', 'Unknown')}")
            print(f"    - Victory Points: {player.get('victory_points', 0)}")
            print(f"    - Resources: {len(player.get('cards', []))}")
            print(f"    - Dev Cards: {len(player.get('dev_cards', []))}")
            if player.get('has_longest_road'):
                print(f"    - Has Longest Road!")
            if player.get('has_largest_army'):
                print(f"    - Has Largest Army!")


def create_test_game_state():
    """
    Create a test game state with some buildings and resources.
    This simulates a game in progress.
    """
    print("\n🎮 Creating test game state...")
    
    # Create a real game to get proper board structure
    game = Game(num_of_players=3)
    
    # Build some structures for testing
    # Player 0 (Red) - settlements and roads
    point1 = game.board.points[0][0]  # Top left
    point2 = game.board.points[1][0]  # Below it
    
    # Starting phase - build without resources
    game.add_settlement(0, point1, is_starting=True)
    game.add_road(0, point1, point2, is_starting=True)
    
    # Player 1 (Blue)
    point4 = game.board.points[2][2]
    point5 = game.board.points[3][2]
    game.add_settlement(1, point4, is_starting=True)
    game.add_road(1, point4, point5, is_starting=True)
    
    # Player 2 (Green)  
    point6 = game.board.points[4][3]
    point7 = game.board.points[5][3]
    game.add_settlement(2, point6, is_starting=True)
    game.add_road(2, point6, point7, is_starting=True)
    
    # Second round of starting placements
    game.add_settlement(2, game.board.points[1][3], is_starting=True)
    game.add_road(2, game.board.points[1][3], game.board.points[2][3], is_starting=True)
    
    game.add_settlement(1, game.board.points[2][1], is_starting=True)
    game.add_road(1, game.board.points[2][1], game.board.points[3][1], is_starting=True)
    
    game.add_settlement(0, game.board.points[4][1], is_starting=True)
    game.add_road(0, game.board.points[4][1], game.board.points[5][1], is_starting=True)
    
    # Give players some resources
    game.players[0].cards[ResCard.Wood] = 3
    game.players[0].cards[ResCard.Brick] = 2
    game.players[0].cards[ResCard.Wheat] = 2
    game.players[0].cards[ResCard.Ore] = 1
    
    game.players[1].cards[ResCard.Sheep] = 4
    game.players[1].cards[ResCard.Wheat] = 1
    game.players[1].cards[ResCard.Ore] = 2
    
    game.players[2].cards[ResCard.Wood] = 2
    game.players[2].cards[ResCard.Brick] = 3
    game.players[2].cards[ResCard.Sheep] = 1
    
    # Give player 0 some development cards
    game.players[0].dev_cards[DevCard.Knight] = 2
    game.players[0].dev_cards[DevCard.VictoryPoint] = 1
    game.players[0].knights_played = 1
    
    # Position robber on a tile
    game.board.robber = game.board.tiles[2][1]  # Move to a different tile
    
    print("✅ Test game state created!")
    print(f"   - 3 Players")
    print(f"   - 6 Settlements placed")
    print(f"   - 6 Roads built")
    print(f"   - Resources distributed")
    print(f"   - Robber positioned")
    
    return game


def game_to_game_state(game: Game) -> GameState:
    """
    Convert a Game object to a GameState object for visualization.
    """
    # Create board state
    tiles = []
    for row_idx, row in enumerate(game.board.tiles):
        for col_idx, tile in enumerate(row):
            if tile:  # Skip None tiles
                tiles.append({
                    'coords': [row_idx, col_idx],
                    'type': tile.tile_type.name if tile.tile_type else 'DESERT',
                    'number': tile.number if hasattr(tile, 'number') else None,
                    'has_robber': tile == game.board.robber
                })
    
    # Create buildings dictionary
    buildings = {}
    for row in game.board.points:
        for point in row:
            if point.building:
                coords = tuple([point.row, point.index])
                building_type_name = "SETTLEMENT" if point.building.type == Building.BUILDING_SETTLEMENT else \
                                    "CITY" if point.building.type == Building.BUILDING_CITY else "UNKNOWN"
                buildings[coords] = {
                    'type': building_type_name,
                    'owner': point.building.owner
                }
    
    # Create roads list
    roads = []
    for player in game.players:
        for road in player.roads:
            roads.append({
                'start': [road.start.row, road.start.index],
                'end': [road.end.row, road.end.index],
                'owner': road.owner
            })
    
    # Find robber position
    robber_pos = (0, 0)
    if game.board.robber:
        robber_pos = (game.board.robber.row, game.board.robber.index)
    
    board_state = BoardState(
        tiles=tiles,
        robber_position=robber_pos,
        harbors=[],  # Can be added if needed
        buildings=buildings,
        roads=roads
    )
    
    # Create player states
    players_state = []
    for player in game.players:
        # Convert cards to list of strings
        cards = []
        for card_type, count in player.cards.items():
            cards.extend([card_type.name] * count)
        
        dev_cards = []
        for card_type, count in player.dev_cards.items():
            dev_cards.extend([card_type.name] * count)
        
        # Get settlements and cities
        settlements = []
        cities = []
        for row in game.board.points:
            for point in row:
                if point.building and point.building.owner == player.player_num:
                    coords = (point.row, point.index)
                    if point.building.type == Building.BUILDING_SETTLEMENT:
                        settlements.append(coords)
                    elif point.building.type == Building.BUILDING_CITY:
                        cities.append(coords)
        
        # Get roads (as tuples of start, end)
        roads_list = []
        for road in player.roads:
            roads_list.append(((road.start.row, road.start.index),
                              (road.end.row, road.end.index)))
        
        player_state = PlayerState(
            player_id=player.player_num,
            name=f"Player {player.player_num}",
            cards=cards,
            dev_cards=dev_cards,
            settlements=settlements,
            cities=cities,
            roads=roads_list,
            victory_points=player.victory_points,
            longest_road_length=player.longest_road_length,
            has_longest_road=player.has_longest_road,
            has_largest_army=player.has_largest_army,
            knights_played=player.knights_played
        )
        players_state.append(player_state)
    
    # Create full game state
    game_state = GameState(
        game_id="test_game",
        turn_number=5,
        current_player=0,
        game_phase=GamePhase.NORMAL_PLAY,
        turn_phase=TurnPhase.PLAYER_ACTIONS,
        board_state=board_state,
        players_state=players_state,
        dice_rolled=(4, 3)  # Example dice roll
    )
    
    return game_state


def load_game_state_from_file(filepath: str) -> GameState:
    """
    Load a game state from a JSON file.
    
    Args:
        filepath: Path to JSON file containing game state
        
    Returns:
        GameState object
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Reconstruct GameState from JSON
    # This is a simplified version - may need expansion
    board_state = BoardState(**data['board_state'])
    players_state = [PlayerState(**p) for p in data['players_state']]
    
    game_state = GameState(
        game_id=data.get('game_id', 'loaded_game'),
        turn_number=data.get('turn_number', 0),
        current_player=data.get('current_player', 0),
        game_phase=GamePhase[data.get('game_phase', 'NORMAL_PLAY')],
        turn_phase=TurnPhase[data.get('turn_phase', 'PLAYER_ACTIONS')],
        board_state=board_state,
        players_state=players_state,
        dice_rolled=tuple(data['dice_rolled']) if data.get('dice_rolled') else None
    )
    
    return game_state


def main():
    """Main function to visualize game state."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Visualize game state for AI testing')
    parser.add_argument('--state-file', type=str, help='Path to game state JSON file')
    parser.add_argument('--port', type=int, default=5000, help='Port for web server')
    parser.add_argument('--no-browser', action='store_true', help='Don\'t open browser automatically')
    
    args = parser.parse_args()
    
    # Create or load game state
    if args.state_file:
        print(f"\n📂 Loading game state from: {args.state_file}")
        game_state = load_game_state_from_file(args.state_file)
    else:
        print("\n🎲 Using default test game state...")
        game = create_test_game_state()
        game_state = game_to_game_state(game)
    
    # Create web visualization
    print(f"\n🌐 Starting Web Visualizer on port {args.port}...")
    web_viz = WebVisualization(port=args.port, auto_open=not args.no_browser)
    
    # Create capture wrapper
    capture = GameStateCapture(web_viz)
    
    # Capture and print the JSON
    web_format = capture.capture_state_update(game_state)
    
    # Update the visualization
    web_viz.update_full_state(game_state)
    
    # Start the web server in a separate thread
    def run_server():
        web_viz.start()
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait a moment for server to start
    time.sleep(1)
    
    print("\n" + "="*80)
    print("🎮 WEB VISUALIZER RUNNING")
    print("="*80)
    print(f"URL: http://localhost:{args.port}")
    print("\nThe game state is now visible in your browser.")
    print("The JSON data above is what an AI agent would receive.")
    print("\nPress Ctrl+C to stop the server.")
    print("="*80)
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")


if __name__ == '__main__':
    main()
