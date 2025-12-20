from pycatan.board import Board
from pycatan.building import Building
from pycatan.card import ResCard, DevCard
from pycatan.game import Game
from pycatan.harbor import Harbor
from pycatan.player import Player
from pycatan.statuses import Statuses

# Board definition system
from pycatan.board_definition import board_definition, point_id_to_coords, coords_to_point_id

# New simulation framework components
from pycatan.actions import (
    Action, ActionType, ActionResult, GameState, PlayerState, BoardState,
    GamePhase, TurnPhase, create_build_settlement_action, create_build_road_action,
    create_trade_action
)
from pycatan.log_events import EventType, LogEntry, create_log_entry
from pycatan.user import User, UserInputError, validate_user_list, create_test_user
from pycatan.human_user import HumanUser
from pycatan.game_manager import GameManager
from pycatan.visualization import Visualization, VisualizationManager
from pycatan.console_visualization import ConsoleVisualization

# Optional web visualization (requires Flask)
try:
    from pycatan.web_visualization import WebVisualization, create_web_visualization
except ImportError:
    # Flask not available - web visualization disabled
    WebVisualization = None
    create_web_visualization = None

# Complete game experience
from pycatan.real_game import RealGame
