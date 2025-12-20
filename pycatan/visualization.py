"""
Visualization base class for PyCatan game display.

This module provides the abstract base class for all visualization implementations.
Different visualization types (console, web, log) inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from .actions import Action, ActionResult
from .log_events import LogEntry


class Visualization(ABC):
    """
    Abstract base class for game visualizations.
    
    All visualization implementations must inherit from this class and implement
    the required methods for displaying game state and actions.
    """
    
    def __init__(self, name: str):
        """
        Initialize the visualization.
        
        Args:
            name: Display name for this visualization type
        """
        self.name = name
        self.enabled = True
    
    @abstractmethod
    def display_game_state(self, game_state: Dict[str, Any]) -> None:
        """
        Display the complete game state.
        
        This is called when a full state update is needed, typically at the
        start of each turn or when a player requests to see the current state.
        
        Args:
            game_state: Complete game state dictionary containing:
                - board: Board state with tiles, points, buildings
                - players: Player information including cards, buildings, score
                - current_player: Index of current player
                - turn_number: Current turn number
                - robber_position: Current robber location
        """
        pass
    
    @abstractmethod
    def display_action(self, action: Action, result: ActionResult) -> None:
        """
        Display a single action and its result.
        
        This is called immediately after an action is executed to show
        what happened and whether it was successful.
        
        Args:
            action: The action that was attempted
            result: The result of the action execution
        """
        pass
    
    @abstractmethod
    def display_turn_start(self, player_name: str, turn_number: int) -> None:
        """
        Display turn start notification.
        
        Args:
            player_name: Name of the player whose turn is starting
            turn_number: Current turn number
        """
        pass
    
    @abstractmethod
    def display_dice_roll(self, player_name: str, dice_values: List[int], total: int) -> None:
        """
        Display dice roll results.
        
        Args:
            player_name: Name of the player who rolled
            dice_values: List of individual die values [die1, die2]
            total: Sum of the dice
        """
        pass
    
    @abstractmethod
    def display_resource_distribution(self, distributions: Dict[str, List[str]]) -> None:
        """
        Display resource distribution from dice roll.
        
        Args:
            distributions: Dictionary mapping player names to lists of resources received
        """
        pass
    
    @abstractmethod
    def display_error(self, message: str) -> None:
        """
        Display error message.
        
        Args:
            message: Error message to display
        """
        pass
    
    @abstractmethod
    def display_message(self, message: str) -> None:
        """
        Display general information message.
        
        Args:
            message: Message to display
        """
        pass
    
    def enable(self) -> None:
        """Enable this visualization."""
        self.enabled = True
    
    def disable(self) -> None:
        """Disable this visualization."""
        self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if this visualization is enabled."""
        return self.enabled


class VisualizationManager:
    """
    Manages multiple visualization instances.
    
    This class coordinates updates across multiple visualizations,
    allowing the game to display information through console, web, log, etc.
    simultaneously.
    """
    
    def __init__(self):
        """Initialize the visualization manager."""
        self.visualizations: List[Visualization] = []
    
    def add_visualization(self, visualization: Visualization) -> None:
        """
        Add a visualization to the manager.
        
        Args:
            visualization: Visualization instance to add
        """
        self.visualizations.append(visualization)
    
    def remove_visualization(self, visualization: Visualization) -> None:
        """
        Remove a visualization from the manager.
        
        Args:
            visualization: Visualization instance to remove
        """
        if visualization in self.visualizations:
            self.visualizations.remove(visualization)
    
    def display_game_state(self, game_state: Dict[str, Any]) -> None:
        """Update all enabled visualizations with game state."""
        for viz in self.visualizations:
            if viz.is_enabled():
                viz.display_game_state(game_state)
    
    def display_action(self, action: Action, result: ActionResult) -> None:
        """Update all enabled visualizations with action result."""
        for viz in self.visualizations:
            if viz.is_enabled():
                viz.display_action(action, result)
    
    def display_turn_start(self, player_name: str, turn_number: int) -> None:
        """Update all enabled visualizations with turn start."""
        for viz in self.visualizations:
            if viz.is_enabled():
                viz.display_turn_start(player_name, turn_number)
    
    def display_dice_roll(self, player_name: str, dice_values: List[int], total: int) -> None:
        """Update all enabled visualizations with dice roll."""
        for viz in self.visualizations:
            if viz.is_enabled():
                viz.display_dice_roll(player_name, dice_values, total)
    
    def display_resource_distribution(self, distributions: Dict[str, List[str]]) -> None:
        """Update all enabled visualizations with resource distribution."""
        for viz in self.visualizations:
            if viz.is_enabled():
                viz.display_resource_distribution(distributions)
    
    def display_error(self, message: str) -> None:
        """Update all enabled visualizations with error message."""
        for viz in self.visualizations:
            if viz.is_enabled():
                viz.display_error(message)
    
    def display_message(self, message: str) -> None:
        """Update all enabled visualizations with message."""
        for viz in self.visualizations:
            if viz.is_enabled():
                viz.display_message(message)
    
    def log_event(self, log_entry: LogEntry) -> None:
        """Log a structured event to all enabled visualizations."""
        for viz in self.visualizations:
            if viz.is_enabled() and hasattr(viz, 'log_event'):
                viz.log_event(log_entry)
    
    def get_visualization_count(self) -> int:
        """Get the number of registered visualizations."""
        return len(self.visualizations)
    
    def get_enabled_count(self) -> int:
        """Get the number of enabled visualizations."""
        return sum(1 for viz in self.visualizations if viz.is_enabled())