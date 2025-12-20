"""
PyCatan Configuration and Mapping

This module contains board definitions, coordinate mappings, and configuration:
- BoardDefinition: Canonical board layout and coordinate systems
- PointMapper: Translation between point IDs and coordinates
"""

from .board_definition import (
    HexDefinition,
    PointDefinition,
    BoardDefinition,
    board_definition,
    point_id_to_coords,
    coords_to_point_id,
    get_adjacent_points,
    validate_road_placement,
)
from .point_mapping import PointMapper

__all__ = [
    'HexDefinition',
    'PointDefinition',
    'BoardDefinition',
    'board_definition',
    'point_id_to_coords',
    'coords_to_point_id',
    'get_adjacent_points',
    'validate_road_placement',
    'PointMapper',
]
