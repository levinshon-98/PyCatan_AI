"""
Unit tests for pycatan.game_manager module.

Tests the GameManager class and its basic functionality.
"""

import pytest
from unittest.mock import Mock, patch
import uuid

from pycatan.actions import Action, ActionType, ActionResult, GameState, GamePhase
from pycatan.user import create_test_user, UserInputError
from pycatan.game_manager import GameManager


class TestGameManagerInitialization:
    """Test GameManager initialization and basic properties."""
    
    def test_gamemanager_creation_basic(self):
        """Test basic GameManager creation."""
        users = [create_test_user("Alice", 0), create_test_user("Bob", 1)]
        gm = GameManager(users)
        
        assert gm.num_players == 2
        assert len(gm.users) == 2
        assert gm.current_player_id == 0
        assert not gm.is_running
        assert not gm.is_paused
        assert gm.game_id is not None
        assert len(gm.game_id) > 0
    
    def test_gamemanager_creation_with_config(self):
        """Test GameManager creation with custom config."""
        users = [create_test_user("Charlie", 0)]
        config = {"board_type": "custom", "victory_points": 15}
        gm = GameManager(users, config)
        
        assert gm.config == config
        assert gm.num_players == 1
    
    def test_gamemanager_invalid_users(self):
        """Test GameManager creation with invalid users."""
        # Empty users list
        with pytest.raises(ValueError, match="User list cannot be empty"):
            GameManager([])
        
        # Duplicate user IDs
        users = [create_test_user("Alice", 0), create_test_user("Bob", 0)]
        with pytest.raises(ValueError, match="All user IDs must be unique"):
            GameManager(users)
    
    def test_gamemanager_properties(self):
        """Test GameManager properties."""
        users = [
            create_test_user("Alice", 0),
            create_test_user("Bob", 1),
            create_test_user("Charlie", 2)
        ]
        gm = GameManager(users)
        
        assert gm.current_user == users[0]  # First user is current
        assert gm.current_user.name == "Alice"
        
        # Check game state
        state = gm.get_full_state()
        assert state.game_id == gm.game_id
        assert state.current_player == 0
        assert state.turn_number == 0
        assert state.game_phase == GamePhase.SETUP_FIRST_ROUND


class TestGameManagerFlow:
    """Test basic game flow operations."""
    
    def setup_method(self):
        """Set up test GameManager for each test."""
        self.users = [
            create_test_user("Alice", 0),
            create_test_user("Bob", 1)
        ]
        self.gm = GameManager(self.users)
    
    def test_start_game(self):
        """Test starting a game."""
        assert not self.gm.is_running
        
        result = self.gm.start_game()
        assert result is True
        assert self.gm.is_running
        assert not self.gm.is_paused
        
        # Can't start again
        result = self.gm.start_game()
        assert result is False
    
    def test_pause_resume_game(self):
        """Test pausing and resuming a game."""
        # Can't pause when not running
        assert not self.gm.pause_game()
        
        self.gm.start_game()
        
        # Can pause when running
        assert self.gm.pause_game()
        assert self.gm.is_paused
        
        # Can't pause when already paused
        assert not self.gm.pause_game()
        
        # Can resume when paused
        assert self.gm.resume_game()
        assert not self.gm.is_paused
        
        # Can't resume when not paused
        assert not self.gm.resume_game()
    
    def test_end_game(self):
        """Test ending a game."""
        # Can't end when not running
        assert not self.gm.end_game()
        
        self.gm.start_game()
        
        # Can end when running
        assert self.gm.end_game()
        assert not self.gm.is_running
        assert not self.gm.is_paused


class TestGameManagerActions:
    """Test action execution and handling."""
    
    def setup_method(self):
        """Set up test GameManager for each test."""
        self.users = [
            create_test_user("Alice", 0),
            create_test_user("Bob", 1)
        ]
        self.gm = GameManager(self.users)
    
    def test_execute_action_game_not_running(self):
        """Test executing action when game is not running."""
        action = Action(ActionType.END_TURN, player_id=0)
        
        result = self.gm.execute_action(action)
        
        assert not result.success
        assert "Game is not running" in result.error_message
        assert result.status_code == "GAME_NOT_RUNNING"
    
    def test_execute_action_wrong_turn(self):
        """Test executing action on wrong player's turn."""
        self.gm.start_game()
        action = Action(ActionType.END_TURN, player_id=1)  # Bob's action on Alice's turn
        
        result = self.gm.execute_action(action)
        
        assert not result.success
        assert "Not player 1's turn" in result.error_message
        assert result.status_code == "NOT_YOUR_TURN"
    
    def test_execute_action_end_turn(self):
        """Test executing end turn action."""
        self.gm.start_game()
        action = Action(ActionType.END_TURN, player_id=0)
        
        result = self.gm.execute_action(action)
        
        assert result.success
        assert self.gm.current_player_id == 1  # Switched to next player
        assert 0 in result.affected_players
        assert 1 in result.affected_players
    
    def test_execute_action_implemented_validation(self):
        """Test that building actions now work and validate properly."""
        self.gm.start_game()
        
        # Force game phase to NORMAL_PLAY to test resource validation
        self.gm._current_game_state.game_phase = GamePhase.NORMAL_PLAY
        
        # Test settlement building without starting mode (should fail due to cards)
        action = Action(ActionType.BUILD_SETTLEMENT, player_id=0, parameters={'point_coords': (1, 1)})
        result = self.gm.execute_action(action)
        
        assert not result.success
        assert "not enough cards" in result.error_message.lower()
        assert result.status_code == "INSUFFICIENT_RESOURCES"
        
        # Test settlement building with starting mode (should succeed)
        # Note: Even in NORMAL_PLAY, if we explicitly pass is_starting=True, it should work (legacy/testing support)
        action_starting = Action(ActionType.BUILD_SETTLEMENT, player_id=0, parameters={'point_coords': [0, 0], 'is_starting': True})
        result_starting = self.gm.execute_action(action_starting)
        
        assert result_starting.success
        assert result_starting.updated_state is not None

    def test_execute_action_setup_phase_inference(self):
        """Test that setup phase automatically infers is_starting=True."""
        self.gm.start_game()
        # Should be in SETUP_FIRST_ROUND by default
        assert self.gm._current_game_state.game_phase == GamePhase.SETUP_FIRST_ROUND
        
        # Test settlement building WITHOUT explicit is_starting=True
        # This should now SUCCEED because GameManager infers it from the phase
        action = Action(ActionType.BUILD_SETTLEMENT, player_id=0, parameters={'point_coords': [0, 0]})
        result = self.gm.execute_action(action)
        
        assert result.success
        assert result.status_code == "ALL_GOOD"
    
    def test_action_history(self):
        """Test that actions are recorded in history."""
        self.gm.start_game()
        
        action1 = Action(ActionType.END_TURN, player_id=0)
        action2 = Action(ActionType.END_TURN, player_id=1)
        
        self.gm.execute_action(action1)
        self.gm.execute_action(action2)
        
        history = self.gm.get_action_history()
        assert len(history) == 2
        assert history[0] == action1
        assert history[1] == action2


class TestGameManagerUserInteraction:
    """Test user interaction and input handling."""
    
    def setup_method(self):
        """Set up test GameManager for each test."""
        self.users = [
            create_test_user("Alice", 0),
            create_test_user("Bob", 1)
        ]
        self.gm = GameManager(self.users)
    
    def test_request_user_input_valid(self):
        """Test requesting input from a valid user."""
        user = self.users[0]
        expected_action = Action(ActionType.BUILD_SETTLEMENT, 0, {'point_coords': (1, 1)})
        user.set_next_action(expected_action)
        
        result = self.gm.request_user_input(0, "Build something")
        
        assert result == expected_action
        assert user.last_input_call is not None
        assert user.last_input_call['prompt_message'] == "Build something"
    
    def test_request_user_input_invalid_id(self):
        """Test requesting input with invalid user ID."""
        with pytest.raises(UserInputError, match="Invalid user ID"):
            self.gm.request_user_input(999, "Test")
    
    def test_request_user_input_inactive_user(self):
        """Test requesting input from inactive user."""
        self.users[0].set_active(False)
        
        with pytest.raises(UserInputError, match="User 0 is not active"):
            self.gm.request_user_input(0, "Test")
    
    def test_get_user_by_id(self):
        """Test getting user by ID."""
        user = self.gm.get_user_by_id(0)
        assert user == self.users[0]
        
        user = self.gm.get_user_by_id(1)
        assert user == self.users[1]
        
        user = self.gm.get_user_by_id(999)
        assert user is None


class TestGameManagerTurnManagement:
    """Test turn management and player rotation."""
    
    def setup_method(self):
        """Set up test GameManager for each test."""
        self.users = [
            create_test_user("Alice", 0),
            create_test_user("Bob", 1),
            create_test_user("Charlie", 2)
        ]
        self.gm = GameManager(self.users)
        self.gm.start_game()
    
    def test_turn_rotation(self):
        """Test that turns rotate correctly between players."""
        # Start with player 0
        assert self.gm.current_player_id == 0
        assert self.gm.current_user.name == "Alice"
        
        # End turn -> player 1
        self.gm.execute_action(Action(ActionType.END_TURN, 0))
        assert self.gm.current_player_id == 1
        assert self.gm.current_user.name == "Bob"
        
        # End turn -> player 2
        self.gm.execute_action(Action(ActionType.END_TURN, 1))
        assert self.gm.current_player_id == 2
        assert self.gm.current_user.name == "Charlie"
        
        # End turn -> back to player 0
        self.gm.execute_action(Action(ActionType.END_TURN, 2))
        assert self.gm.current_player_id == 0
        assert self.gm.current_user.name == "Alice"
    
    def test_turn_number_increments(self):
        """Test that turn number increments correctly."""
        initial_turn = self.gm.get_full_state().turn_number
        
        # Execute a few end turn actions
        for player_id in [0, 1, 2]:
            self.gm.execute_action(Action(ActionType.END_TURN, player_id))
        
        final_turn = self.gm.get_full_state().turn_number
        assert final_turn == initial_turn + 3


class TestGameManagerStringRepresentation:
    """Test string representations of GameManager."""
    
    def setup_method(self):
        """Set up test GameManager for each test."""
        self.users = [create_test_user("Alice", 0)]
        self.gm = GameManager(self.users)
    
    def test_str_representation(self):
        """Test string representation."""
        str_repr = str(self.gm)
        assert "GameManager" in str_repr
        assert "players=1" in str_repr
        assert "status=stopped" in str_repr
        
        self.gm.start_game()
        str_repr = str(self.gm)
        assert "status=running" in str_repr
        
        self.gm.pause_game()
        str_repr = str(self.gm)
        assert "status=paused" in str_repr
    
    def test_repr_representation(self):
        """Test detailed representation."""
        repr_str = repr(self.gm)
        assert "GameManager" in repr_str
        assert "players=1" in repr_str
        assert "current_player=0" in repr_str
        assert "turn=0" in repr_str
        assert "running=False" in repr_str
        assert "paused=False" in repr_str


class TestGameManagerIntegration:
    """Integration tests with actual game components."""
    
    def setup_method(self):
        """Set up test GameManager for each test."""
        self.users = [
            create_test_user("Alice", 0),
            create_test_user("Bob", 1)
        ]
        self.gm = GameManager(self.users)
    
    def test_integration_with_game_class(self):
        """Test that GameManager properly initializes Game class."""
        # GameManager should have created a Game instance
        assert self.gm.game is not None
        assert hasattr(self.gm.game, 'add_settlement')  # Verify it's the right type
        
        # Game should be initialized with correct number of players
        assert len(self.gm.game.players) == 2
    
    def test_game_state_consistency(self):
        """Test that game state remains consistent."""
        self.gm.start_game()
        
        state = self.gm.get_full_state()
        assert state.game_id == self.gm.game_id
        assert state.current_player == self.gm.current_player_id
        initial_turn = state.turn_number
        
        # After ending a turn, state should update
        self.gm.execute_action(Action(ActionType.END_TURN, 0))
        
        new_state = self.gm.get_full_state()
        assert new_state.current_player == 1
        assert new_state.turn_number == initial_turn + 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])