"""
Unit tests for pycatan.user module.

Tests the abstract User class, validation functions, and test utilities.
"""

import pytest
from abc import ABC
from unittest.mock import Mock

from pycatan.actions import Action, ActionType, GameState
from pycatan.user import User, UserInputError, validate_user_list, create_test_user


class TestUserAbstract:
    """Test User abstract base class."""
    
    def test_user_is_abstract(self):
        """Test that User is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            User("Test", 0)
    
    def test_user_abstract_method(self):
        """Test that get_input is abstract and must be implemented."""
        # Create a class that inherits from User but doesn't implement get_input
        class IncompleteUser(User):
            pass
        
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteUser("Test", 0)
    
    def test_concrete_user_implementation(self):
        """Test that concrete User implementations work correctly."""
        class ConcreteUser(User):
            def get_input(self, game_state, prompt_message, allowed_actions=None):
                return Action(ActionType.END_TURN, self.user_id)
        
        user = ConcreteUser("TestUser", 0)
        assert user.name == "TestUser"
        assert user.user_id == 0
        assert user.is_active is True


class TestUserBasicFunctionality:
    """Test basic User functionality using test user."""
    
    def setup_method(self):
        """Set up test user for each test."""
        self.user = create_test_user("Alice", 0)
    
    def test_user_initialization(self):
        """Test user initialization."""
        assert self.user.name == "Alice"
        assert self.user.user_id == 0
        assert self.user.is_active is True
    
    def test_user_active_property(self):
        """Test active property getter and setter."""
        assert self.user.is_active is True
        
        self.user.set_active(False)
        assert self.user.is_active is False
        
        self.user.set_active(True)
        assert self.user.is_active is True
    
    def test_user_string_representation(self):
        """Test string representations."""
        str_repr = str(self.user)
        assert "TestUser" in str_repr
        assert "Alice" in str_repr
        assert "0" in str_repr
        
        detailed_repr = repr(self.user)
        assert "TestUser" in detailed_repr
        assert "Alice" in detailed_repr
        assert "0" in detailed_repr
        assert "active" in detailed_repr
    
    def test_user_string_representation_inactive(self):
        """Test string representation when inactive."""
        self.user.set_active(False)
        detailed_repr = repr(self.user)
        assert "inactive" in detailed_repr
    
    def test_notify_action_default(self):
        """Test that notify_action has a default implementation."""
        action = Action(ActionType.END_TURN, 0)
        # Should not raise exception
        self.user.notify_action(action, True, "Success")
        self.user.notify_action(action, False, "Failed")
    
    def test_notify_game_event_default(self):
        """Test that notify_game_event has a default implementation."""
        # Should not raise exception
        self.user.notify_game_event("dice_roll", "Player rolled 7", [0, 1])
        self.user.notify_game_event("trade", "Trade completed")


class TestUserInput:
    """Test User input functionality."""
    
    def setup_method(self):
        """Set up test user for each test."""
        self.user = create_test_user("Bob", 1)
        self.game_state = GameState()
    
    def test_get_input_called_with_parameters(self):
        """Test that get_input is called with correct parameters."""
        result = self.user.get_input(self.game_state, "Choose action", ["BUILD", "TRADE"])
        
        # Check that the call was recorded
        assert self.user.last_input_call is not None
        assert self.user.last_input_call['game_state'] == self.game_state
        assert self.user.last_input_call['prompt_message'] == "Choose action"
        assert self.user.last_input_call['allowed_actions'] == ["BUILD", "TRADE"]
        
        # Check default return value
        assert result.action_type == ActionType.END_TURN
        assert result.player_id == 1
    
    def test_get_input_with_preset_action(self):
        """Test get_input with pre-configured action."""
        expected_action = Action(ActionType.BUILD_SETTLEMENT, 1, {'point_coords': (2, 3)})
        self.user.set_next_action(expected_action)
        
        result = self.user.get_input(self.game_state, "Build something")
        
        assert result == expected_action
    
    def test_get_input_minimal_parameters(self):
        """Test get_input with minimal parameters."""
        result = self.user.get_input(self.game_state, "Your turn")
        
        assert self.user.last_input_call['allowed_actions'] is None
        assert result.action_type == ActionType.END_TURN


class TestUserInputError:
    """Test UserInputError exception."""
    
    def test_user_input_error_creation(self):
        """Test creating UserInputError."""
        error = UserInputError("Invalid input")
        
        assert str(error) == "Invalid input"
        assert error.message == "Invalid input"
        assert error.user is None
    
    def test_user_input_error_with_user(self):
        """Test creating UserInputError with user."""
        user = create_test_user("Charlie", 2)
        error = UserInputError("Bad command", user)
        
        assert error.message == "Bad command"
        assert error.user == user
    
    def test_user_input_error_inheritance(self):
        """Test that UserInputError inherits from Exception."""
        error = UserInputError("Test error")
        assert isinstance(error, Exception)


class TestValidateUserList:
    """Test validate_user_list function."""
    
    def test_validate_empty_list(self):
        """Test validation fails for empty list."""
        with pytest.raises(ValueError, match="User list cannot be empty"):
            validate_user_list([])
    
    def test_validate_single_user(self):
        """Test validation succeeds for single user."""
        users = [create_test_user("Alice", 0)]
        assert validate_user_list(users) is True
    
    def test_validate_multiple_users(self):
        """Test validation succeeds for multiple valid users."""
        users = [
            create_test_user("Alice", 0),
            create_test_user("Bob", 1),
            create_test_user("Charlie", 2)
        ]
        assert validate_user_list(users) is True
    
    def test_validate_duplicate_ids(self):
        """Test validation fails for duplicate user IDs."""
        users = [
            create_test_user("Alice", 0),
            create_test_user("Bob", 0)  # Duplicate ID
        ]
        with pytest.raises(ValueError, match="All user IDs must be unique"):
            validate_user_list(users)
    
    def test_validate_empty_name(self):
        """Test validation fails for empty user name."""
        users = [
            create_test_user("Alice", 0),
            create_test_user("", 1)  # Empty name
        ]
        with pytest.raises(ValueError, match="User 1 has empty name"):
            validate_user_list(users)
    
    def test_validate_whitespace_name(self):
        """Test validation fails for whitespace-only name."""
        users = [
            create_test_user("Alice", 0),
            create_test_user("   ", 1)  # Whitespace name
        ]
        with pytest.raises(ValueError, match="User 1 has empty name"):
            validate_user_list(users)
    
    def test_validate_non_sequential_ids(self):
        """Test validation fails for non-sequential IDs."""
        users = [
            create_test_user("Alice", 0),
            create_test_user("Bob", 2)  # Missing ID 1
        ]
        with pytest.raises(ValueError, match="User IDs must be sequential"):
            validate_user_list(users)
    
    def test_validate_ids_not_starting_from_zero(self):
        """Test validation fails when IDs don't start from 0."""
        users = [
            create_test_user("Alice", 1),  # Should start from 0
            create_test_user("Bob", 2)
        ]
        with pytest.raises(ValueError, match="User IDs must be sequential"):
            validate_user_list(users)


class TestCreateTestUser:
    """Test create_test_user utility function."""
    
    def test_create_test_user_basic(self):
        """Test creating a basic test user."""
        user = create_test_user("TestUser", 5)
        
        assert user.name == "TestUser"
        assert user.user_id == 5
        assert user.is_active is True
        assert isinstance(user, User)
    
    def test_create_test_user_has_test_features(self):
        """Test that test user has testing-specific features."""
        user = create_test_user("TestUser", 0)
        
        # Should have test-specific attributes
        assert hasattr(user, 'last_input_call')
        assert hasattr(user, 'next_action')
        assert hasattr(user, 'set_next_action')
        
        # Initial values
        assert user.last_input_call is None
        assert user.next_action is None
    
    def test_test_user_inheritance(self):
        """Test that test user properly inherits from User."""
        user = create_test_user("Inherit", 0)
        
        # Should have User methods
        assert hasattr(user, 'get_input')
        assert hasattr(user, 'notify_action')
        assert hasattr(user, 'notify_game_event')
        assert hasattr(user, 'is_active')
        assert hasattr(user, 'set_active')


class TestUserIntegration:
    """Integration tests for User with other components."""
    
    def test_user_with_game_state(self):
        """Test User interaction with GameState."""
        user = create_test_user("Integration", 0)
        game_state = GameState()
        game_state.current_player = 0
        game_state.turn_number = 5
        
        action = user.get_input(game_state, "Your move")
        
        # Verify the call was made with the game state
        assert user.last_input_call['game_state'] == game_state
        assert action.player_id == user.user_id
    
    def test_user_action_consistency(self):
        """Test that user actions are consistent with user ID."""
        user = create_test_user("Consistent", 3)
        expected_action = Action(ActionType.TRADE_PROPOSE, 3, {
            'offer': {'wood': 1},
            'request': {'brick': 1},
            'target_player': 0
        })
        user.set_next_action(expected_action)
        
        result = user.get_input(GameState(), "Trade time")
        
        assert result.player_id == user.user_id
        assert result == expected_action


if __name__ == '__main__':
    pytest.main([__file__, '-v'])