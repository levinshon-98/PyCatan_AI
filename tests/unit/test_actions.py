"""
Unit tests for pycatan.actions module.

Tests all action types, data structures, validation, and utility functions.
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from pycatan.management.actions import (
    Action, ActionType, ActionResult, GameState, PlayerState, BoardState,
    GamePhase, TurnPhase, create_build_settlement_action, create_build_road_action,
    create_trade_action
)


class TestActionType:
    """Test ActionType enum."""
    
    def test_all_action_types_exist(self):
        """Verify all expected action types are defined."""
        expected_actions = [
            'BUILD_SETTLEMENT', 'BUILD_CITY', 'BUILD_ROAD',
            'TRADE_PROPOSE', 'TRADE_ACCEPT', 'TRADE_REJECT', 'TRADE_COUNTER', 'TRADE_BANK',
            'USE_DEV_CARD', 'BUY_DEV_CARD',
            'ROLL_DICE', 'END_TURN',
            'ROBBER_MOVE', 'DISCARD_CARDS', 'STEAL_CARD',
            'PLACE_STARTING_SETTLEMENT', 'PLACE_STARTING_ROAD'
        ]
        
        for action_name in expected_actions:
            assert hasattr(ActionType, action_name), f"ActionType.{action_name} not found"
    
    def test_action_type_values_are_unique(self):
        """Ensure all action type values are unique."""
        values = [action.value for action in ActionType]
        assert len(values) == len(set(values)), "ActionType values are not unique"


class TestAction:
    """Test Action dataclass."""
    
    def test_basic_action_creation(self):
        """Test creating a basic action."""
        action = Action(
            action_type=ActionType.END_TURN,
            player_id=1
        )
        
        assert action.action_type == ActionType.END_TURN
        assert action.player_id == 1
        assert action.parameters == {}
        assert isinstance(action.timestamp, datetime)
    
    def test_action_with_parameters(self):
        """Test creating an action with parameters."""
        params = {'point_coords': (1, 2)}
        action = Action(
            action_type=ActionType.BUILD_SETTLEMENT,
            player_id=0,
            parameters=params
        )
        
        assert action.parameters == params
    
    def test_action_validation_success(self):
        """Test successful action validation."""
        # Action with required parameters should validate successfully
        action = Action(
            action_type=ActionType.BUILD_SETTLEMENT,
            player_id=0,
            parameters={'point_coords': (1, 2)}
        )
        # Should not raise exception
    
    def test_action_validation_missing_params(self):
        """Test action validation with missing required parameters."""
        with pytest.raises(ValueError, match="missing required parameters"):
            Action(
                action_type=ActionType.BUILD_SETTLEMENT,
                player_id=0,
                parameters={}  # Missing point_coords
            )
    
    def test_action_validation_trade_propose(self):
        """Test validation for trade propose action."""
        # Valid trade propose
        action = Action(
            action_type=ActionType.TRADE_PROPOSE,
            player_id=0,
            parameters={
                'offer': {'wood': 1},
                'request': {'brick': 1},
                'target_player': 1
            }
        )
        # Should not raise exception
        
        # Missing target_player
        with pytest.raises(ValueError, match="missing required parameters"):
            Action(
                action_type=ActionType.TRADE_PROPOSE,
                player_id=0,
                parameters={
                    'offer': {'wood': 1},
                    'request': {'brick': 1}
                    # Missing target_player
                }
            )
    
    def test_action_validation_no_requirements(self):
        """Test actions that don't require parameters."""
        actions_without_requirements = [
            ActionType.ROLL_DICE,
            ActionType.END_TURN,
            ActionType.BUY_DEV_CARD
        ]
        
        for action_type in actions_without_requirements:
            action = Action(
                action_type=action_type,
                player_id=0
            )
            # Should not raise exception


class TestGameState:
    """Test GameState dataclass."""
    
    def test_default_game_state(self):
        """Test creating a default game state."""
        state = GameState()
        
        assert state.game_id == ""
        assert state.turn_number == 0
        assert state.current_player == 0
        assert state.game_phase == GamePhase.SETUP_FIRST_ROUND
        assert state.turn_phase == TurnPhase.ROLL_DICE
        assert state.dev_cards_available == 25
        assert len(state.players_state) == 0
        assert state.dice_rolled is None
        assert len(state.pending_trades) == 0
        assert len(state.action_history) == 0
    
    def test_game_state_with_players(self):
        """Test game state with players."""
        players = [
            PlayerState(player_id=0, name="Alice", cards=[], dev_cards=[], 
                       settlements=[], cities=[], roads=[], victory_points=0,
                       longest_road_length=0, has_longest_road=False, 
                       has_largest_army=False, knights_played=0),
            PlayerState(player_id=1, name="Bob", cards=[], dev_cards=[], 
                       settlements=[], cities=[], roads=[], victory_points=0,
                       longest_road_length=0, has_longest_road=False, 
                       has_largest_army=False, knights_played=0)
        ]
        
        state = GameState(players_state=players)
        assert len(state.players_state) == 2
        assert state.players_state[0].name == "Alice"
        assert state.players_state[1].name == "Bob"
    
    def test_get_player_state(self):
        """Test getting player state by ID."""
        players = [
            PlayerState(player_id=0, name="Alice", cards=[], dev_cards=[], 
                       settlements=[], cities=[], roads=[], victory_points=0,
                       longest_road_length=0, has_longest_road=False, 
                       has_largest_army=False, knights_played=0),
            PlayerState(player_id=2, name="Charlie", cards=[], dev_cards=[], 
                       settlements=[], cities=[], roads=[], victory_points=0,
                       longest_road_length=0, has_longest_road=False, 
                       has_largest_army=False, knights_played=0)
        ]
        
        state = GameState(players_state=players)
        
        # Existing player
        alice = state.get_player_state(0)
        assert alice is not None
        assert alice.name == "Alice"
        
        # Non-existing player
        missing = state.get_player_state(1)
        assert missing is None
    
    def test_get_current_player_state(self):
        """Test getting current player state."""
        players = [
            PlayerState(player_id=0, name="Alice", cards=[], dev_cards=[], 
                       settlements=[], cities=[], roads=[], victory_points=0,
                       longest_road_length=0, has_longest_road=False, 
                       has_largest_army=False, knights_played=0),
            PlayerState(player_id=1, name="Bob", cards=[], dev_cards=[], 
                       settlements=[], cities=[], roads=[], victory_points=0,
                       longest_road_length=0, has_longest_road=False, 
                       has_largest_army=False, knights_played=0)
        ]
        
        state = GameState(players_state=players, current_player=1)
        
        current = state.get_current_player_state()
        assert current is not None
        assert current.name == "Bob"


class TestActionResult:
    """Test ActionResult dataclass."""
    
    def test_success_result_creation(self):
        """Test creating a success result."""
        state = GameState()
        result = ActionResult.success_result(state, [0, 1])
        
        assert result.success is True
        assert result.error_message is None
        assert result.updated_state == state
        assert result.affected_players == [0, 1]
        assert result.status_code == "ALL_GOOD"
    
    def test_success_result_default_players(self):
        """Test success result with default affected players."""
        state = GameState()
        result = ActionResult.success_result(state)
        
        assert result.affected_players == []
    
    def test_failure_result_creation(self):
        """Test creating a failure result."""
        error_msg = "Invalid move"
        status_code = "ERR_BLOCKED"
        result = ActionResult.failure_result(error_msg, status_code)
        
        assert result.success is False
        assert result.error_message == error_msg
        assert result.updated_state is None
        assert result.affected_players == []
        assert result.status_code == status_code
    
    def test_failure_result_default_status(self):
        """Test failure result with default status code."""
        result = ActionResult.failure_result("Error occurred")
        assert result.status_code == ""


class TestUtilityFunctions:
    """Test utility functions for action creation."""
    
    def test_create_build_settlement_action(self):
        """Test building settlement action creation."""
        # Normal settlement
        action = create_build_settlement_action(player_id=1, point_coords=(2, 3))
        
        assert action.action_type == ActionType.BUILD_SETTLEMENT
        assert action.player_id == 1
        assert action.parameters['point_coords'] == (2, 3)
    
    def test_create_build_settlement_action_starting(self):
        """Test building starting settlement action creation."""
        action = create_build_settlement_action(player_id=0, point_coords=(1, 1), is_starting=True)
        
        assert action.action_type == ActionType.PLACE_STARTING_SETTLEMENT
        assert action.player_id == 0
        assert action.parameters['point_coords'] == (1, 1)
    
    def test_create_build_road_action(self):
        """Test building road action creation."""
        # Normal road
        action = create_build_road_action(player_id=2, start_coords=(1, 1), end_coords=(1, 2))
        
        assert action.action_type == ActionType.BUILD_ROAD
        assert action.player_id == 2
        assert action.parameters['start_coords'] == (1, 1)
        assert action.parameters['end_coords'] == (1, 2)
    
    def test_create_build_road_action_starting(self):
        """Test building starting road action creation."""
        action = create_build_road_action(player_id=1, start_coords=(2, 2), end_coords=(2, 3), is_starting=True)
        
        assert action.action_type == ActionType.PLACE_STARTING_ROAD
        assert action.player_id == 1
        assert action.parameters['start_coords'] == (2, 2)
        assert action.parameters['end_coords'] == (2, 3)
    
    def test_create_trade_action_player(self):
        """Test player-to-player trade action creation."""
        offer = {'wood': 2}
        request = {'brick': 1}
        action = create_trade_action(player_id=0, offer=offer, request=request, target_player=2)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.player_id == 0
        assert action.parameters['offer'] == offer
        assert action.parameters['request'] == request
        assert action.parameters['target_player'] == 2
    
    def test_create_trade_action_bank(self):
        """Test bank trade action creation."""
        offer = {'wood': 4}
        request = {'brick': 1}
        action = create_trade_action(player_id=1, offer=offer, request=request)
        
        assert action.action_type == ActionType.TRADE_BANK
        assert action.player_id == 1
        assert action.parameters['offer'] == offer
        assert action.parameters['request'] == request
        assert 'target_player' not in action.parameters


class TestDataStructureIntegrity:
    """Test data structure relationships and integrity."""
    
    def test_game_state_action_history_integration(self):
        """Test that actions can be properly stored in game state history."""
        action = Action(ActionType.BUILD_SETTLEMENT, player_id=0, parameters={'point_coords': (1, 1)})
        state = GameState(action_history=[action])
        
        assert len(state.action_history) == 1
        assert state.action_history[0].action_type == ActionType.BUILD_SETTLEMENT
    
    def test_player_state_data_consistency(self):
        """Test player state data consistency."""
        player = PlayerState(
            player_id=0,
            name="Test Player",
            cards=['wood', 'brick'],
            dev_cards=['knight'],
            settlements=[(1, 1)],
            cities=[(2, 2)],
            roads=[((1, 1), (1, 2))],
            victory_points=3,
            longest_road_length=5,
            has_longest_road=True,
            has_largest_army=False,
            knights_played=2
        )
        
        assert player.player_id == 0
        assert len(player.cards) == 2
        assert len(player.dev_cards) == 1
        assert len(player.settlements) == 1
        assert len(player.cities) == 1
        assert len(player.roads) == 1
    
    def test_action_timestamp_creation(self):
        """Test that action timestamp is properly set."""
        import time
        
        # Record time before and after action creation
        time_before = datetime.now()
        time.sleep(0.001)  # Small delay to ensure timestamp difference
        action = Action(ActionType.END_TURN, player_id=0)
        time.sleep(0.001)
        time_after = datetime.now()
        
        # Verify timestamp is between before and after
        assert time_before < action.timestamp < time_after


if __name__ == '__main__':
    pytest.main([__file__, '-v'])