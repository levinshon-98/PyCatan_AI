"""
Human User Implementation for PyCatan Game Management

This module implements HumanUser, which provides a command-line interface
for human players to interact with the game.
"""

from typing import List, Optional, Dict, Tuple
from .user import User, UserInputError
from pycatan.management.actions import Action, ActionType, GameState
from pycatan.core.card import ResCard, DevCard
from pycatan.config.board_definition import board_definition


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
                
                # Convert point to coordinates using BoardDefinition
                coords = board_definition.point_id_to_game_coords(point)
                if coords is None:
                    raise UserInputError(f"Invalid point number: {point}. Valid points: 1-{len(board_definition.get_all_point_ids())}")
                
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
        """
        Parse player trading command.
        
        Supports flexible trading formats:
        - Simple 1:1: 'trade player 1 wood sheep'
        - With amounts: 'trade player 1 wood 2 sheep 1'
        - Multiple resources: 'trade player 1 wood 2 brick 1 for wheat 2 ore 1'
        - Gifts: 'trade player 1 nothing wheat 1' or 'trade player 1 wood 2 nothing'
        """
        if len(parts) < 2:
            raise UserInputError("Player trade format: 'trade player [player_id_or_name] [give_resources] [for/get] [receive_resources]'\n"
                               "Examples:\n"
                               "  - trade player 1 wood sheep (1:1 simple)\n"
                               "  - trade player 1 wood 2 sheep 1 (with amounts)\n"
                               "  - trade player 1 wood 2 brick 1 for wheat 2 (separator word)\n"
                               "  - trade player 1 nothing wheat 1 (gift from them)")
        
        try:
            # Parse target player
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
            
            # Find separator word (for/get/want) or split at middle
            separator_words = ['for', 'get', 'want', 'receive']
            separator_index = None
            
            for i, part in enumerate(parts[1:], start=1):
                if part.lower() in separator_words:
                    separator_index = i
                    break
            
            # Parse offer and request based on separator
            if separator_index:
                # Has separator word
                offer_parts = parts[1:separator_index]
                request_parts = parts[separator_index + 1:]
            else:
                # No separator - try to detect format
                # Check if it's old simple format (2 resources) or new format with amounts
                remaining = parts[1:]
                
                # Try to parse as pairs: [resource amount resource amount...]
                offer, request = self._split_trade_resources(remaining)
                offer_parts = offer
                request_parts = request
            
            # Parse offer and request
            offer_dict = self._parse_resource_list(offer_parts if separator_index else offer_parts)
            request_dict = self._parse_resource_list(request_parts if separator_index else request_parts)
            
            params = {
                'target_player': target_player,
                'offer': offer_dict,
                'request': request_dict
            }
            
            return Action(ActionType.TRADE_PROPOSE, self.user_id, params)
            
        except (ValueError, KeyError) as e:
            raise UserInputError(f"Invalid trade format: {e}")
    
    def _split_trade_resources(self, parts: List[str]) -> tuple:
        """
        Split trade resources into offer and request when no separator word is present.
        Handles both simple format (wood sheep) and amount format (wood 2 sheep 1).
        
        Strategy: Parse from left, consuming resource-amount pairs.
        When we've consumed about half the tokens, split there.
        """
        if len(parts) == 2:
            # Simple 1:1 format: [resource1] [resource2]
            return [parts[0]], [parts[1]]
        
        # Parse tokens and identify resource groups
        # A group is: resource_name [optional_number]
        groups = []
        i = 0
        while i < len(parts):
            token = parts[i]
            
            # Skip standalone numbers (shouldn't happen but safeguard)
            if token.isdigit():
                i += 1
                continue
            
            # Check if this is 'nothing' keyword
            if token.lower() == 'nothing':
                groups.append([token])
                i += 1
                continue
            
            # Check if next token is a number
            if i + 1 < len(parts) and parts[i + 1].isdigit():
                # Resource with amount: [resource, amount]
                groups.append([token, parts[i + 1]])
                i += 2
            else:
                # Resource without amount: [resource]
                groups.append([token])
                i += 1
        
        # Split groups roughly in half
        mid = len(groups) // 2
        
        # Flatten groups back to parts
        offer_parts = []
        for group in groups[:mid]:
            offer_parts.extend(group)
        
        request_parts = []
        for group in groups[mid:]:
            request_parts.extend(group)
        
        return offer_parts, request_parts
    
    def _parse_resource_list(self, parts: List[str]) -> dict:
        """
        Parse a list of resources with optional amounts.
        Examples:
        - ['wood', 'brick'] -> {'wood': 1, 'brick': 1}
        - ['wood', '2', 'brick', '1'] -> {'wood': 2, 'brick': 1}
        - ['nothing'] -> {}
        - [] -> {}
        """
        if not parts or (len(parts) == 1 and parts[0].lower() == 'nothing'):
            return {}
        
        result = {}
        i = 0
        
        while i < len(parts):
            # Skip if this is a number (should have been consumed as amount)
            if parts[i].isdigit():
                i += 1
                continue
            
            resource_name = parts[i]
            
            # Check for 'nothing' keyword
            if resource_name.lower() == 'nothing':
                i += 1
                continue
            
            # Check if next part is a number (amount)
            amount = 1
            if i + 1 < len(parts) and parts[i + 1].isdigit():
                amount = int(parts[i + 1])
                i += 2
            else:
                i += 1
            
            # Parse the resource
            try:
                resource = self._parse_resource(resource_name)
                resource_key = resource.name.lower()
                
                # Add to result (accumulate if resource appears multiple times)
                if resource_key in result:
                    result[resource_key] += amount
                else:
                    result[resource_key] = amount
            except UserInputError:
                # If we can't parse it as a resource, skip it
                # This handles edge cases
                continue
        
        return result
    
    def _parse_use_dev_card(self, parts: List[str], game_state: GameState) -> Action:
        """Parse development card usage command."""
        if len(parts) < 2:
            raise UserInputError("Use command requires card type. Example: 'use knight' or 'use road'")
        
        card_name = parts[1].lower()
        
        # Map user-friendly names to DevCard enum values
        card_type_map = {
            'knight': 'Knight',
            'road': 'Road',
            'roadbuilding': 'Road',
            'monopoly': 'Monopoly',
            'yearofplenty': 'YearOfPlenty',
            'plenty': 'YearOfPlenty',
            'year': 'YearOfPlenty'
        }
        
        if card_name not in card_type_map:
            raise UserInputError(f"Unknown card type '{card_name}'. Valid: knight, road, monopoly, yearofplenty")
        
        dev_card_type = card_type_map[card_name]
        params = {'card_type': dev_card_type}
        
        # Handle Monopoly card - needs resource type
        if dev_card_type == 'Monopoly':
            # Format: use monopoly wood
            # parts = ['use', 'monopoly', 'wood']
            if len(parts) < 3:
                raise UserInputError(
                    "Monopoly card needs a resource type.\n"
                    "    Format: use monopoly [resource]\n"
                    "    Example: use monopoly wood\n"
                    "    Valid resources: wood, brick, sheep, wheat, ore"
                )
            
            resource_name = parts[2].lower()
            resource_map = {
                'wood': 'Wood',
                'brick': 'Brick',
                'sheep': 'Sheep',
                'wheat': 'Wheat',
                'ore': 'Ore'
            }
            
            if resource_name not in resource_map:
                raise UserInputError(
                    f"Invalid resource '{resource_name}'.\n"
                    "    Valid resources: wood, brick, sheep, wheat, ore"
                )
            
            params['resource_type'] = resource_map[resource_name]
        
        # Handle Road Building card - needs 2 roads in same command
        elif dev_card_type == 'Road':
            # Format: use road rd 10 11 rd 12 13
            # parts = ['use', 'road', 'rd', '10', '11', 'rd', '12', '13']
            if len(parts) < 8 or parts[2] != 'rd' or parts[5] != 'rd':
                raise UserInputError(
                    "Road Building card needs 2 roads in one command.\n"
                    "    Format: use road rd [point1] [point2] rd [point3] [point4]\n"
                    "    Example: use road rd 10 11 rd 12 13"
                )
            
            try:
                # Parse first road
                road1_point1 = int(parts[3])
                road1_point2 = int(parts[4])
                
                # Parse second road
                road2_point1 = int(parts[6])
                road2_point2 = int(parts[7])
                
                # Validate road placements
                if not board_definition.is_valid_road_placement(road1_point1, road1_point2):
                    raise UserInputError(f"Invalid first road: points {road1_point1} and {road1_point2} are not adjacent")
                
                if not board_definition.is_valid_road_placement(road2_point1, road2_point2):
                    raise UserInputError(f"Invalid second road: points {road2_point1} and {road2_point2} are not adjacent")
                
                # Convert to game coordinates
                road1_start = board_definition.point_id_to_game_coords(road1_point1)
                road1_end = board_definition.point_id_to_game_coords(road1_point2)
                road2_start = board_definition.point_id_to_game_coords(road2_point1)
                road2_end = board_definition.point_id_to_game_coords(road2_point2)
                
                if None in [road1_start, road1_end, road2_start, road2_end]:
                    raise UserInputError("Invalid point numbers. Check your road coordinates.")
                
                # Store coordinates - GameManager will convert to point objects
                params['road_one_coords'] = {
                    'start': road1_start,
                    'end': road1_end
                }
                params['road_two_coords'] = {
                    'start': road2_start,
                    'end': road2_end
                }
                
            except (ValueError, IndexError):
                raise UserInputError("Invalid road format. Point numbers must be integers.")
        
        # Handle Knight card - needs tile location and optional victim
        elif dev_card_type == 'Knight':
            # Format: use knight tile [tile_id] [steal [player_name]]
            # parts = ['use', 'knight', 'tile', '5', 'steal', 'Alice']
            if len(parts) < 4 or parts[2] != 'tile':
                raise UserInputError(
                    "Knight card needs tile location.\n"
                    "    Format: use knight tile [tile_id] [steal [player_name]]\n"
                    "    Example: use knight tile 5\n"
                    "    Example: use knight tile 5 steal Bob"
                )
            
            try:
                # Parse tile ID
                tile_id = int(parts[3])
                
                # Convert tile ID to game coordinates using board_definition
                tile_coords = board_definition.hex_id_to_game_coords(tile_id)
                if tile_coords is None:
                    max_tile = len(board_definition.get_all_tile_ids())
                    raise UserInputError(f"Invalid tile ID: {tile_id}. Valid tiles: 1-{max_tile}")
                
                params['tile_coords'] = tile_coords
                
                # Parse optional victim
                victim_name = None
                if len(parts) >= 6 and parts[4] == 'steal':
                    victim_name = parts[5]
                    
                    # Find player ID by name
                    victim_id = None
                    for pid, player_state in enumerate(game_state.players_state):
                        # PlayerState has a 'name' attribute
                        user_name = player_state.name if hasattr(player_state, 'name') else 'UNKNOWN'
                        if user_name.lower() == victim_name.lower():
                            victim_id = pid
                            break
                    
                    if victim_id is None:
                        raise UserInputError(f"Player '{victim_name}' not found")
                    
                    # Don't allow stealing from yourself
                    if victim_id == self.user_id:
                        raise UserInputError("You cannot steal from yourself!")
                    
                    params['victim_id'] = victim_id
                else:
                    params['victim_id'] = None
                
            except ValueError:
                raise UserInputError("Tile ID must be a number. Example: 'use knight tile 5'")
        
        # Each card type needs specific additional input
        # For now, we'll create the action with just the card type
        # The GameManager will request additional input as needed
        
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
        print("      Example: 'trade bank wood 4 sheep 1'")
        print()
        print("  trade player <id_or_name> <resources_offer> [for] <resources_want>")
        print("      Simple 1:1:     't player 1 wood sheep'")
        print("      With amounts:   't player bob wood 2 sheep 1'")
        print("      Multiple:       't player 1 wood 2 brick 1 for wheat 2 ore 1'")
        print("      Gifts:          't player 2 nothing wheat 1' (receive gift)")
        print("      Gifts:          't player 2 wood 3 nothing' (give gift)")
        print("      💡 Use 'for' or 'get' to separate offer from request")
        print()
        print("🃏 DEVELOPMENT CARDS:")
        print("  buy / dev           - Buy dev card (cost: 1 Ore + 1 Sheep + 1 Wheat)")
        print("  use <card_type>     - Use development card")
        print()
        print("  📋 Card Types & Effects:")
        print("     knight         - Move robber + steal card (gives +1 knight count)")
        print("                      Format: use knight tile [tile_id] [steal [player_name]]")
        print("                      Example: use knight tile 5 steal Bob")
        print("     road           - Build 2 free roads instantly")
        print("                      Format: use road rd [p1] [p2] rd [p3] [p4]")
        print("                      Example: use road rd 10 11 rd 12 13")
        print("     monopoly       - Take ALL cards of one resource from all players")
        print("                      Format: use monopoly [resource]")
        print("                      Example: use monopoly wood")
        print("                      Valid: wood, brick, sheep, wheat, ore")
        print("     yearofplenty   - Take any 2 resource cards from bank")
        print("     victorypoint   - +1 VP (auto-counted, don't use manually)")
        print()
        print("  💡 Tips:")
        print("     • 3+ knights = Largest Army (2 VP)")
        print("     • Knight steals from random adjacent player if you don't specify")
        print("     • Example: 'use knight tile 5' (auto-steal) or 'use knight tile 5 steal Bob'")
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
        # Display success/error messages to the user in their input console
        if message:
            if success:
                print(f"    ✓ {message}")
            else:
                print(f"    ✗ {message}")
    
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