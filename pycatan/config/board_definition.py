"""
Central Board Definition for PyCatan

This module provides the definitive, canonical mapping of the Catan board,
including all coordinate systems and conversion functions.

ALL other modules should use this as the single source of truth for:
- Point coordinates and IDs
- Hex/tile coordinates and IDs  
- Conversion between coordinate systems
- Board layout and geometry

This ensures consistency across Game, WebVisualization, JavaScript, and user input.
"""

from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass
import json


@dataclass
class HexDefinition:
    """Definition of a single hex on the board."""
    hex_id: int           # 1-19 for standard Catan
    game_coords: Tuple[int, int]  # [row, index] used by Game internally
    axial_coords: Tuple[int, int] # [q, r] for web display
    adjacent_points: List[int]    # Point IDs (1-54) that border this hex


@dataclass
class PointDefinition:
    """Definition of a single point/vertex on the board."""
    point_id: int         # 1-54 for standard Catan  
    game_coords: Tuple[int, int]  # [row, index] used by Game internally
    pixel_coords: Tuple[float, float]  # [x, y] for web display
    adjacent_points: List[int]    # Connected point IDs for roads
    adjacent_hexes: List[int]     # Hex IDs that this point touches


class BoardDefinition:
    """
    Central definition of the Catan board layout.
    
    This class provides the single source of truth for all coordinate
    mappings and board geometry. All other systems should use this
    instead of their own coordinate conversion logic.
    """
    
    def __init__(self):
        """Initialize the standard Catan board definition."""
        self.hexes: Dict[int, HexDefinition] = {}
        self.points: Dict[int, PointDefinition] = {}
        
        # Try to load from file first
        if not self._load_from_file():
            # Fallback to hardcoded initialization
            self._initialize_hexes()
            self._initialize_points() 
            self._calculate_adjacencies()
            
    def _load_from_file(self, filename: str = None) -> bool:
        """Load board definition from JSON file."""
        import os
        if filename is None:
            # Default path: pycatan/config/data/board_definition.json
            filename = os.path.join(os.path.dirname(__file__), 'data', 'board_definition.json')
        if not os.path.exists(filename):
            return False
            
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                
            # Load Hexes
            for hex_id_str, hex_data in data.get('hexes', {}).items():
                hex_id = int(hex_id_str)
                self.hexes[hex_id] = HexDefinition(
                    hex_id=hex_id,
                    game_coords=tuple(hex_data['game_coords']),
                    axial_coords=tuple(hex_data['axial_coords']),
                    adjacent_points=hex_data.get('adjacent_points', [])
                )
                
            # Load Points
            for point_id_str, point_data in data.get('points', {}).items():
                point_id = int(point_id_str)
                self.points[point_id] = PointDefinition(
                    point_id=point_id,
                    game_coords=tuple(point_data['game_coords']),
                    pixel_coords=tuple(point_data['pixel_coords']),
                    adjacent_points=point_data.get('adjacent_points', []),
                    adjacent_hexes=point_data.get('adjacent_hexes', [])
                )
                
            print(f"Loaded board definition from {filename}")
            return True
        except Exception as e:
            print(f"Error loading board definition: {e}")
            return False
    
    def _initialize_hexes(self):
        """Initialize all 19 hexes with their coordinate mappings."""
        # Standard Catan board: 5 rows with 3,4,5,4,3 hexes
        hex_id = 1
        
        # Define the game coordinate to axial coordinate conversion
        # This matches the layout expected by the web visualization
        hex_layouts = [
            # Row 0: 3 hexes -> axial coordinates 
            [(0, 0, 0, -2), (0, 1, 1, -2), (0, 2, 2, -2)],
            # Row 1: 4 hexes  
            [(1, 0, -1, -1), (1, 1, 0, -1), (1, 2, 1, -1), (1, 3, 2, -1)],
            # Row 2: 5 hexes (middle row)
            [(2, 0, -2, 0), (2, 1, -1, 0), (2, 2, 0, 0), (2, 3, 1, 0), (2, 4, 2, 0)],
            # Row 3: 4 hexes
            [(3, 0, -2, 1), (3, 1, -1, 1), (3, 2, 0, 1), (3, 3, 1, 1)],
            # Row 4: 3 hexes  
            [(4, 0, -2, 2), (4, 1, -1, 2), (4, 2, 0, 2)]
        ]
        
        for row_layout in hex_layouts:
            for row, col, q, r in row_layout:
                self.hexes[hex_id] = HexDefinition(
                    hex_id=hex_id,
                    game_coords=(row, col),
                    axial_coords=(q, r), 
                    adjacent_points=[]  # Will be calculated later
                )
                hex_id += 1
    
    def _initialize_points(self):
        """Initialize all 54 points with their coordinate mappings."""
        # Standard Catan board: 6 rows with 7,9,11,11,9,7 points
        point_id = 1
        
        # Define all point coordinates as used by the Game internally
        point_layouts = [
            # Row 0: 7 points
            [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6)],
            # Row 1: 9 points
            [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8)],
            # Row 2: 11 points
            [(2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (2, 10)],
            # Row 3: 11 points  
            [(3, 0), (3, 1), (3, 2), (3, 3), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (3, 10)],
            # Row 4: 9 points
            [(4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (4, 6), (4, 7), (4, 8)],
            # Row 5: 7 points
            [(5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6)]
        ]
        
        for row_points in point_layouts:
            for row, col in row_points:
                # Calculate pixel coordinates for web display
                pixel_x, pixel_y = self._calculate_pixel_coords(row, col)
                
                self.points[point_id] = PointDefinition(
                    point_id=point_id,
                    game_coords=(row, col),
                    pixel_coords=(pixel_x, pixel_y),
                    adjacent_points=[],  # Will be calculated later
                    adjacent_hexes=[]    # Will be calculated later
                )
                point_id += 1
    
    def _calculate_pixel_coords(self, row: int, col: int) -> Tuple[float, float]:
        """
        Calculate pixel coordinates for a point given its game coordinates.
        
        Uses direct mapping of each point to the appropriate hex vertex position.
        This ensures points are positioned exactly on hex corners.
        """
        import math
        
        # Base parameters matching JavaScript
        HEX_RADIUS = 45
        CENTER_X = 400
        CENTER_Y = 300
        
        # Helper: get pixel coords of hex center from axial coords
        def get_hex_center(q, r):
            x = CENTER_X + HEX_RADIUS * (3/2 * q)
            y = CENTER_Y + HEX_RADIUS * (math.sqrt(3)/2 * q + math.sqrt(3) * r)
            return (x, y)
        
        # Helper: get vertex position (0=top, clockwise)
        def get_hex_vertex(q, r, vertex_idx):
            cx, cy = get_hex_center(q, r)
            angle_deg = 60 * vertex_idx - 90  # Start at top (270°), go clockwise
            angle_rad = math.radians(angle_deg)
            x = cx + HEX_RADIUS * math.cos(angle_rad)
            y = cy + HEX_RADIUS * math.sin(angle_rad)
            return (x, y)
        
        # Manual mapping: (row, col) -> (q, r, vertex)
        # Based on standard Catan board with axial coordinates
        point_to_hex_vertex = {
            # Row 0 (7 points) - top edge
            (0, 0): (0, -2, 4),   (0, 1): (0, -2, 5),   (0, 2): (0, -2, 0),
            (0, 3): (1, -2, 5),   (0, 4): (1, -2, 0),   (0, 5): (2, -2, 5),
            (0, 6): (2, -2, 0),
            
            # Row 1 (9 points)
            (1, 0): (-1, -1, 4),  (1, 1): (-1, -1, 5),  (1, 2): (0, -1, 4),
            (1, 3): (0, -1, 5),   (1, 4): (1, -1, 4),   (1, 5): (1, -1, 5),
            (1, 6): (2, -1, 4),   (1, 7): (2, -1, 5),   (1, 8): (2, -1, 0),
            
            # Row 2 (11 points) - widest
            (2, 0): (-2, 0, 4),   (2, 1): (-2, 0, 5),   (2, 2): (-1, 0, 4),
            (2, 3): (-1, 0, 5),   (2, 4): (0, 0, 4),    (2, 5): (0, 0, 5),
            (2, 6): (1, 0, 4),    (2, 7): (1, 0, 5),    (2, 8): (2, 0, 4),
            (2, 9): (2, 0, 5),    (2, 10): (2, 0, 0),
            
            # Row 3 (11 points) - widest
            (3, 0): (-2, 1, 3),   (3, 1): (-2, 1, 4),   (3, 2): (-1, 1, 3),
            (3, 3): (-1, 1, 4),   (3, 4): (0, 1, 3),    (3, 5): (0, 1, 4),
            (3, 6): (1, 1, 3),    (3, 7): (1, 1, 4),    (3, 8): (1, 1, 5),
            (3, 9): (1, 1, 0),    (3, 10): (1, 1, 1),
            
            # Row 4 (9 points)
            (4, 0): (-2, 2, 2),   (4, 1): (-2, 2, 3),   (4, 2): (-1, 2, 2),
            (4, 3): (-1, 2, 3),   (4, 4): (0, 2, 2),    (4, 5): (0, 2, 3),
            (4, 6): (0, 2, 4),    (4, 7): (0, 2, 5),    (4, 8): (0, 2, 0),
            
            # Row 5 (7 points) - bottom edge
            (5, 0): (-2, 2, 1),   (5, 1): (-2, 2, 2),   (5, 2): (-1, 2, 1),
            (5, 3): (-1, 2, 2),   (5, 4): (0, 2, 1),    (5, 5): (0, 2, 2),
            (5, 6): (0, 2, 3),
        }
        
        # Get the hex and vertex for this point
        if (row, col) in point_to_hex_vertex:
            q, r, vertex = point_to_hex_vertex[(row, col)]
            return get_hex_vertex(q, r, vertex)
        else:
            # Fallback for unmapped points
            print(f"Warning: No mapping for point ({row}, {col})")
            return (CENTER_X, CENTER_Y)
        return (x, y)
    
    def _calculate_adjacencies(self):
        """Calculate which points and hexes are adjacent to each other."""
        # For each hex, determine which points border it
        # For each point, determine which other points it connects to and which hexes it touches
        
        # This is based on the geometric relationships of the hexagonal board
        # We'll use the existing logic from DefaultBoard.get_tile_indexes_for_point
        # but in a cleaner, centralized way
        
        for point_id, point_def in self.points.items():
            row, col = point_def.game_coords
            
            # Find adjacent hexes using the existing logic from DefaultBoard
            adjacent_hex_coords = self._get_hex_coords_for_point(row, col)
            for hex_coord in adjacent_hex_coords:
                # Find hex with these coordinates
                for hex_id, hex_def in self.hexes.items():
                    if hex_def.game_coords == hex_coord:
                        point_def.adjacent_hexes.append(hex_id)
                        hex_def.adjacent_points.append(point_id)
            
            # Find adjacent points using board connectivity rules
            point_def.adjacent_points = self._get_connected_point_ids(row, col)
    
    def _get_hex_coords_for_point(self, row: int, col: int) -> List[Tuple[int, int]]:
        """
        Get hex coordinates that border a given point.
        This is the same logic as DefaultBoard.get_tile_indexes_for_point
        """
        hex_coords = []
        
        # The complex logic from DefaultBoard - but cleaner
        if row < 3:  # Top half
            # Hexes below the point
            if col < [7, 9, 11][row] - 1:
                hex_coords.append((row, col // 2))
            
            if col % 2 == 0 and col > 0:
                hex_coords.append((row, col // 2 - 1))
            
            # Hexes above the point
            if row > 0:
                if col > 0 and col < [7, 9, 11][row] - 2:
                    hex_coords.append((row - 1, (col - 1) // 2))
                
                if col % 2 == 1 and col < [7, 9, 11][row] - 1 and col > 1:
                    hex_coords.append((row - 1, (col - 1) // 2 - 1))
        
        else:  # Bottom half
            # Hexes below
            if row < 5:
                if col < [11, 9, 7][row - 3] - 2 and col > 0:
                    hex_coords.append((row, (col - 1) // 2))
                
                if col % 2 == 1 and col > 1 and col < [11, 9, 7][row - 3]:
                    hex_coords.append((row, (col - 1) // 2 - 1))
            
            # Hexes above
            if col < [11, 9, 7][row - 3] - 1:
                hex_coords.append((row - 1, col // 2))
            
            if col > 1 and col % 2 == 0:
                hex_coords.append((row - 1, (col - 1) // 2))
        
        return hex_coords
    
    def _get_connected_point_ids(self, row: int, col: int) -> List[int]:
        """
        Get point IDs that are directly connected to the given point.
        This is based on DefaultBoard.get_connected_points logic.
        """
        connected = []
        
        # Left and right connections
        if col > 0:
            left_point_id = self.coords_to_point_id(row, col - 1)
            if left_point_id:
                connected.append(left_point_id)
        
        row_widths = [7, 9, 11, 11, 9, 7]
        if col < row_widths[row] - 1:
            right_point_id = self.coords_to_point_id(row, col + 1)
            if right_point_id:
                connected.append(right_point_id)
        
        # Up and down connections (more complex due to hexagonal geometry)
        if row == 2 and col % 2 == 0:
            down_point_id = self.coords_to_point_id(row + 1, col)
            if down_point_id:
                connected.append(down_point_id)
        elif row == 3 and col % 2 == 0:
            up_point_id = self.coords_to_point_id(row - 1, col)
            if up_point_id:
                connected.append(up_point_id)
        elif row < 3:
            if col % 2 == 0:
                down_point_id = self.coords_to_point_id(row + 1, col + 1)
                if down_point_id:
                    connected.append(down_point_id)
            elif row > 0 and col > 0:
                up_point_id = self.coords_to_point_id(row - 1, col - 1)
                if up_point_id:
                    connected.append(up_point_id)
        else:
            if col % 2 == 0:
                up_point_id = self.coords_to_point_id(row - 1, col + 1)
                if up_point_id:
                    connected.append(up_point_id)
            elif row < 5 and col > 0:
                down_point_id = self.coords_to_point_id(row + 1, col - 1)
                if down_point_id:
                    connected.append(down_point_id)
        
        return connected
    
    # ===== PUBLIC API FOR COORDINATE CONVERSIONS =====
    
    def point_id_to_game_coords(self, point_id: int) -> Optional[Tuple[int, int]]:
        """Convert point ID (1-54) to game coordinates [row, col]."""
        point_def = self.points.get(point_id)
        return point_def.game_coords if point_def else None
    
    def game_coords_to_point_id(self, row: int, col: int) -> Optional[int]:
        """Convert game coordinates [row, col] to point ID (1-54)."""
        for point_id, point_def in self.points.items():
            if point_def.game_coords == (row, col):
                return point_id
        return None
    
    def coords_to_point_id(self, row: int, col: int) -> Optional[int]:
        """Alias for game_coords_to_point_id for backward compatibility."""
        return self.game_coords_to_point_id(row, col)
    
    def point_id_to_pixel_coords(self, point_id: int) -> Optional[Tuple[float, float]]:
        """Convert point ID to pixel coordinates for web display."""
        point_def = self.points.get(point_id)
        return point_def.pixel_coords if point_def else None
    
    def hex_id_to_game_coords(self, hex_id: int) -> Optional[Tuple[int, int]]:
        """Convert hex ID (1-19) to game coordinates [row, col]."""
        hex_def = self.hexes.get(hex_id)
        return hex_def.game_coords if hex_def else None
    
    def game_coords_to_hex_id(self, row: int, col: int) -> Optional[int]:
        """Convert game coordinates [row, col] to hex ID (1-19)."""
        for hex_id, hex_def in self.hexes.items():
            if hex_def.game_coords == (row, col):
                return hex_id
        return None
    
    def hex_id_to_axial_coords(self, hex_id: int) -> Optional[Tuple[int, int]]:
        """Convert hex ID to axial coordinates [q, r] for web display."""
        hex_def = self.hexes.get(hex_id)
        return hex_def.axial_coords if hex_def else None
    
    def get_adjacent_point_ids(self, point_id: int) -> List[int]:
        """Get all point IDs directly connected to the given point."""
        point_def = self.points.get(point_id)
        return point_def.adjacent_points.copy() if point_def else []
    
    def get_adjacent_hex_ids(self, point_id: int) -> List[int]:
        """Get all hex IDs that border the given point."""
        point_def = self.points.get(point_id)
        return point_def.adjacent_hexes.copy() if point_def else []
    
    def get_hex_border_points(self, hex_id: int) -> List[int]:
        """Get all point IDs that border the given hex."""
        hex_def = self.hexes.get(hex_id)
        return hex_def.adjacent_points.copy() if hex_def else []
    
    def is_valid_road_placement(self, point_id_1: int, point_id_2: int) -> bool:
        """Check if a road can be placed between two points."""
        if point_id_1 == point_id_2:
            return False
        
        adjacent_points = self.get_adjacent_point_ids(point_id_1)
        return point_id_2 in adjacent_points
    
    def get_all_point_ids(self) -> List[int]:
        """Get all valid point IDs (1-54)."""
        return sorted(self.points.keys())
    
    def get_all_hex_ids(self) -> List[int]:
        """Get all valid hex IDs (1-19)."""
        return sorted(self.hexes.keys())
    
    # ===== EXPORT FUNCTIONS FOR OTHER SYSTEMS =====
    
    def export_for_web(self) -> Dict:
        """Export board definition in format expected by web visualization."""
        return {
            'hexes': [
                {
                    'id': hex_def.hex_id,
                    'q': hex_def.axial_coords[0],
                    'r': hex_def.axial_coords[1],
                    'game_coords': hex_def.game_coords
                }
                for hex_def in self.hexes.values()
            ],
            'points': [
                {
                    'id': point_def.point_id,
                    'x': point_def.pixel_coords[0], 
                    'y': point_def.pixel_coords[1],
                    'game_coords': point_def.game_coords,
                    'adjacent_points': point_def.adjacent_points,
                    'adjacent_hexes': point_def.adjacent_hexes
                }
                for point_def in self.points.values()
            ],
            'total_points': len(self.points),
            'total_hexes': len(self.hexes)
        }
    
    def export_point_mapping(self) -> Dict:
        """Export point mapping for backward compatibility with point_mapping.py."""
        return {
            'point_to_coords': {
                point_id: list(point_def.game_coords)
                for point_id, point_def in self.points.items()
            },
            'coords_to_point': {
                f"{point_def.game_coords[0]},{point_def.game_coords[1]}": point_id
                for point_id, point_def in self.points.items()
            },
            'total_points': len(self.points)
        }
    
    def save_to_file(self, filename: str = None):
        """Save board definition to JSON file."""
        import os
        if filename is None:
            # Default path: pycatan/config/data/board_definition.json
            filename = os.path.join(os.path.dirname(__file__), 'data', 'board_definition.json')
        data = {
            'hexes': {
                hex_id: {
                    'hex_id': hex_def.hex_id,
                    'game_coords': hex_def.game_coords,
                    'axial_coords': hex_def.axial_coords,
                    'adjacent_points': hex_def.adjacent_points
                }
                for hex_id, hex_def in self.hexes.items()
            },
            'points': {
                point_id: {
                    'point_id': point_def.point_id,
                    'game_coords': point_def.game_coords,
                    'pixel_coords': point_def.pixel_coords,
                    'adjacent_points': point_def.adjacent_points,
                    'adjacent_hexes': point_def.adjacent_hexes
                }
                for point_id, point_def in self.points.items()
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Board definition saved to {filename}")


# Global board definition instance - single source of truth
board_definition = BoardDefinition()


# Convenience functions for backward compatibility
def point_id_to_coords(point_id: int) -> Optional[List[int]]:
    """Convert point ID to game coordinates."""
    coords = board_definition.point_id_to_game_coords(point_id)
    return list(coords) if coords else None


def coords_to_point_id(row: int, col: int) -> Optional[int]:
    """Convert game coordinates to point ID."""
    return board_definition.game_coords_to_point_id(row, col)


def get_adjacent_points(point_id: int) -> List[int]:
    """Get adjacent point IDs for the given point."""
    return board_definition.get_adjacent_point_ids(point_id)


def validate_road_placement(point_id_1: int, point_id_2: int) -> bool:
    """Check if a road can be placed between two points."""
    return board_definition.is_valid_road_placement(point_id_1, point_id_2)


if __name__ == "__main__":
    # Test and demonstration
    print("=== PyCatan Board Definition ===")
    print(f"Total hexes: {len(board_definition.hexes)}")
    print(f"Total points: {len(board_definition.points)}")
    
    # Test coordinate conversions
    print("\n=== Coordinate Conversion Tests ===")
    test_points = [1, 10, 25, 54]
    for point_id in test_points:
        game_coords = board_definition.point_id_to_game_coords(point_id)
        pixel_coords = board_definition.point_id_to_pixel_coords(point_id)
        back_to_id = board_definition.game_coords_to_point_id(*game_coords) if game_coords else None
        
        print(f"Point {point_id}: {game_coords} -> pixels {pixel_coords} -> back to {back_to_id}")
    
    # Test adjacency
    print("\n=== Adjacency Tests ===")
    test_point = 25
    adjacent = board_definition.get_adjacent_point_ids(test_point)
    adjacent_hexes = board_definition.get_adjacent_hex_ids(test_point)
    print(f"Point {test_point} adjacent to points: {adjacent}")
    print(f"Point {test_point} adjacent to hexes: {adjacent_hexes}")
    
    # Test road validation
    print("\n=== Road Validation Tests ===")
    test_roads = [(1, 2), (1, 8), (25, 26), (1, 54)]
    for p1, p2 in test_roads:
        valid = board_definition.is_valid_road_placement(p1, p2)
        status = "✓" if valid else "✗"
        print(f"Road {p1} -> {p2}: {status}")
    
    # Export for web
    board_definition.save_to_file('board_definition.json')