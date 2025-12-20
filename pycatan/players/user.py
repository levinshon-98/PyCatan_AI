"""
User Abstract Base Class for PyCatan Game Management

This module defines the abstract User class that serves as the foundation
for all types of users (human players, AI players) in the game system.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from pycatan.management.actions import Action, GameState


class User(ABC):
    """
    Abstract base class for all user types in the game.
    
    This class defines the interface that all user implementations must follow.
    Different user types (HumanUser, AIUser) inherit from this class and
    implement their own decision-making logic.
    """
    
    def __init__(self, name: str, user_id: int):
        """
        Initialize a User.
        
        Args:
            name: Display name for the user
            user_id: Unique identifier for this user (matches player_id in the game)
        """
        self.name = name
        self.user_id = user_id
        self._is_active = True
    
    @property
    def is_active(self) -> bool:
        """Whether this user is currently active in the game."""
        return self._is_active
    
    def set_active(self, active: bool) -> None:
        """Set the active state of this user."""
        self._is_active = active
    
    @abstractmethod
    def get_input(self, game_state: GameState, prompt_message: str, 
                  allowed_actions: Optional[List[str]] = None) -> Action:
        """
        Get the next action from this user.
        
        This is the core method that each user type must implement.
        The GameManager calls this method when it's the user's turn to act.
        
        Args:
            game_state: Current state of the game
            prompt_message: Message explaining what input is needed
            allowed_actions: Optional list of allowed action types for this situation
            
        Returns:
            Action: The action the user wants to perform
            
        Raises:
            NotImplementedError: If the subclass doesn't implement this method
        """
        pass
    
    def notify_action(self, action: Action, success: bool, message: str = "") -> None:
        """
        Notify the user about an action result.
        
        This method is called to inform the user about the outcome of actions,
        whether their own or other players'. Default implementation does nothing,
        but subclasses can override to provide feedback.
        
        Args:
            action: The action that was performed
            success: Whether the action succeeded
            message: Additional message about the result
        """
        pass
    
    def notify_game_event(self, event_type: str, message: str, 
                         affected_players: Optional[List[int]] = None) -> None:
        """
        Notify the user about general game events.
        
        This method is called to inform users about game-wide events like
        dice rolls, trades, robber moves, etc.
        
        Args:
            event_type: Type of event (e.g., "dice_roll", "trade_completed")
            message: Human-readable description of the event
            affected_players: List of player IDs affected by this event
        """
        pass
    
    def __str__(self) -> str:
        """String representation of the user."""
        return f"{self.__class__.__name__}(name='{self.name}', id={self.user_id})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the user."""
        active_status = "active" if self.is_active else "inactive"
        return f"{self.__class__.__name__}(name='{self.name}', id={self.user_id}, {active_status})"


class UserInputError(Exception):
    """
    Exception raised when user input is invalid or causes an error.
    
    This exception can be raised by User implementations when they encounter
    problems getting valid input from their respective sources.
    """
    
    def __init__(self, message: str, user: Optional[User] = None):
        """
        Initialize UserInputError.
        
        Args:
            message: Error description
            user: The user that caused the error (optional)
        """
        super().__init__(message)
        self.user = user
        self.message = message


# Type hints for user-related functions
UserList = List[User]


def validate_user_list(users: UserList) -> bool:
    """
    Validate a list of users for game setup.
    
    Checks that:
    - All users have unique IDs
    - All users have non-empty names
    - User IDs are sequential starting from 0
    
    Args:
        users: List of User objects to validate
        
    Returns:
        bool: True if the user list is valid
        
    Raises:
        ValueError: If validation fails with details about the issue
    """
    if not users:
        raise ValueError("User list cannot be empty")
    
    # Check for unique IDs
    user_ids = [user.user_id for user in users]
    if len(user_ids) != len(set(user_ids)):
        raise ValueError("All user IDs must be unique")
    
    # Check for non-empty names
    for user in users:
        if not user.name.strip():
            raise ValueError(f"User {user.user_id} has empty name")
    
    # Check that IDs are sequential starting from 0
    expected_ids = list(range(len(users)))
    if sorted(user_ids) != expected_ids:
        raise ValueError(f"User IDs must be sequential starting from 0. Expected: {expected_ids}, Got: {sorted(user_ids)}")
    
    return True


def create_test_user(name: str, user_id: int) -> User:
    """
    Create a test user for testing purposes.
    
    Args:
        name: Name for the test user
        user_id: ID for the test user
        
    Returns:
        TestUser: A concrete implementation of User for testing
    """
    
    class TestUser(User):
        """Simple test implementation of User."""
        
        def __init__(self, name: str, user_id: int):
            super().__init__(name, user_id)
            self.last_input_call = None
            self.next_action = None
        
        def get_input(self, game_state: GameState, prompt_message: str, 
                      allowed_actions: Optional[List[str]] = None) -> Action:
            """Return a pre-configured action for testing."""
            self.last_input_call = {
                'game_state': game_state,
                'prompt_message': prompt_message,
                'allowed_actions': allowed_actions
            }
            
            if self.next_action is None:
                from pycatan.management.actions import ActionType
                return Action(ActionType.END_TURN, self.user_id)
            
            return self.next_action
        
        def set_next_action(self, action: Action) -> None:
            """Set the action this test user will return on next get_input call."""
            self.next_action = action
    
    return TestUser(name, user_id)