"""
PyCatan - Settlers of Catan Simulation Library

A modular Python library for simulating Settlers of Catan games with support
for multiple player types (human/AI) and visualization interfaces.

Architecture:
- core: Game rules and state management
- management: Turn flow and orchestration  
- players: Human and AI player implementations
- visualizations: Console and web display interfaces
- config: Board definitions and mappings
"""

# Core game components
from pycatan.core import (
    Game, Board, DefaultBoard, Player, Tile, TileType, Point, Building,
    ResCard, DevCard, Harbor, Statuses
)

# Game management
from pycatan.management import (
    GameManager, Action, ActionType, ActionResult, GameState, PlayerState,
    BoardState, GamePhase, TurnPhase, LogEntry, EventType
)

# Players
from pycatan.players import (
    User, UserInputError, validate_user_list, create_test_user, HumanUser
)

# Visualizations
from pycatan.visualizations import (
    Visualization, ConsoleVisualization
)

# Optional web visualization (requires Flask)
try:
    from pycatan.visualizations import WebVisualization, create_web_visualization
except ImportError:
    # Flask not available - web visualization disabled
    WebVisualization = None
    create_web_visualization = None

# Configuration and mappings
from pycatan.config import (
    BoardDefinition, PointMapper, board_definition
)

# Complete game experience
from pycatan.real_game import RealGame

__version__ = "0.14.0"
