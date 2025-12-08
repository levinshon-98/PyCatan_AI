"""
Human User Implementation for PyCatan Game Management

This module implements HumanUser, which provides a command-line interface
for human players to interact with the game.
"""

from typing import List, Optional, Dict, Tuple
from pycatan.user import User, UserInputError
from pycatan.actions import Action, ActionType, GameState
from pycatan.card import ResCard, DevCard
from pycatan.board_definition import board_definition


class HumanUser(User):
    """
    Human user implementation with command-line interface.
    
    This class provides a text-based interface for human players to interact
    with the game. It parses text commands and converts them to Action objects.
    """
    
    def __init__(self, name: str, user_id: int):
        """Initialize a HumanUser with CLI interface."""
        super().__init__(name, user_id)
        self.command_history = []
    
    def get_input(self, game_state: GameState, prompt_message: str, 
                  allowed_actions: Optional[List[str]] = None) -> Action:
        """
        Get input from human player via command line.
        
        Args:
            game_state: Current state of the game
            prompt_message: Message explaining what input is needed
            allowed_actions: Optional list of allowed action types
            
        Returns:
            Action: The action the player wants to perform
            
        Raises:
            UserInputError: If input parsing fails or action is invalid
        """
        while True:
            try:
                # Show game status
                self._display_game_status(game_state)
                
                # Show prompt with clear format
                print(f"\n>>> {self.name}'s Turn")
                
                # Show the prompt message if provided (important for context like "steal from X, Y, Z")
                if prompt_message and prompt_message.strip():
                    print(f"    💬 {prompt_message}")
                
                # Show allowed actions in a compact format
                if allowed_actions:
                    # Format actions nicely (e.g., "BUILD_SETTLEMENT" -> "build settlement")
                    formatted_actions = [self._format_action_name(a) for a in allowed_actions]
                    actions_str = " | ".join(formatted_actions)
                    print(f"    Options: {actions_str}")
                
                # Get user input with clean prompt
                user_input = input(f"    {self.name} > ").strip()
                
                if not user_input:
                    continue
                
                # Store in history
                self.command_history.append(user_input)
                
                # Parse the input into an action
                action = self._parse_input(user_input, game_state)
                
                # Validate against allowed actions if provided
                if allowed_actions and action.action_type.name not in allowed_actions:
                    print(f"    ✗ '{self._format_action_name(action.action_type.name)}' is not allowed right now.")
                    continue
                
                return action
                
            except UserInputError as e:
                print(f"    ✗ {e.message}")
            except KeyboardInterrupt:
                print("\n    Game interrupted by user.")
                return Action(ActionType.END_TURN, self.user_id)
    
    def _display_game_status(self, game_state: GameState) -> None:
        return
        """Display current game status to the user."""
        print("\n" + "="*60)
        print(f"🎮 GAME STATUS - Turn {game_state.turn_number}")
        print("="*60)
        
        # Show all players
        for player in game_state.players_state:
            is_current = player.player_id == game_state.current_player
            marker = "👉 " if is_current else "   "
            
            print(f"\n{marker}Player {player.player_id}: {player.name}")
            print(f"   🏆 Victory Points: {player.victory_points}")
            
            # Count resources
            resource_count = {}
            for card in player.cards:
                resource_count[card] = resource_count.get(card, 0) + 1
            
            if resource_count:
                # Show only if it's the current user or if viewing own cards
                if player.player_id == self.user_id:
                    print(f"   📦 Resources: ", end="")
                    cards_str = ", ".join([f"{count} {res}" for res, count in resource_count.items()])
                    print(cards_str)
                else:
                    # Just show total count for other players
                    print(f"   📦 Resources: {len(player.cards)} cards")
            else:
                print(f"   📦 Resources: none")
            
            print(f"   🏘️  Settlements: {len(player.settlements)} | Cities: {len(player.cities)} | Roads: {len(player.roads)}")
            
            if player.dev_cards:
                print(f"   🎴 Dev Cards: {len(player.dev_cards)}")
            
            if player.has_longest_road:
                print(f"   🛣️  Has Longest Road!")
            if player.has_largest_army:
                print(f"   ⚔️  Has Largest Army!")
        
        print("\n" + "="*60)
    
    def _format_action_name(self, action_name: str) -> str:
        """Convert action enum name to readable format."""
        # Convert "BUILD_SETTLEMENT" to "build settlement"
        words = action_name.replace("_", " ").lower()
        return words
    
    def _parse_input(self, user_input: str, game_state: GameState) -> Action:
        """
        Parse user input text into an Action object.
        
        Args:
            user_input: Text command from user
            game_state: Current game state for context
            
        Returns:
            Action: Parsed action
            
        Raises:
            UserInputError: If parsing fails
        """
        parts = user_input.lower().split()
        if not parts:
            raise UserInputError("Empty command")
        
        command = parts[0]
        
        # Handle different commands
        if command in ['help', 'h', '?']:
            self._show_help()
            raise UserInputError("Help displayed, please enter a command")
        
        elif command in ['quit', 'exit', 'q']:
            raise KeyboardInterrupt("User requested to quit")
        
        elif command in ['points', 'p']:
            self._show_points()
            raise UserInputError("Points displayed, please enter a command")
        
        elif command in ['status', 'info', 'i']:
            self._show_game_status(game_state)
            raise UserInputError("Game status displayed, please enter a command")
        
        elif command in ['end', 'pass', 'done']:
            return Action(ActionType.END_TURN, self.user_id)
        
        elif command in ['roll', 'dice', 'r']:
            return Action(ActionType.ROLL_DICE, self.user_id)
        
        elif command in ['settlement', 'settle', 's', 'set']:
            return self._parse_build_settlement(parts, game_state)
        
        elif command in ['city', 'c']:
            return self._parse_build_city(parts, game_state)
        
        elif command in ['road', 'rd']:
            return self._parse_build_road(parts, game_state)
        
        elif command in ['trade', 't']:
            return self._parse_trade(parts, game_state)
        
        elif command in ['buy', 'dev']:
            return Action(ActionType.BUY_DEV_CARD, self.user_id)
        
        elif command in ['use']:
            return self._parse_use_dev_card(parts, game_state)
        
        elif command in ['robber', 'rob']:
            return self._parse_robber_move(parts, game_state)
        
        elif command in ['drop', 'discard']:
            return self._parse_discard_cards(parts, game_state)
        
        elif command in ['steal']:
            return self._parse_steal(parts, game_state)
        
        elif command in ['yes', 'y', 'accept']:
            return Action(ActionType.TRADE_ACCEPT, self.user_id)
        
        elif command in ['no', 'n', 'reject', 'decline']:
            return Action(ActionType.TRADE_REJECT, self.user_id)
        
        else:
            raise UserInputError(f"Unknown command: {command}. Type 'help' for available commands.")
    
    def _parse_build_settlement(self, parts: List[str], game_state: GameState) -> Action:
        """Parse settlement building command."""
        # Support both old coordinate format and new point format
        if len(parts) < 2:
            raise UserInputError("Settlement command requires a point number or coordinates. Example: 'settlement 12' or 'settlement 0 5'")
        
        # Check if using new point format (1 number) or old coordinate format (2 numbers)
        if len(parts) == 2 or (len(parts) == 3 and parts[2].lower() in ['start', 'starting']):
            # New point format: settlement <point> [start]
            try:
                point = int(parts[1])
                is_starting = len(parts) > 2 and parts[2].lower() in ['start', 'starting']
                
                # Convert point to coordinates using BoardDefinition
                coords = board_definition.point_id_to_game_coords(point)
                if coords is None:
                    raise UserInputError(f"Invalid point number: {point}. Valid points: 1-{len(board_definition.get_all_point_ids())}")
                
                row, index = coords
                
            except ValueError:
                raise UserInputError("Point number must be a valid integer. Example: 'settlement 12'")
                
        else:
            # Old coordinate format: settlement <row> <index> [start]
            if len(parts) < 3:
                raise UserInputError("Old format settlement command requires row and index. Example: 'settlement 0 5'")
            
            try:
                row = int(parts[1])
                index = int(parts[2])
                is_starting = len(parts) > 3 and parts[3].lower() in ['start', 'starting']
                
            except ValueError:
                raise UserInputError("Row and index must be numbers. Example: 'settlement 0 5'")
        
        # Auto-detect if we're in setup phase to determine action type
        in_setup = hasattr(game_state, 'game_phase') and hasattr(game_state.game_phase, 'name') and \
                   'SETUP' in game_state.game_phase.name
        
        # Force starting settlement if in setup phase
        if in_setup:
            action_type = ActionType.PLACE_STARTING_SETTLEMENT
        else:
            action_type = ActionType.PLACE_STARTING_SETTLEMENT if is_starting else ActionType.BUILD_SETTLEMENT
        
        params = {
            'point_coords': [row, index],
            'is_starting': in_setup or is_starting
        }
        
        return Action(action_type, self.user_id, params)
    
    def _parse_build_city(self, parts: List[str], game_state: GameState) -> Action:
        """Parse city building command."""
        # Support both old coordinate format and new point format
        if len(parts) < 2:
            raise UserInputError("City command requires a point number or coordinates. Example: 'city 12' or 'city 0 5'")
        
        # Check if using new point format (1 number) or old coordinate format (2 numbers)
        if len(parts) == 2:
            # New point format: city <point>
            try:
                point = int(parts[1])
                
                # Convert point to coordinates
                coords = point_to_coords(point)
                if coords is None:
                    raise UserInputError(f"Invalid point number: {point}. Valid points: 1-{len(get_all_points())}")
                
                row, index = coords
                
            except ValueError:
                raise UserInputError("Point number must be a valid integer. Example: 'city 12'")
                
        else:
            # Old coordinate format: city <row> <index>
            if len(parts) < 3:
                raise UserInputError("Old format city command requires row and index. Example: 'city 0 5'")
            
            try:
                row = int(parts[1])
                index = int(parts[2])
                
            except ValueError:
                raise UserInputError("Row and index must be numbers. Example: 'city 0 5'")
        
        params = {'point_coords': [row, index]}
        return Action(ActionType.BUILD_CITY, self.user_id, params)
    
    def _parse_build_road(self, parts: List[str], game_state: GameState) -> Action:
        """Parse road building command."""
        # Support both old coordinate format and new point format
        if len(parts) < 3:
            raise UserInputError("Road command requires 2 points. Example: 'road 5 6' or 'road 0 5 0 6'")
        
        # Check if using new point format (2 numbers) or old coordinate format (4 numbers)
        if len(parts) == 3 or (len(parts) == 4 and parts[3].lower() in ['start', 'starting']):
            # New point format: road <point1> <point2> [start]
            try:
                point1 = int(parts[1])
                point2 = int(parts[2])
                is_starting = len(parts) > 3 and parts[3].lower() in ['start', 'starting']
                
                # Validate road placement using BoardDefinition
                if not board_definition.is_valid_road_placement(point1, point2):
                    raise UserInputError(f"Cannot build road between points {point1} and {point2} - they are not adjacent")
                
                # Convert points to coordinates using BoardDefinition
                start_coords = board_definition.point_id_to_game_coords(point1)
                end_coords = board_definition.point_id_to_game_coords(point2)
                
                if start_coords is None:
                    raise UserInputError(f"Invalid point number: {point1}. Valid points: 1-{len(board_definition.get_all_point_ids())}")
                if end_coords is None:
                    raise UserInputError(f"Invalid point number: {point2}. Valid points: 1-{len(board_definition.get_all_point_ids())}")
                
                start_row, start_index = start_coords
                end_row, end_index = end_coords
                
            except ValueError:
                raise UserInputError("Point numbers must be valid integers. Example: 'road 5 6'")
                
        else:
            # Old coordinate format: road <start_row> <start_index> <end_row> <end_index> [start]
            if len(parts) < 5:
                raise UserInputError("Old format road command requires start and end coordinates. Example: 'road 0 5 0 6'")
            
            try:
                start_row = int(parts[1])
                start_index = int(parts[2])
                end_row = int(parts[3])
                end_index = int(parts[4])
                is_starting = len(parts) > 5 and parts[5].lower() in ['start', 'starting']
                
            except ValueError:
                raise UserInputError("Coordinates must be numbers. Example: 'road 0 5 0 6'")
        
        # Auto-detect if we're in setup phase to determine action type
        in_setup = hasattr(game_state, 'game_phase') and hasattr(game_state.game_phase, 'name') and \
                   'SETUP' in game_state.game_phase.name
        
        # Force starting road if in setup phase
        if in_setup:
            action_type = ActionType.PLACE_STARTING_ROAD
        else:
            action_type = ActionType.PLACE_STARTING_ROAD if is_starting else ActionType.BUILD_ROAD
        
        params = {
            'start_coords': [start_row, start_index],
            'end_coords': [end_row, end_index],
            'is_starting': in_setup or is_starting
        }
        
        return Action(action_type, self.user_id, params)
    
    def _parse_trade(self, parts: List[str], game_state: GameState) -> Action:
        """Parse trading command."""
        if len(parts) < 2:
            raise UserInputError("Trade command needs more info. Examples: 'trade bank wood 4 wheat 1' or 'trade player 1 wood sheep'")
        
        if parts[1].lower() == 'bank':
            return self._parse_bank_trade(parts[2:])
        elif parts[1].lower() == 'player':
            return self._parse_player_trade(parts[2:], game_state)
        else:
            raise UserInputError("Trade must specify 'bank' or 'player'. Examples: 'trade bank wood 4 wheat 1' or 'trade player 1 wood sheep'")
    
    def _parse_bank_trade(self, parts: List[str]) -> Action:
        """Parse bank trading command."""
        if len(parts) < 4:
            raise UserInputError("Bank trade format: 'trade bank [give_resource] [give_amount] [get_resource] [get_amount]'")
        
        try:
            give_resource = self._parse_resource(parts[0])
            give_amount = int(parts[1])
            get_resource = self._parse_resource(parts[2])
            get_amount = int(parts[3])
            
            params = {
                'offer': {give_resource.name.lower(): give_amount},
                'request': {get_resource.name.lower(): get_amount}
            }
            
            return Action(ActionType.TRADE_BANK, self.user_id, params)
            
        except (ValueError, KeyError):
            raise UserInputError("Invalid trade format or resource names")
    
    def _parse_player_trade(self, parts: List[str], game_state: GameState = None) -> Action:
        """Parse player trading command."""
        if len(parts) < 3:
            raise UserInputError("Player trade format: 'trade player [player_id_or_name] [your_resource] [their_resource]'")
        
        try:
            # Try to parse as player ID first
            try:
                target_player = int(parts[0])
            except ValueError:
                # Not a number, try to find by name
                player_name = parts[0].lower()
                target_player = None
                
                if game_state and game_state.players_state:
                    for player in game_state.players_state:
                        if player.name.lower() == player_name:
                            target_player = player.player_id
                            break
                
                if target_player is None:
                    raise UserInputError(f"Player '{parts[0]}' not found. Use player name or ID (0-{len(game_state.players_state)-1 if game_state else 3})")
            
            give_resource = self._parse_resource(parts[1])
            get_resource = self._parse_resource(parts[2])
            
            params = {
                'target_player': target_player,
                'offer': {give_resource.name.lower(): 1},
                'request': {get_resource.name.lower(): 1}
            }
            
            return Action(ActionType.TRADE_PROPOSE, self.user_id, params)
            
        except (ValueError, KeyError):
            raise UserInputError("Invalid trade format or resource names")
    
    def _parse_use_dev_card(self, parts: List[str], game_state: GameState) -> Action:
        """Parse development card usage command."""
        if len(parts) < 2:
            raise UserInputError("Use command requires card type. Example: 'use knight' or 'use road'")
        
        card_name = parts[1].lower()
        params = {'card_type': card_name}
        
        # Add specific parameters based on card type
        if card_name == 'knight' and len(parts) >= 5:
            try:
                robber_row = int(parts[2])
                robber_index = int(parts[3])
                victim_player = int(parts[4]) if parts[4] != 'none' else None
                
                params.update({
                    'tile_coords': [robber_row, robber_index],
                    'victim': victim_player
                })
            except ValueError:
                raise UserInputError("Knight card format: 'use knight [robber_row] [robber_index] [victim_player_or_none]'")
        
        return Action(ActionType.USE_DEV_CARD, self.user_id, params)
    
    def _parse_robber_move(self, parts: List[str], game_state: GameState) -> Action:
        """Parse robber movement command.
        
        Format: 'robber [tile_id]' or 'robber [row] [index]'
        Examples: 'robber 5' or 'robber 2 1'
        The steal action is now separate via 'steal [player]' command.
        """
        if len(parts) < 2:
            raise UserInputError("Robber command format: 'robber [tile_id]' or 'robber [row] [index]'. Example: 'robber 5'")
        
        try:
            # Try single tile ID format first
            if len(parts) == 2:
                tile_id = int(parts[1])
                # Convert tile ID (1-19) to game coordinates using board_definition
                coords = board_definition.hex_id_to_game_coords(tile_id)
                if coords is None:
                    raise UserInputError(f"Invalid tile ID: {tile_id}. Must be between 1 and 19.")
                row, index = coords
            # Fall back to [row, index] format
            elif len(parts) == 3:
                row = int(parts[1])
                index = int(parts[2])
            else:
                raise UserInputError("Robber command format: 'robber [tile_id]' or 'robber [row] [index]'. Example: 'robber 5'")
            
            params = {
                'tile_coords': [row, index]
            }
            
            return Action(ActionType.ROBBER_MOVE, self.user_id, params)
            
        except ValueError:
            raise UserInputError("Robber coordinates must be numbers. Example: 'robber 5'")
    
    def _parse_steal(self, parts: List[str], game_state: GameState) -> Action:
        """Parse steal card command.
        
        Format: 'steal [player_id_or_name]' or 'steal none'
        """
        if len(parts) < 2:
            raise UserInputError("Steal command format: 'steal [player_id_or_name]' or 'steal none'")
        
        target = parts[1].lower()
        
        if target == 'none':
            # No one to steal from (all adjacent players have 0 cards)
            params = {'target_player': None}
        else:
            try:
                # Try to parse as player ID first
                target_player = int(target)
            except ValueError:
                # Try to find by name
                target_player = None
                if game_state and game_state.players_state:
                    for player in game_state.players_state:
                        if player.name.lower() == target:
                            target_player = player.player_id
                            break
                
                if target_player is None:
                    raise UserInputError(f"Player '{parts[1]}' not found.")
            
            params = {'target_player': target_player}
        
        return Action(ActionType.STEAL_CARD, self.user_id, params)
    
    def _parse_discard_cards(self, parts: List[str], game_state: GameState) -> Action:
        """Parse discard cards command.
        
        Format: 'drop [amount1] [resource1] [amount2] [resource2] ...'
        Example: 'drop 2 wood 1 brick' means discard 2 wood and 1 brick
        
        The game will validate that the total discarded equals the required amount
        and that the player has those cards.
        """
        if len(parts) < 3:
            raise UserInputError(
                "Discard command format: 'drop [amount] [resource] [amount] [resource] ...'\n"
                "Example: 'drop 2 wood 1 brick' to discard 2 wood and 1 brick"
            )
        
        # Parse pairs of (amount, resource)
        cards_to_discard = []
        i = 1
        
        while i < len(parts) - 1:
            try:
                amount = int(parts[i])
                resource_name = parts[i + 1].lower()
                
                # Parse the resource
                resource = self._parse_resource(resource_name)
                
                # Add the cards to discard list (one entry per card)
                for _ in range(amount):
                    cards_to_discard.append(resource.name)
                
                i += 2
            except ValueError:
                raise UserInputError(
                    f"Invalid format at '{parts[i]}'. Expected: [amount] [resource]\n"
                    "Example: 'drop 2 wood 1 brick'"
                )
        
        if not cards_to_discard:
            raise UserInputError("You must specify at least one card to discard.")
        
        params = {'cards': cards_to_discard}
        return Action(ActionType.DISCARD_CARDS, self.user_id, params)
    
    def _parse_resource(self, resource_name: str) -> ResCard:
        """Parse resource name to ResCard enum."""
        resource_mapping = {
            'wood': ResCard.Wood,
            'lumber': ResCard.Wood,
            'brick': ResCard.Brick,
            'sheep': ResCard.Sheep,
            'wool': ResCard.Sheep,
            'wheat': ResCard.Wheat,
            'grain': ResCard.Wheat,
            'ore': ResCard.Ore,
            'stone': ResCard.Ore
        }
        
        resource_name = resource_name.lower()
        if resource_name not in resource_mapping:
            raise UserInputError(f"Unknown resource: {resource_name}. Valid resources: {list(resource_mapping.keys())}")
        
        return resource_mapping[resource_name]
    
    def _show_points(self) -> None:
        """Display all available points on the board."""
        print("\n" + "="*60)
        print("BOARD POINTS MAP")
        print("="*60)
        
        # Get all points using BoardDefinition
        all_points_list = board_definition.get_all_point_ids()
        
        # Group points by row for cleaner display
        points_by_row = {}
        for point_id in all_points_list:
            coords = board_definition.point_id_to_game_coords(point_id)
            if coords:
                row, index = coords
                if row not in points_by_row:
                    points_by_row[row] = []
                points_by_row[row].append((point_id, index))
        
        # Display by row
        for row in sorted(points_by_row.keys()):
            points_in_row = sorted(points_by_row[row], key=lambda x: x[1])
            point_list = [f"{pid}({idx})" for pid, idx in points_in_row]
            print(f"Row {row}: {', '.join(point_list)}")
        
        print()
        print("Format: Point_ID(Index)")
        print("Usage: 'settlement 12' builds at point 12")
        print("       'road 5 6' builds road between points 5 and 6")
        print("="*60)

    def _show_help(self) -> None:
        """Display help information to the user."""
        print("\n" + "="*60)
        print("🎮 PYCATAN COMMANDS HELP")
        print("="*60)
        print("🏗️  BUILDING (Points 1-54):")
        print("  s <point>           - Build settlement (short: s, settle, settlement)")
        print("  road <p1> <p2>      - Build road between points (short: rd)")
        print("  city <point>        - Upgrade settlement to city (short: c)")
        print()
        print("💰 TRADING:")
        print("  trade bank <give> <amount> <get> <amount>")
        print("  trade player <id_or_name> <give> <get>    (short: t)")
        print("  Examples: 'trade bank wood 4 sheep 1' or 't player v wood sheep'")
        print()
        print("🃏 DEVELOPMENT CARDS:")
        print("  buy                 - Buy development card (short: dev)")
        print("  use <card_type>     - Use development card")
        print()
        print("🎲 TURN ACTIONS:")
        print("  roll               - Roll dice (short: r, dice)")
        print("  end                - End turn (short: pass, done)")
        print()
        print("🎯 ROBBER:")
        print("  robber <tile_num>  - Move robber to tile (short: rob)")
        print("  steal <player>     - Steal card from player (after moving robber)")
        print("  Examples: 'robber 5' then 'steal alice' or 'steal 2'")
        print()
        print("⚠️  DISCARD (when 7 is rolled):")
        print("  drop <amount> <resource> ... - Discard cards")
        print("  Example: 'drop 2 wood 1 brick' discards 2 wood and 1 brick")
        print()
        print("ℹ️  INFO:")
        print("  help               - Show this help (short: h, ?)")
        print("  status             - Show all players' status (short: info, i)")
        print("  points             - Show all valid points (short: p)")
        print()
        print("📦 RESOURCES: wood, brick, sheep, wheat, ore")
        print("🎯 POINTS: Use numbers 1-54. Example: 's 12' builds settlement at point 12")
        print("🔗 ROADS: Example: 'road 5 6' builds road between points 5 and 6")
        print("="*60)
    
    def notify_action(self, action: Action, success: bool, message: str = "") -> None:
        """Notify the user about an action result."""
        # Don't print here - the console visualization already displays this
        # This method is kept for compatibility but doesn't produce output
        pass
    
    def notify_game_event(self, event_type: str, message: str, 
                         affected_players: Optional[List[int]] = None) -> None:
        """Notify the user about general game events."""
        # Only notify for specific important events - avoid clutter
        skip_events = [
            'turn_change',  # Already handled by display_turn_start
            'action_performed',  # Already handled by notify_action + visualization
            'phase_change'  # Important, show this
        ]
        
        # Skip most events to avoid clutter
        if event_type not in ['phase_change']:
            return
        
        # For phase changes, show them clearly
        if event_type == 'phase_change':
            print(f"\n    ✨ {message}\n")