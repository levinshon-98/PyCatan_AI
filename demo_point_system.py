"""
Interactive demo showing how users can work with point IDs.

This demonstrates the new simplified interface where users work
with point IDs (1-54) instead of complex coordinates.
"""

from pycatan import Game, board_definition
from pycatan.statuses import Statuses

def print_board_info():
    """Print basic board information."""
    print("🎮 Catan Board Information")
    print("=" * 40)
    print(f"📍 Points available: 1-{len(board_definition.get_all_point_ids())}")
    print(f"⬢ Hexes on board: {len(board_definition.get_all_hex_ids())}")
    print()

def show_point_examples():
    """Show examples of working with points."""
    print("📍 Point Examples:")
    print("-" * 20)
    
    # Show some corner and edge points
    example_points = [1, 7, 8, 16, 46, 54]  # Corner and edge points
    
    for point_id in example_points:
        coords = board_definition.point_id_to_game_coords(point_id)
        adjacent = board_definition.get_adjacent_point_ids(point_id)
        hexes = board_definition.get_adjacent_hex_ids(point_id)
        
        print(f"Point {point_id:2d}: connects to points {adjacent}, touches {len(hexes)} hexes")
    
    print()

def demonstrate_road_building():
    """Demonstrate road building validation."""
    print("🛤️  Road Building Examples:")
    print("-" * 30)
    
    # Valid road connections
    valid_roads = [
        (1, 2),    # Adjacent corner points
        (10, 11),  # Adjacent edge points  
        (25, 26),  # Adjacent middle points
        (25, 36),  # Vertical connection
    ]
    
    invalid_roads = [
        (1, 54),   # Opposite corners
        (1, 10),   # Non-adjacent
        (25, 30),  # Non-adjacent
    ]
    
    print("Valid roads:")
    for start, end in valid_roads:
        is_valid = board_definition.is_valid_road_placement(start, end)
        print(f"  Point {start:2d} -> Point {end:2d}: {'✓' if is_valid else '✗'}")
    
    print("\nInvalid roads:")
    for start, end in invalid_roads:
        is_valid = board_definition.is_valid_road_placement(start, end)
        print(f"  Point {start:2d} -> Point {end:2d}: {'✓' if is_valid else '✗'}")
    
    print()

def simulate_game_moves():
    """Simulate some game moves using point IDs."""
    print("🎯 Simulated Game Moves:")
    print("-" * 25)
    
    # Create game
    game = Game(num_of_players=2)
    
    # Show how a user would build settlements and roads
    print("Player 0 builds settlement at point 1:")
    print(f"  Command: game.add_settlement(player=0, point=board.points[0][0], is_starting=True)")
    
    # Convert point ID to actual point for game
    point_coords = board_definition.point_id_to_game_coords(1)
    if point_coords:
        point = game.board.points[point_coords[0]][point_coords[1]]
        result = game.add_settlement(player=0, point=point, is_starting=True)
        print(f"  Result: {result}")
    
    print("\nPlayer 0 builds road from point 1 to point 2:")
    # Build road between adjacent points
    start_coords = board_definition.point_id_to_game_coords(1)
    end_coords = board_definition.point_id_to_game_coords(2)
    
    if start_coords and end_coords:
        start_point = game.board.points[start_coords[0]][start_coords[1]]
        end_point = game.board.points[end_coords[0]][end_coords[1]]
        result = game.add_road(player=0, start=start_point, end=end_point, is_starting=True)
        print(f"  Result: {result}")
    
    print("\nCurrent game state:")
    state = game.get_full_state()
    print(f"  Buildings: {len(state.board_state.buildings)}")
    print(f"  Roads: {len(state.board_state.roads)}")
    
    if state.board_state.buildings:
        for point_id, building_info in state.board_state.buildings.items():
            print(f"    {building_info['type'].title()} at point {point_id} (owner: Player {building_info['owner']})")
    
    if state.board_state.roads:
        for road_info in state.board_state.roads:
            print(f"    Road from point {road_info['start_point_id']} to {road_info['end_point_id']} (owner: Player {road_info['owner']})")
    
    print()

def show_future_user_interface():
    """Show how the user interface could look."""
    print("🖥️  Future User Interface Example:")
    print("-" * 35)
    
    print("User input examples:")
    print("  > build settlement 25")
    print("  > build road 25 26") 
    print("  > build city 25")
    print()
    
    print("The system would:")
    print("  1. Validate point IDs (1-54)")
    print("  2. Check road connectivity") 
    print("  3. Convert to internal coordinates")
    print("  4. Execute game action")
    print("  5. Update web visualization")
    print()

def main():
    """Run the interactive demo."""
    print("🎮 PyCatan Point ID System Demo")
    print("=" * 50)
    print()
    
    print_board_info()
    show_point_examples()
    demonstrate_road_building()
    simulate_game_moves()
    show_future_user_interface()
    
    print("✨ Key Benefits:")
    print("  - Simple point IDs (1-54) instead of complex coordinates")
    print("  - Consistent across Game, Web UI, and user input")
    print("  - Automatic validation of road placement")
    print("  - Single source of truth for board layout")
    print("  - Easy for humans to remember and use")
    print()
    
    print("🚀 Next steps:")
    print("  - Update HumanUser to accept point IDs")
    print("  - Update GameManager to convert point IDs")
    print("  - Test with web interface")

if __name__ == "__main__":
    main()