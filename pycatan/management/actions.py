"""
Actions & Data Structures for PyCatan Game Management

This module defines the core data structures for managing game actions,
state, and results in the PyCatan simulation framework.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime


class ActionType(Enum):
    """Enumeration of all possible actions in a Catan game."""
    
    # Building actions
    BUILD_SETTLEMENT = auto()
    BUILD_CITY = auto() 
    BUILD_ROAD = auto()
    
    # Trading actions
    TRADE_PROPOSE = auto()
    TRADE_ACCEPT = auto()
    TRADE_REJECT = auto()
    TRADE_COUNTER = auto()
    TRADE_BANK = auto()
    
    # Development card actions
    USE_DEV_CARD = auto()
    BUY_DEV_CARD = auto()
    
    # Turn management
    ROLL_DICE = auto()
    END_TURN = auto()
    
    # Special actions
    ROBBER_MOVE = auto()
    DISCARD_CARDS = auto()
    STEAL_CARD = auto()
    
    # Setup phase actions
    PLACE_STARTING_SETTLEMENT = auto()
    PLACE_STARTING_ROAD = auto()


class GamePhase(Enum):
    """Enumeration of game phases."""
    SETUP_FIRST_ROUND = auto()
    SETUP_SECOND_ROUND = auto()
    NORMAL_PLAY = auto()
    ENDED = auto()


class TurnPhase(Enum):
    """Enumeration of phases within a single turn."""
    ROLL_DICE = auto()
    HANDLE_DICE_EFFECTS = auto()  # Resource distribution, robber on 7
    DISCARD_PHASE = auto()  # Players with 7+ cards must discard half
    ROBBER_MOVE = auto()  # Current player must move the robber
    ROBBER_STEAL = auto()  # Current player must steal from adjacent player
    PLAYER_ACTIONS = auto()
    END_TURN = auto()


@dataclass
class Action:
    """
    Represents a single action that can be performed in the game.
    
    This is the primary interface between Users and the GameManager.
    All player decisions are expressed as Action objects.
    """
    action_type: ActionType
    player_id: int
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate action parameters based on action type."""
        self._validate_parameters()
    
    def _validate_parameters(self):
        """Basic validation of action parameters."""
        required_params = {
            ActionType.BUILD_SETTLEMENT: ['point_coords'],
            ActionType.BUILD_CITY: ['point_coords'],
            ActionType.BUILD_ROAD: ['start_coords', 'end_coords'],
            ActionType.TRADE_PROPOSE: ['offer', 'request', 'target_player'],
            # TRADE_ACCEPT and TRADE_REJECT don't need trade_id in synchronous mode
            ActionType.TRADE_COUNTER: ['trade_id', 'counter_offer', 'counter_request'],
            ActionType.TRADE_BANK: ['offer', 'request'],
            ActionType.USE_DEV_CARD: ['card_type'],
            ActionType.ROBBER_MOVE: ['tile_coords'],
            ActionType.STEAL_CARD: ['target_player'],
            ActionType.DISCARD_CARDS: ['cards'],
            ActionType.PLACE_STARTING_SETTLEMENT: ['point_coords'],
            ActionType.PLACE_STARTING_ROAD: ['start_coords', 'end_coords'],
        }
        
        required = required_params.get(self.action_type, [])
        missing = [param for param in required if param not in self.parameters]
        
        if missing:
            raise ValueError(f"Action {self.action_type} missing required parameters: {missing}")


@dataclass
@dataclass
class PlayerState:
    """Represents the complete state of a single player."""
    player_id: int
    name: str
    cards: List[str]  # Resource cards
    dev_cards: List[str]  # Development cards
    settlements: List[tuple]  # Coordinates of settlements
    cities: List[tuple]  # Coordinates of cities  
    roads: List[tuple]  # Coordinates of roads (start, end)
    victory_points: int
    longest_road_length: int
    has_longest_road: bool
    has_largest_army: bool
    knights_played: int


@dataclass
class BoardState:
    """Represents the state of the game board."""
    tiles: List[Dict[str, Any]]  # Tile information
    robber_position: tuple  # Coordinates of robber
    harbors: List[Dict[str, Any]]  # Harbor information
    buildings: Dict[tuple, Dict[str, Any]]  # Point -> building info
    roads: List[tuple]  # All roads on board
    points: List[Dict[str, Any]] = field(default_factory=list)  # Node/Point information for AI


@dataclass  
class GameState:
    """
    Represents the complete state of a Catan game at any point in time.
    
    This is used for visualization, AI decision-making, and game persistence.
    """
    # Game metadata
    game_id: str = ""
    turn_number: int = 0
    current_player: int = 0
    game_phase: GamePhase = GamePhase.SETUP_FIRST_ROUND
    turn_phase: TurnPhase = TurnPhase.ROLL_DICE
    
    # Game state
    board_state: BoardState = field(default_factory=lambda: BoardState([], (0, 0), [], {}, []))
    players_state: List[PlayerState] = field(default_factory=list)
    
    # Game resources
    dev_cards_available: int = 25
    resource_cards_available: Dict[str, int] = field(default_factory=lambda: {
        'wood': 19, 'brick': 19, 'sheep': 19, 'wheat': 19, 'ore': 19
    })
    
    # Current turn state
    dice_rolled: Optional[tuple] = None
    pending_trades: List[Dict[str, Any]] = field(default_factory=list)
    pending_actions: List[str] = field(default_factory=list)  # Actions waiting for completion
    allowed_actions: List[str] = field(default_factory=list)  # Available actions for current player
    
    # Robber/Discard state (when 7 is rolled)
    players_must_discard: Dict[int, int] = field(default_factory=dict)  # player_id -> cards to discard
    robber_moved: bool = False  # Whether robber has been moved this turn
    steal_pending: bool = False  # Whether steal action is pending
    
    # Game history (for replay/debugging)
    action_history: List[Action] = field(default_factory=list)
    
    def get_player_state(self, player_id: int) -> Optional[PlayerState]:
        """Get state for a specific player."""
        for player in self.players_state:
            if player.player_id == player_id:
                return player
        return None
    
    def get_current_player_state(self) -> Optional[PlayerState]:
        """Get state for the current player."""
        return self.get_player_state(self.current_player)


@dataclass
class ActionResult:
    """
    Result of executing an action.
    
    Contains information about success/failure, updated game state,
    and any side effects that occurred.
    """
    success: bool
    error_message: Optional[str] = None
    updated_state: Optional[GameState] = None
    affected_players: List[int] = field(default_factory=list)
    side_effects: List[Action] = field(default_factory=list)  # Additional actions triggered
    status_code: str = ""  # Maps to pycatan.statuses for compatibility
    
    @classmethod
    def success_result(cls, updated_state: GameState, affected_players: List[int] = None) -> 'ActionResult':
        """Create a successful action result."""
        return cls(
            success=True,
            updated_state=updated_state,
            affected_players=affected_players or [],
            status_code="ALL_GOOD"
        )
    
    @classmethod  
    def failure_result(cls, error_message: str, status_code: str = "") -> 'ActionResult':
        """Create a failed action result."""
        return cls(
            success=False,
            error_message=error_message,
            status_code=status_code
        )


# Utility functions for common action creation
def create_build_settlement_action(player_id: int, point_coords: tuple, is_starting: bool = False) -> Action:
    """Helper function to create a build settlement action."""
    action_type = ActionType.PLACE_STARTING_SETTLEMENT if is_starting else ActionType.BUILD_SETTLEMENT
    return Action(
        action_type=action_type,
        player_id=player_id,
        parameters={'point_coords': point_coords}
    )


def create_build_road_action(player_id: int, start_coords: tuple, end_coords: tuple, is_starting: bool = False) -> Action:
    """Helper function to create a build road action."""
    action_type = ActionType.PLACE_STARTING_ROAD if is_starting else ActionType.BUILD_ROAD
    return Action(
        action_type=action_type,
        player_id=player_id,
        parameters={'start_coords': start_coords, 'end_coords': end_coords}
    )


def create_trade_action(player_id: int, offer: Dict[str, int], request: Dict[str, int], 
                       target_player: Optional[int] = None) -> Action:
    """Helper function to create a trade action."""
    action_type = ActionType.TRADE_BANK if target_player is None else ActionType.TRADE_PROPOSE
    parameters = {'offer': offer, 'request': request}
    if target_player is not None:
        parameters['target_player'] = target_player
    
    return Action(
        action_type=action_type,
        player_id=player_id,
        parameters=parameters
    )