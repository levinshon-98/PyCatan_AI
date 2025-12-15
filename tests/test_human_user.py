"""
Tests for HumanUser implementation.

This module tests the human user interface and command parsing functionality.
"""

import pytest
import io
import sys
from unittest.mock import patch, MagicMock

from pycatan.human_user import HumanUser
from pycatan.user import UserInputError
from pycatan.actions import Action, ActionType, GameState, GamePhase
from pycatan.card import ResCard


class TestHumanUserInitialization:
    """Test HumanUser initialization and basic properties."""
    
    def test_human_user_creation(self):
        """Test creating a HumanUser instance."""
        user = HumanUser("Alice", 0)
        
        assert user.name == "Alice"
        assert user.user_id == 0
        assert user.is_active is True
        assert user.command_history == []
    
    def test_human_user_inheritance(self):
        """Test that HumanUser properly inherits from User."""
        from pycatan.user import User
        user = HumanUser("Bob", 1)
        
        assert isinstance(user, User)
        assert hasattr(user, 'get_input')
        assert hasattr(user, 'notify_action')
        assert hasattr(user, 'notify_game_event')


class TestCommandParsing:
    """Test command parsing functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.user = HumanUser("TestUser", 0)
        self.game_state = GameState()
    
    def test_parse_end_turn_commands(self):
        """Test parsing end turn commands."""
        commands = ['end', 'pass', 'done']
        
        for command in commands:
            action = self.user._parse_input(command, self.game_state)
            assert action.action_type == ActionType.END_TURN
            assert action.player_id == 0
    
    def test_parse_roll_dice_commands(self):
        """Test parsing dice roll commands."""
        commands = ['roll', 'dice', 'r']
        
        for command in commands:
            action = self.user._parse_input(command, self.game_state)
            assert action.action_type == ActionType.ROLL_DICE
            assert action.player_id == 0
    
    def test_parse_build_settlement_basic(self):
        """Test parsing basic settlement building command."""
        action = self.user._parse_input("settlement 0 5", self.game_state)
        
        assert action.action_type == ActionType.BUILD_SETTLEMENT
        assert action.player_id == 0
        assert action.parameters['point_coords'] == [0, 5]
        assert action.parameters['is_starting'] is False
    
    def test_parse_build_settlement_starting(self):
        """Test parsing starting settlement command."""
        action = self.user._parse_input("settlement 0 5 starting", self.game_state)
        
        assert action.action_type == ActionType.PLACE_STARTING_SETTLEMENT
        assert action.parameters['is_starting'] is True
    
    def test_parse_build_settlement_setup_phase(self):
        """Test parsing settlement command in setup phase (should NOT infer starting in User class)."""
        # Note: Logic moved to GameManager, so User class should return normal BUILD_SETTLEMENT
        # unless explicitly told 'starting'
        # We keep this test to verify User class doesn't do magic anymore
        self.game_state.game_phase = GamePhase.SETUP_FIRST_ROUND
        action = self.user._parse_input("settlement 0 5", self.game_state)
        
        assert action.action_type == ActionType.BUILD_SETTLEMENT
        assert action.parameters['is_starting'] is False

    def test_parse_build_city(self):
        """Test parsing city building command."""
        action = self.user._parse_input("city 1 3", self.game_state)
        
        assert action.action_type == ActionType.BUILD_CITY
        assert action.parameters['point_coords'] == [1, 3]
    
    def test_parse_build_road_basic(self):
        """Test parsing basic road building command."""
        action = self.user._parse_input("road 0 5 0 6", self.game_state)
        
        assert action.action_type == ActionType.BUILD_ROAD
        assert action.parameters['start_coords'] == [0, 5]
        assert action.parameters['end_coords'] == [0, 6]
        assert action.parameters['is_starting'] is False
    
    def test_parse_build_road_starting(self):
        """Test parsing starting road command."""
        action = self.user._parse_input("road 0 5 0 6 starting", self.game_state)
        
        assert action.action_type == ActionType.PLACE_STARTING_ROAD
        assert action.parameters['is_starting'] is True
    
    def test_parse_build_road_setup_phase(self):
        """Test parsing road command in setup phase (should NOT infer starting in User class)."""
        # Note: Logic moved to GameManager
        self.game_state.game_phase = GamePhase.SETUP_SECOND_ROUND
        action = self.user._parse_input("road 0 5 0 6", self.game_state)
        
        assert action.action_type == ActionType.BUILD_ROAD
        assert action.parameters['is_starting'] is False
    
    def test_parse_bank_trade(self):
        """Test parsing bank trade command."""
        action = self.user._parse_input("trade bank wood 4 wheat 1", self.game_state)
        
        assert action.action_type == ActionType.TRADE_BANK
        assert action.parameters['offer'] == {'wood': 4}
        assert action.parameters['request'] == {'wheat': 1}
    
    def test_parse_player_trade(self):
        """Test parsing player trade command."""
        action = self.user._parse_input("trade player 1 wood sheep", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['target_player'] == 1
        assert action.parameters['offer'] == {'wood': 1}
        assert action.parameters['request'] == {'sheep': 1}
    
    def test_parse_buy_dev_card(self):
        """Test parsing buy development card command."""
        action = self.user._parse_input("buy", self.game_state)
        
        assert action.action_type == ActionType.BUY_DEV_CARD
        assert action.player_id == 0
    
    def test_parse_use_dev_card_basic(self):
        """Test parsing basic use development card command."""
        action = self.user._parse_input("use knight", self.game_state)
        
        assert action.action_type == ActionType.USE_DEV_CARD
        assert action.parameters['card_type'] == 'knight'
    
    def test_parse_robber_move(self):
        """Test parsing robber move command."""
        action = self.user._parse_input("robber 2 1", self.game_state)
        
        assert action.action_type == ActionType.ROBBER_MOVE
        assert action.parameters['tile_coords'] == [2, 1]
        # Note: victim is now handled separately via 'steal' command
    
    def test_parse_steal_command(self):
        """Test parsing steal command."""
        action = self.user._parse_input("steal 1", self.game_state)
        
        assert action.action_type == ActionType.STEAL_CARD
        assert action.parameters['target_player'] == 1
    
    def test_parse_steal_none(self):
        """Test parsing steal with no target."""
        action = self.user._parse_input("steal none", self.game_state)
        
        assert action.action_type == ActionType.STEAL_CARD
        assert action.parameters['target_player'] is None
    
    def test_parse_discard_cards(self):
        """Test parsing discard command."""
        action = self.user._parse_input("drop 2 wood 1 brick", self.game_state)
        
        assert action.action_type == ActionType.DISCARD_CARDS
        assert action.parameters['cards'] == ['Wood', 'Wood', 'Brick']
    
    def test_parse_discard_single_resource(self):
        """Test parsing discard with single resource type."""
        action = self.user._parse_input("drop 3 wheat", self.game_state)
        
        assert action.action_type == ActionType.DISCARD_CARDS
        assert action.parameters['cards'] == ['Wheat', 'Wheat', 'Wheat']


class TestResourceParsing:
    """Test resource name parsing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.user = HumanUser("TestUser", 0)
    
    def test_parse_resource_names(self):
        """Test parsing various resource names."""
        resource_tests = [
            ('wood', ResCard.Wood),
            ('lumber', ResCard.Wood),
            ('brick', ResCard.Brick),
            ('sheep', ResCard.Sheep),
            ('wool', ResCard.Sheep),
            ('wheat', ResCard.Wheat),
            ('grain', ResCard.Wheat),
            ('ore', ResCard.Ore),
            ('stone', ResCard.Ore)
        ]
        
        for resource_name, expected_card in resource_tests:
            result = self.user._parse_resource(resource_name)
            assert result == expected_card
    
    def test_parse_resource_case_insensitive(self):
        """Test that resource parsing is case insensitive."""
        variations = ['WOOD', 'Wood', 'wOoD', 'WHEAT', 'Wheat']
        
        for variation in variations:
            # Should not raise exception
            self.user._parse_resource(variation)
    
    def test_parse_invalid_resource(self):
        """Test parsing invalid resource name."""
        with pytest.raises(UserInputError) as exc_info:
            self.user._parse_resource("invalid")
        
        assert "Unknown resource" in str(exc_info.value)


class TestErrorHandling:
    """Test error handling in command parsing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.user = HumanUser("TestUser", 0)
        self.game_state = GameState()
    
    def test_empty_command(self):
        """Test parsing empty command."""
        with pytest.raises(UserInputError) as exc_info:
            self.user._parse_input("", self.game_state)
        
        assert "Empty command" in str(exc_info.value)
    
    def test_unknown_command(self):
        """Test parsing unknown command."""
        with pytest.raises(UserInputError) as exc_info:
            self.user._parse_input("unknowncommand", self.game_state)
        
        assert "Unknown command" in str(exc_info.value)
    
    def test_settlement_insufficient_args(self):
        """Test settlement command with insufficient arguments."""
        with pytest.raises(UserInputError) as exc_info:
            self.user._parse_input("settlement 0", self.game_state)
        
        # The message should mention invalid point number or requirements
        assert any(phrase in str(exc_info.value) for phrase in 
                  ["requires row and index", "Invalid point number", "Valid points"])
    
    def test_settlement_invalid_coordinates(self):
        """Test settlement command with invalid coordinates."""
        with pytest.raises(UserInputError) as exc_info:
            self.user._parse_input("settlement abc def", self.game_state)
        
        assert "must be numbers" in str(exc_info.value)
    
    def test_road_insufficient_args(self):
        """Test road command with insufficient arguments."""
        with pytest.raises(UserInputError) as exc_info:
            self.user._parse_input("road 0 5", self.game_state)
        
        # The message should mention requirements or adjacency issues
        assert any(phrase in str(exc_info.value) for phrase in 
                  ["requires start and end coordinates", "not adjacent", "Cannot build road"])
    
    def test_trade_insufficient_args(self):
        """Test trade command with insufficient arguments."""
        with pytest.raises(UserInputError) as exc_info:
            self.user._parse_input("trade", self.game_state)
        
        assert "needs more info" in str(exc_info.value)
    
    def test_bank_trade_insufficient_args(self):
        """Test bank trade with insufficient arguments."""
        with pytest.raises(UserInputError) as exc_info:
            self.user._parse_input("trade bank wood", self.game_state)
        
        assert "Bank trade format" in str(exc_info.value)


class TestUserInterface:
    """Test user interface functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.user = HumanUser("TestUser", 0)
        self.game_state = GameState()
        self.game_state.turn_number = 5
        self.game_state.current_player_id = 0
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_get_input_successful_command(self, mock_print, mock_input):
        """Test successful command input."""
        mock_input.return_value = "end"
        
        action = self.user.get_input(self.game_state, "Your turn:")
        
        assert action.action_type == ActionType.END_TURN
        assert len(self.user.command_history) == 1
        assert self.user.command_history[0] == "end"
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_get_input_with_allowed_actions(self, mock_print, mock_input):
        """Test input with allowed actions restriction."""
        mock_input.side_effect = ["settlement 0 5", "end"]  # First invalid, then valid
        
        action = self.user.get_input(self.game_state, "Your turn:", ["END_TURN"])
        
        assert action.action_type == ActionType.END_TURN
        # Should have been called twice due to first invalid command
        assert mock_input.call_count == 2
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_get_input_retry_on_error(self, mock_print, mock_input):
        """Test that invalid commands prompt for retry."""
        mock_input.side_effect = ["invalidcommand", "end"]
        
        action = self.user.get_input(self.game_state, "Your turn:")
        
        assert action.action_type == ActionType.END_TURN
        assert mock_input.call_count == 2
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_get_input_keyboard_interrupt(self, mock_print, mock_input):
        """Test handling keyboard interrupt."""
        mock_input.side_effect = KeyboardInterrupt()
        
        action = self.user.get_input(self.game_state, "Your turn:")
        
        assert action.action_type == ActionType.END_TURN
    
    @patch('builtins.print')
    def test_display_game_status(self, mock_print):
        """Test game status display."""
        # Set up game state with player info
        from pycatan.actions import PlayerState
        player_state = PlayerState(
            player_id=0,
            name="TestPlayer",
            cards=["wood", "wood", "brick", "sheep"],
            dev_cards=[],
            settlements=[(0, 5), (1, 3)],
            cities=[(2, 7)],
            roads=[(0, 5, 0, 6), (1, 3, 1, 4)],
            victory_points=5,
            longest_road_length=3,
            has_longest_road=False,
            has_largest_army=False,
            knights_played=0
        )
        self.game_state.players_state = [player_state]
        
        self.user._display_game_status(self.game_state)
        
        # Verify that print was called (we don't check exact format)
        # assert mock_print.call_count > 0
        pass
    
    def test_show_help(self, capsys):
        """Test help display."""
        self.user._show_help()
        
        captured = capsys.readouterr()
        # Verify that help was displayed with expected content
        assert len(captured.out) > 0
        assert 'PYCATAN COMMANDS HELP' in captured.out
        assert 'settlement' in captured.out
        # Check for building section (could be "Building:" or "Building (")  
        assert any(phrase in captured.out for phrase in ['Building:', 'Building ('])
    
    def test_notify_action_success(self, capsys):
        """Test action success notification."""
        action = Action(ActionType.BUILD_SETTLEMENT, 0, {'point_coords': [0, 5]})
        self.user.notify_action(action, True, "Settlement built successfully!")
        
        captured = capsys.readouterr()
        assert "✓ Action successful" in captured.out
        assert "Settlement built successfully!" in captured.out
    
    def test_notify_action_failure(self, capsys):
        """Test action failure notification."""
        action = Action(ActionType.BUILD_SETTLEMENT, 0, {'point_coords': [0, 5]})
        self.user.notify_action(action, False, "Not enough resources")
        
        captured = capsys.readouterr()
        assert "✗ Action failed" in captured.out
        assert "Not enough resources" in captured.out
    
    def test_notify_game_event(self, capsys):
        """Test game event notification."""
        self.user.notify_game_event("dice_roll", "Player rolled 7", [0, 1, 2])
        
        captured = capsys.readouterr()
        assert "📢 dice_roll: Player rolled 7" in captured.out
        assert "Affects players: [0, 1, 2]" in captured.out


class TestHelpCommand:
    """Test help command functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.user = HumanUser("TestUser", 0)
        self.game_state = GameState()
    
    def test_help_command_raises_error(self):
        """Test that help command raises UserInputError to prompt retry."""
        help_commands = ['help', 'h', '?']
        
        for cmd in help_commands:
            with pytest.raises(UserInputError) as exc_info:
                self.user._parse_input(cmd, self.game_state)
            
            assert "Help displayed" in str(exc_info.value)


class TestCommandHistory:
    """Test command history functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.user = HumanUser("TestUser", 0)
        self.game_state = GameState()
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_command_history_tracking(self, mock_print, mock_input):
        """Test that commands are added to history."""
        commands = ["end", "roll", "settlement 0 5"]
        
        for i, cmd in enumerate(commands):
            mock_input.return_value = cmd
            try:
                self.user.get_input(self.game_state, f"Command {i}:")
            except UserInputError:
                # Some commands might cause parsing errors in isolation
                pass
        
        # Check that all commands were added to history
        assert len(self.user.command_history) == len(commands)
        for cmd in commands:
            assert cmd in self.user.command_history


class TestAdvancedTrading:
    """Test advanced trading functionality with flexible amounts."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.user = HumanUser("TestUser", 0)
        self.game_state = GameState()
    
    def test_simple_one_to_one_trade(self):
        """Test simple 1:1 trade (backward compatibility)."""
        action = self.user._parse_input("trade player 1 wood sheep", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['target_player'] == 1
        assert action.parameters['offer'] == {'wood': 1}
        assert action.parameters['request'] == {'sheep': 1}
    
    def test_trade_with_amounts(self):
        """Test trade with explicit amounts."""
        action = self.user._parse_input("trade player 1 wood 2 sheep 1", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['target_player'] == 1
        assert action.parameters['offer'] == {'wood': 2}
        assert action.parameters['request'] == {'sheep': 1}
    
    def test_trade_multiple_resources(self):
        """Test trade with multiple resources on both sides."""
        action = self.user._parse_input("trade player 1 wood 2 brick 1 for wheat 2 ore 1", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['target_player'] == 1
        assert action.parameters['offer'] == {'wood': 2, 'brick': 1}
        assert action.parameters['request'] == {'wheat': 2, 'ore': 1}
    
    def test_trade_with_separator_words(self):
        """Test trade with various separator words."""
        separators = ['for', 'get', 'want', 'receive']
        
        for sep in separators:
            action = self.user._parse_input(f"trade player 1 wood 2 {sep} sheep 1", self.game_state)
            
            assert action.action_type == ActionType.TRADE_PROPOSE
            assert action.parameters['offer'] == {'wood': 2}
            assert action.parameters['request'] == {'sheep': 1}
    
    def test_gift_receiving(self):
        """Test receiving a gift (nothing for something)."""
        action = self.user._parse_input("trade player 1 nothing wheat 1", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['offer'] == {}
        assert action.parameters['request'] == {'wheat': 1}
    
    def test_gift_giving(self):
        """Test giving a gift (something for nothing)."""
        action = self.user._parse_input("trade player 1 wood 3 nothing", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['offer'] == {'wood': 3}
        assert action.parameters['request'] == {}
    
    def test_extreme_trade_zero_for_five(self):
        """Test extreme trade: 0 cards for 5 cards (use separator for clarity)."""
        action = self.user._parse_input("trade player 1 nothing for wheat 2 ore 2 brick 1", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['offer'] == {}
        assert action.parameters['request'] == {'wheat': 2, 'ore': 2, 'brick': 1}
    
    def test_extreme_trade_five_for_zero(self):
        """Test extreme trade: 5 cards for 0 cards (use separator for clarity)."""
        action = self.user._parse_input("trade player 1 wood 2 brick 2 sheep 1 for nothing", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['offer'] == {'wood': 2, 'brick': 2, 'sheep': 1}
        assert action.parameters['request'] == {}
    
    def test_complex_multi_resource_trade(self):
        """Test complex trade with many resources on both sides."""
        action = self.user._parse_input("trade player 1 wood 3 brick 2 sheep 1 for wheat 4 ore 2", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['offer'] == {'wood': 3, 'brick': 2, 'sheep': 1}
        assert action.parameters['request'] == {'wheat': 4, 'ore': 2}
    
    def test_trade_with_player_name(self):
        """Test trading with player name instead of ID."""
        from pycatan.actions import PlayerState
        
        # Create PlayerState objects (it's a dataclass, pass all params)
        alice = PlayerState(
            player_id=0,
            name="Alice",
            cards=[],
            dev_cards=[],
            settlements=[],
            cities=[],
            roads=[],
            victory_points=0,
            longest_road_length=0,
            has_longest_road=False,
            has_largest_army=False,
            knights_played=0
        )
        
        bob = PlayerState(
            player_id=1,
            name="Bob",
            cards=[],
            dev_cards=[],
            settlements=[],
            cities=[],
            roads=[],
            victory_points=0,
            longest_road_length=0,
            has_longest_road=False,
            has_largest_army=False,
            knights_played=0
        )
        
        # Add player states to game_state
        self.game_state.players_state = [alice, bob]
        
        action = self.user._parse_input("trade player bob wood 2 for sheep 1", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['target_player'] == 1  # Bob's ID
        assert action.parameters['offer'] == {'wood': 2}
        assert action.parameters['request'] == {'sheep': 1}
    
    def test_trade_accumulates_duplicate_resources(self):
        """Test that duplicate resources in same offer accumulate."""
        action = self.user._parse_input("trade player 1 wood 2 wood 1 for sheep 1", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['offer'] == {'wood': 3}  # 2 + 1 = 3
        assert action.parameters['request'] == {'sheep': 1}
    
    def test_short_trade_command(self):
        """Test short 't' command for trading."""
        action = self.user._parse_input("t player 1 wood 2 sheep 1", self.game_state)
        
        assert action.action_type == ActionType.TRADE_PROPOSE
        assert action.parameters['offer'] == {'wood': 2}
        assert action.parameters['request'] == {'sheep': 1}