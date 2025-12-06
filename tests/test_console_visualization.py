"""
Tests for the visualization module.

This module tests the visualization base classes and console visualization
implementation to ensure proper display functionality.
"""

import unittest
from unittest.mock import patch
from io import StringIO

from pycatan.visualization import Visualization, VisualizationManager
from pycatan.console_visualization import ConsoleVisualization
from pycatan.actions import Action, ActionResult, ActionType
from pycatan.card import ResCard, DevCard


class MockVisualization(Visualization):
    """Mock visualization implementation for testing."""
    
    def __init__(self, name: str = "Mock"):
        super().__init__(name)
        self.calls = []  # Track method calls
    
    def display_game_state(self, game_state):
        self.calls.append(('display_game_state', game_state))
    
    def display_action(self, action, result):
        self.calls.append(('display_action', action, result))
    
    def display_turn_start(self, player_name, turn_number):
        self.calls.append(('display_turn_start', player_name, turn_number))
    
    def display_dice_roll(self, player_name, dice_values, total):
        self.calls.append(('display_dice_roll', player_name, dice_values, total))
    
    def display_resource_distribution(self, distributions):
        self.calls.append(('display_resource_distribution', distributions))
    
    def display_error(self, message):
        self.calls.append(('display_error', message))
    
    def display_message(self, message):
        self.calls.append(('display_message', message))


class TestVisualization(unittest.TestCase):
    """Test the base Visualization class."""
    
    def test_visualization_creation(self):
        """Test basic visualization creation."""
        viz = MockVisualization("Test")
        self.assertEqual(viz.name, "Test")
        self.assertTrue(viz.enabled)
        self.assertTrue(viz.is_enabled())
    
    def test_enable_disable(self):
        """Test enabling and disabling visualization."""
        viz = MockVisualization()
        
        # Should start enabled
        self.assertTrue(viz.is_enabled())
        
        # Test disable
        viz.disable()
        self.assertFalse(viz.is_enabled())
        
        # Test enable
        viz.enable()
        self.assertTrue(viz.is_enabled())


class TestVisualizationManager(unittest.TestCase):
    """Test the VisualizationManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = VisualizationManager()
        self.viz1 = MockVisualization("Viz1")
        self.viz2 = MockVisualization("Viz2")
    
    def test_manager_creation(self):
        """Test manager creation."""
        self.assertEqual(self.manager.get_visualization_count(), 0)
        self.assertEqual(self.manager.get_enabled_count(), 0)
    
    def test_add_remove_visualizations(self):
        """Test adding and removing visualizations."""
        # Add visualizations
        self.manager.add_visualization(self.viz1)
        self.assertEqual(self.manager.get_visualization_count(), 1)
        self.assertEqual(self.manager.get_enabled_count(), 1)
        
        self.manager.add_visualization(self.viz2)
        self.assertEqual(self.manager.get_visualization_count(), 2)
        self.assertEqual(self.manager.get_enabled_count(), 2)
        
        # Remove visualization
        self.manager.remove_visualization(self.viz1)
        self.assertEqual(self.manager.get_visualization_count(), 1)
        self.assertEqual(self.manager.get_enabled_count(), 1)
    
    def test_display_methods(self):
        """Test that manager calls all enabled visualizations."""
        self.manager.add_visualization(self.viz1)
        self.manager.add_visualization(self.viz2)
        
        # Test game state display
        game_state = {'turn': 1, 'players': []}
        self.manager.display_game_state(game_state)
        
        self.assertIn(('display_game_state', game_state), self.viz1.calls)
        self.assertIn(('display_game_state', game_state), self.viz2.calls)
        
        # Test action display with valid parameters
        action = Action(ActionType.END_TURN, player_id="player1")  # No required params
        result = ActionResult(True, "Success")
        self.manager.display_action(action, result)
        
        self.assertIn(('display_action', action, result), self.viz1.calls)
        self.assertIn(('display_action', action, result), self.viz2.calls)
    
    def test_disabled_visualization_not_called(self):
        """Test that disabled visualizations are not called."""
        self.manager.add_visualization(self.viz1)
        self.manager.add_visualization(self.viz2)
        
        # Disable viz2
        self.viz2.disable()
        self.assertEqual(self.manager.get_enabled_count(), 1)
        
        # Display something
        self.manager.display_message("Test message")
        
        # Only viz1 should be called
        self.assertIn(('display_message', "Test message"), self.viz1.calls)
        self.assertNotIn(('display_message', "Test message"), self.viz2.calls)


class TestConsoleVisualization(unittest.TestCase):
    """Test the ConsoleVisualization class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.console = ConsoleVisualization(use_colors=False)  # No colors for easier testing
    
    def test_console_creation(self):
        """Test console visualization creation."""
        self.assertEqual(self.console.name, "Console")
        self.assertTrue(self.console.is_enabled())
        self.assertFalse(self.console.use_colors)
    
    def test_console_with_colors(self):
        """Test console with colors enabled."""
        console = ConsoleVisualization(use_colors=True)
        self.assertTrue(console.use_colors)
        self.assertIn('red', console.colors)
        self.assertTrue(console.colors['red'])  # Should have ANSI codes
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_message(self, mock_stdout):
        """Test displaying a simple message."""
        self.console.display_message("Test message")
        output = mock_stdout.getvalue()
        self.assertIn("Test message", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_error(self, mock_stdout):
        """Test displaying an error message."""
        self.console.display_error("Test error")
        output = mock_stdout.getvalue()
        self.assertIn("Test error", output)
        self.assertIn("Error", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_dice_roll(self, mock_stdout):
        """Test displaying dice roll."""
        self.console.display_dice_roll("Alice", [3, 4], 7)
        output = mock_stdout.getvalue()
        self.assertIn("Alice", output)
        self.assertIn("3", output)
        self.assertIn("4", output)
        self.assertIn("7", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_turn_start(self, mock_stdout):
        """Test displaying turn start."""
        self.console.display_turn_start("Bob", 5)
        output = mock_stdout.getvalue()
        self.assertIn("Bob", output)
        self.assertIn("5", output)
        self.assertIn("turn", output.lower())
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_game_state(self, mock_stdout):
        """Test displaying game state."""
        game_state = {
            'turn_number': 3,
            'current_player_name': 'Alice',
            'current_player_index': 0,
            'players': [
                {
                    'name': 'Alice',
                    'victory_points': 5,
                    'cards': [ResCard.Wood, ResCard.Brick, ResCard.Wood],
                    'dev_cards': [],
                    'settlements': 2,
                    'cities': 1,
                    'roads': 3
                },
                {
                    'name': 'Bob',
                    'victory_points': 3,
                    'cards': [ResCard.Sheep, ResCard.Wheat],
                    'dev_cards': [DevCard.Knight],
                    'settlements': 1,
                    'cities': 0,
                    'roads': 2
                }
            ],
            'board': {},
            'robber_position': [2, 1]
        }
        
        self.console.display_game_state(game_state)
        output = mock_stdout.getvalue()
        
        # Check that key information is displayed
        self.assertIn("GAME STATE", output)
        self.assertIn("Alice", output)
        self.assertIn("Bob", output)
        self.assertIn("Turn: 3", output)
        self.assertIn("Victory Points", output)
        self.assertIn("Resources", output)
        self.assertIn("Buildings", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_action(self, mock_stdout):
        """Test displaying action results."""
        action = Action(ActionType.BUILD_SETTLEMENT, 
                       player_id="alice",
                       parameters={'player_name': 'Alice', 'point_coords': [1, 2]})
        result = ActionResult(True, "Settlement built successfully")
        
        self.console.display_action(action, result)
        output = mock_stdout.getvalue()
        
        self.assertIn("Alice", output)
        self.assertIn("settlement", output)
        self.assertIn("✓", output)  # Success symbol
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_failed_action(self, mock_stdout):
        """Test displaying failed action."""
        action = Action(ActionType.BUILD_ROAD, 
                       player_id="bob",
                       parameters={'player_name': 'Bob', 'start_coords': [1, 2], 'end_coords': [2, 3]})
        result = ActionResult(False, "Not enough resources")
        
        self.console.display_action(action, result)
        output = mock_stdout.getvalue()
        
        self.assertIn("Bob", output)
        self.assertIn("road", output)
        self.assertIn("✗", output)  # Failure symbol
        self.assertIn("Not enough resources", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_resource_distribution(self, mock_stdout):
        """Test displaying resource distribution."""
        distributions = {
            'Alice': ['Wood', 'Brick'],
            'Bob': ['Sheep'],
            'Charlie': []
        }
        
        self.console.display_resource_distribution(distributions)
        output = mock_stdout.getvalue()
        
        self.assertIn("Resources distributed", output)
        self.assertIn("Alice: Wood, Brick", output)
        self.assertIn("Bob: Sheep", output)
    
    def test_disabled_console_no_output(self):
        """Test that disabled console produces no output."""
        self.console.disable()
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            self.console.display_message("This should not appear")
            output = mock_stdout.getvalue()
            self.assertEqual(output, "")
    
    def test_compact_mode(self):
        """Test compact mode setting."""
        self.assertFalse(self.console.compact_mode)
        
        self.console.set_compact_mode(True)
        self.assertTrue(self.console.compact_mode)
        
        self.console.set_compact_mode(False)
        self.assertFalse(self.console.compact_mode)
    
    def test_colors_setting(self):
        """Test color setting functionality."""
        console = ConsoleVisualization(use_colors=True)
        self.assertTrue(console.use_colors)
        
        # Disable colors
        console.set_colors(False)
        self.assertFalse(console.use_colors)
        # All color codes should be empty
        for color_code in console.colors.values():
            self.assertEqual(color_code, "")
    
    def test_action_descriptions(self):
        """Test action description generation."""
        # Test various action types with valid parameters
        actions_and_expected = [
            (Action(ActionType.BUILD_SETTLEMENT, 
                   player_id="alice",
                   parameters={'player_name': 'Alice', 'point_coords': [1, 2]}), "settlement"),
            (Action(ActionType.BUILD_CITY,
                   player_id="bob", 
                   parameters={'player_name': 'Bob', 'point_coords': [2, 3]}), "city"),
            (Action(ActionType.BUILD_ROAD,
                   player_id="charlie",
                   parameters={'player_name': 'Charlie', 'start_coords': [1, 2], 'end_coords': [2, 3]}), "road"),
            (Action(ActionType.BUY_DEV_CARD,
                   player_id="dave",
                   parameters={'player_name': 'Dave'}), "development card"),
            (Action(ActionType.END_TURN,
                   player_id="eve",
                   parameters={'player_name': 'Eve'}), "ended their turn"),
        ]
        
        for action, expected in actions_and_expected:
            description = self.console._get_action_description(action)
            self.assertIn(expected, description.lower())
            self.assertIn(action.parameters['player_name'], description)


if __name__ == '__main__':
    unittest.main()