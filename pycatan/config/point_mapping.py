"""
Point Mapping System for PyCatan

This module provides translation between user-friendly point IDs (1, 2, 3...)
and internal coordinate system ([row, index]).

This creates a unified point reference system for both human input and visualization.
"""

from typing import Dict, List, Tuple, Optional
import json
import os


class PointMapper:
    """
    Manages mapping between point IDs and coordinates.
    
    Point IDs are simple numbers (1, 2, 3...) that users can easily reference.
    Coordinates are [row, index] pairs used internally by the game engine.
    """
    
    def __init__(self):
        """Initialize the point mapper."""
        self.point_to_coords: Dict[int, List[int]] = {}
        self.coords_to_point: Dict[str, int] = {}
        self._load_default_mapping()
    
    def _load_default_mapping(self):
        """Load the default Catan board point mapping."""
        # Standard Catan board layout - 54 intersection points
        # This follows the hexagonal board structure with 19 tiles
        
        default_mapping = [
            # Top row (7 points) - wider at the top
            [0, 0], [0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [0, 6],
            
            # Second row (9 points) 
            [1, 0], [1, 1], [1, 2], [1, 3], [1, 4], [1, 5], [1, 6], [1, 7], [1, 8],
            
            # Third row (11 points) - widest row
            [2, 0], [2, 1], [2, 2], [2, 3], [2, 4], [2, 5], [2, 6], [2, 7], [2, 8], [2, 9], [2, 10],
            
            # Fourth row (11 points) - also widest
            [3, 0], [3, 1], [3, 2], [3, 3], [3, 4], [3, 5], [3, 6], [3, 7], [3, 8], [3, 9], [3, 10],
            
            # Fifth row (9 points)
            [4, 0], [4, 1], [4, 2], [4, 3], [4, 4], [4, 5], [4, 6], [4, 7], [4, 8],
            
            # Bottom row (7 points) - narrows at the bottom  
            [5, 0], [5, 1], [5, 2], [5, 3], [5, 4], [5, 5], [5, 6]
        ]
        
        # Create both mappings
        for point_id, coords in enumerate(default_mapping, 1):
            self.point_to_coords[point_id] = coords
            self.coords_to_point[f"{coords[0]},{coords[1]}"] = point_id
    
    def point_to_coordinate(self, point_id: int) -> Optional[List[int]]:
        """Convert point ID to coordinates."""
        return self.point_to_coords.get(point_id)
    
    def coordinate_to_point(self, row: int, index: int) -> Optional[int]:
        """Convert coordinates to point ID."""
        return self.coords_to_point.get(f"{row},{index}")
    
    def get_all_points(self) -> List[int]:
        """Get all valid point IDs."""
        return sorted(self.point_to_coords.keys())
    
    def get_adjacent_points(self, point_id: int) -> List[int]:
        """
        Get points adjacent to the given point (for road validation).
        
        This is a simplified version - in a real implementation,
        this would check actual board topology.
        """
        coords = self.point_to_coordinate(point_id)
        if not coords:
            return []
        
        row, index = coords
        adjacent_coords = [
            [row-1, index-1], [row-1, index], [row-1, index+1],
            [row, index-1], [row, index+1],
            [row+1, index-1], [row+1, index], [row+1, index+1]
        ]
        
        adjacent_points = []
        for adj_coords in adjacent_coords:
            adj_point = self.coordinate_to_point(adj_coords[0], adj_coords[1])
            if adj_point:
                adjacent_points.append(adj_point)
        
        return adjacent_points
    
    def validate_road_placement(self, start_point: int, end_point: int) -> bool:
        """Check if two points can be connected by a road."""
        if start_point == end_point:
            return False
        
        # Check if points are adjacent
        adjacent_to_start = self.get_adjacent_points(start_point)
        return end_point in adjacent_to_start
    
    def export_mapping(self, filename: str = "point_mapping.json"):
        """Export mapping to JSON file for use by visualizations."""
        export_data = {
            "point_to_coords": self.point_to_coords,
            "coords_to_point": self.coords_to_point,
            "total_points": len(self.point_to_coords)
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Point mapping exported to {filename}")
    
    def import_mapping(self, filename: str):
        """Import mapping from JSON file."""
        if not os.path.exists(filename):
            print(f"Mapping file {filename} not found, using default mapping")
            return
        
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Convert string keys back to integers for point_to_coords
        self.point_to_coords = {int(k): v for k, v in data["point_to_coords"].items()}
        self.coords_to_point = data["coords_to_point"]
        
        print(f"Point mapping imported from {filename}")
    
    def print_mapping(self):
        """Print the current mapping for debugging."""
        print("Point ID -> Coordinates mapping:")
        print("=" * 40)
        
        for point_id in sorted(self.point_to_coords.keys()):
            coords = self.point_to_coords[point_id]
            print(f"Point {point_id:2d} -> [{coords[0]}, {coords[1]}]")
        
        print(f"\\nTotal points: {len(self.point_to_coords)}")


# Global point mapper instance
point_mapper = PointMapper()


# Convenience functions for easy import
def point_to_coords(point_id: int) -> Optional[List[int]]:
    """Convert point ID to coordinates."""
    return point_mapper.point_to_coordinate(point_id)


def coords_to_point(row: int, index: int) -> Optional[int]:
    """Convert coordinates to point ID."""
    return point_mapper.coordinate_to_point(row, index)


def validate_road(start_point: int, end_point: int) -> bool:
    """Check if a road can be placed between two points."""
    return point_mapper.validate_road_placement(start_point, end_point)


def get_all_points() -> List[int]:
    """Get all valid point IDs."""
    return point_mapper.get_all_points()


if __name__ == "__main__":
    # Demo and testing
    print("PyCatan Point Mapping System")
    print("=" * 40)
    
    # Print the mapping
    point_mapper.print_mapping()
    
    # Test some conversions
    print("\\n" + "=" * 40)
    print("Testing conversions:")
    
    test_points = [1, 10, 25, 54]
    for point in test_points:
        coords = point_to_coords(point)
        if coords:
            back_to_point = coords_to_point(coords[0], coords[1])
            print(f"Point {point} -> {coords} -> Point {back_to_point}")
    
    # Test road validation
    print("\\n" + "=" * 40)
    print("Testing road placements:")
    
    test_roads = [(1, 2), (1, 10), (25, 26), (1, 54)]
    for start, end in test_roads:
        valid = validate_road(start, end)
        status = "✓" if valid else "✗"
        print(f"Road {start} -> {end}: {status}")
    
    # Export mapping for web visualization
    print("\\n" + "=" * 40)
    point_mapper.export_mapping("pycatan/static/js/point_mapping.json")