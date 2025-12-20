"""
GameManager - Central coordinator for PyCatan game flow

This module contains the GameManager class that orchestrates the entire
game flow, manages turns, coordinates between users and the game state.
"""

from typing import List, Optional, Dict, Any
import uuid
import random
from datetime import datetime

from pycatan.actions import Action, ActionResult, GameState, GamePhase, TurnPhase, ActionType
from pycatan.user import User, UserList, validate_user_list, UserInputError
from pycatan.game import Game
from pycatan.statuses import Statuses
from pycatan.card import DevCard
from pycatan.log_events import EventType, create_log_entry


class GameManager:
    """
    Central coordinator for a Catan game session.
    
    The GameManager orchestrates the entire game flow:
    - Manages turn order and game phases
    - Coordinates between Users and the Game logic
    - Maintains the current game state
    - Handles user input and action execution
    - Manages game-wide events and notifications
    """
    
    def __init__(self, users: UserList, game_config: Optional[Dict[str, Any]] = None, random_seed: Optional[int] = None):
        """
        Initialize a new GameManager.
        
        Args:
            users: List of User objects for this game
            game_config: Optional configuration for the game (board layout, rules, etc.)
            random_seed: Optional seed for random number generator (for reproducible games)
            
        Raises:
            ValueError: If users list is invalid
        """
        # Validate users
        validate_user_list(users)
        
        # Set random seed if provided (for reproducible games)
        if random_seed is not None:
            random.seed(random_seed)
        
        # Store game metadata
        self.game_id = str(uuid.uuid4())
        self.created_at = datetime.now()
        self.users = users
        self.num_players = len(users)
        
        # Initialize game configuration
        self.config = game_config or {}
        
        # Visualization manager (can be set later)
        self.visualization_manager = None
        
        # Create the underlying game instance
        self.game = Game(num_of_players=self.num_players)
        
        # Initialize game state
        self._current_game_state = GameState(
            game_id=self.game_id,
            turn_number=0,
            current_player=0,
            game_phase=GamePhase.SETUP_FIRST_ROUND,
            turn_phase=TurnPhase.ROLL_DICE
        )
        
        # Game flow control
        self._is_running = False
        self._is_paused = False
        
        # Action history and pending operations
        self._action_history: List[Action] = []
        self._pending_actions: List[Action] = []
        
        # Error tracking per player to prevent infinite loops
        self._player_error_count = [0] * self.num_players
        
        # Setup phase progress tracking
        self._setup_turn_progress = {'settlement': False, 'road': False}
        
    @property
    def is_running(self) -> bool:
        """Whether the game is currently running."""
        return self._is_running
    
    @property
    def is_paused(self) -> bool:
        """Whether the game is currently paused."""
        return self._is_paused
    
    @property
    def current_player_id(self) -> int:
        """ID of the current player."""
        return self._current_game_state.current_player
    
    @property
    def current_user(self) -> User:
        """The User object for the current player."""
        return self.users[self.current_player_id]
    
    def get_full_state(self) -> GameState:
        """
        Get the complete current state of the game.
        
        This method extracts state from the Game object and combines it
        with GameManager state like current player and turn information.
        
        Returns:
            GameState: Complete current game state
        """
        # Get the base state from the Game object
        game_state = self.game.get_full_state()
        
        # Update player names with user names
        for i, user in enumerate(self.users):
            if i < len(game_state.players_state):
                game_state.players_state[i].name = getattr(user, 'name', f'Player {i + 1}')
        
        # Update with GameManager-specific information
        game_state.game_id = self.game_id
        game_state.turn_number = self._current_game_state.turn_number
        game_state.current_player = self._current_game_state.current_player
        game_state.game_phase = self._current_game_state.game_phase
        game_state.turn_phase = self._current_game_state.turn_phase
        
        return game_state
    
    def get_available_actions(self) -> List[str]:
        """
        Get a list of available action types for the current game state.
        
        Returns:
            List[str]: List of allowed ActionType names
        """
        actions = []
        phase = self._current_game_state.game_phase
        turn_phase = self._current_game_state.turn_phase
        
        if phase in [GamePhase.SETUP_FIRST_ROUND, GamePhase.SETUP_SECOND_ROUND]:
            # In setup phase: settlement first, then road
            if not self._setup_turn_progress['settlement']:
                # Can only place settlement when none placed yet
                actions.append(ActionType.PLACE_STARTING_SETTLEMENT.name)
            elif not self._setup_turn_progress['road']:
                # Can only place road after settlement is placed
                actions.append(ActionType.PLACE_STARTING_ROAD.name)
            else:
                # Both built, turn should auto-end but allow manual end
                actions.append(ActionType.END_TURN.name)
            
        elif phase == GamePhase.NORMAL_PLAY:
            # Check special robber-related phases first
            if turn_phase == TurnPhase.DISCARD_PHASE:
                # Only discard action allowed
                actions.append(ActionType.DISCARD_CARDS.name)
            elif turn_phase == TurnPhase.ROBBER_MOVE:
                # Only robber move allowed
                actions.append(ActionType.ROBBER_MOVE.name)
            elif turn_phase == TurnPhase.ROBBER_STEAL:
                # Only steal action allowed
                actions.append(ActionType.STEAL_CARD.name)
            elif not self._current_game_state.dice_rolled:
                # Normal pre-roll phase
                actions.extend([
                    ActionType.ROLL_DICE.name,
                    ActionType.USE_DEV_CARD.name
                ])
            else:
                # Normal post-roll phase - player actions
                actions.extend([
                    ActionType.BUILD_SETTLEMENT.name,
                    ActionType.BUILD_CITY.name,
                    ActionType.BUILD_ROAD.name,
                    ActionType.TRADE_PROPOSE.name,
                    ActionType.TRADE_BANK.name,
                    ActionType.BUY_DEV_CARD.name,
                    ActionType.USE_DEV_CARD.name,
                    ActionType.END_TURN.name
                ])
                
        return actions

    def execute_action(self, action: Action) -> ActionResult:
        """
        Execute an action in the game.
        
        This is the main entry point for all game actions.
        Validates the action and delegates to the appropriate handler.
        
        Args:
            action: The action to execute
            
        Returns:
            ActionResult: Result of the action execution
        """
        # Basic validation
        if not self._is_running:
            return ActionResult.failure_result(
                "Game is not running",
                "GAME_NOT_RUNNING"
            )
        
        if action.player_id != self.current_player_id:
            return ActionResult.failure_result(
                f"Not player {action.player_id}'s turn",
                "NOT_YOUR_TURN"
            )
        
        # Log the action attempt
        self._action_history.append(action)
        
        try:
            # Route to appropriate handler based on action type
            if action.action_type == ActionType.END_TURN:
                return self._handle_end_turn(action)
            elif action.action_type in [ActionType.BUILD_SETTLEMENT, ActionType.BUILD_CITY, ActionType.BUILD_ROAD,
                                      ActionType.PLACE_STARTING_SETTLEMENT, ActionType.PLACE_STARTING_ROAD]:
                return self._handle_building_action(action)
            elif action.action_type == ActionType.ROLL_DICE:
                return self._handle_roll_dice(action)
            elif action.action_type in [ActionType.TRADE_PROPOSE, ActionType.TRADE_ACCEPT, ActionType.TRADE_REJECT]:
                return self._handle_trade_action(action)
            elif action.action_type == ActionType.TRADE_BANK:
                return self._execute_trade_bank(action)
            elif action.action_type == ActionType.BUY_DEV_CARD:
                return self._execute_buy_dev_card(action)
            elif action.action_type == ActionType.USE_DEV_CARD:
                return self._execute_use_dev_card(action)
            elif action.action_type == ActionType.DISCARD_CARDS:
                return self._handle_discard_cards(action)
            elif action.action_type == ActionType.ROBBER_MOVE:
                return self._handle_robber_move(action)
            elif action.action_type == ActionType.STEAL_CARD:
                return self._handle_steal_card(action)
            else:
                # For now, return "not implemented" for other actions
                return ActionResult.failure_result(
                    f"Action {action.action_type} not yet implemented",
                    "NOT_IMPLEMENTED"
                )
                
        except Exception as e:
            return ActionResult.failure_result(
                f"Error executing action: {str(e)}",
                "EXECUTION_ERROR"
            )
    
    def _handle_end_turn(self, action: Action) -> ActionResult:
        """Handle end turn action."""
        # In the new architecture, this method just validates and returns success.
        # The actual turn advancement happens in _advance_to_next_player()
        # which is called by the game loop when this action returns success.
        
        return ActionResult.success_result(
            self.get_full_state(),
            affected_players=[action.player_id]
        )
    
    def _handle_building_action(self, action: Action) -> ActionResult:
        """Handle building actions (settlements, cities, roads)."""
        try:
            if action.action_type in [ActionType.BUILD_SETTLEMENT, ActionType.PLACE_STARTING_SETTLEMENT]:
                return self._execute_build_settlement(action)
            elif action.action_type == ActionType.BUILD_CITY:
                return self._execute_build_city(action)
            elif action.action_type in [ActionType.BUILD_ROAD, ActionType.PLACE_STARTING_ROAD]:
                return self._execute_build_road(action)
            else:
                return ActionResult.failure_result(
                    f"Unknown building action: {action.action_type}",
                    "UNKNOWN_ACTION"
                )
        except Exception as e:
            return ActionResult.failure_result(
                f"Error executing building action: {str(e)}",
                "BUILDING_ERROR"
            )

    def _distribute_setup_resources(self, player_id: int, point: Any) -> None:
        """Distribute initial resources based on the second settlement."""
        from pycatan.board import Board
        
        resources_given = []
        
        # Iterate over tiles adjacent to the point
        # Point object has 'tiles' attribute which is a list of Tile objects
        if hasattr(point, 'tiles'):
            for tile in point.tiles:
                # Get resource type from tile type
                card_type = Board.get_card_from_tile(tile.type)
                
                # If it's a valid resource (not None/Desert)
                if card_type:
                    # Add card to player
                    self.game.players[player_id].add_cards([card_type])
                    resources_given.append(card_type.name)
        
        if resources_given:
            # Create a dummy action for notification purposes
            # We use PLACE_STARTING_SETTLEMENT but need to provide dummy point_coords
            # to satisfy validation, even though they aren't used for the notification
            dummy_action = Action(
                ActionType.PLACE_STARTING_SETTLEMENT, 
                player_id,
                {'point_coords': [0, 0]}  # Dummy coordinates
            )
            
            self._notify_user(
                player_id, 
                dummy_action, 
                True, 
                f"Received starting resources: {', '.join(resources_given)}"
            )
            
            # Notify visualization about starting resources
            if self.visualization_manager:
                player_name = self.users[player_id].name if hasattr(self.users[player_id], 'name') else f"Player {player_id + 1}"
                # Create distribution dict format
                distribution = {player_name: resources_given}
                self.visualization_manager.display_resource_distribution(distribution)

    def _execute_build_settlement(self, action: Action) -> ActionResult:
        """Execute settlement building action."""
        # Extract coordinates from action parameters
        if 'point_coords' not in action.parameters:
            return ActionResult.failure_result(
                "Settlement action missing point_coords parameter",
                "MISSING_COORDS"
            )
        
        coords = action.parameters['point_coords']
        
        # Determine if this is a starting settlement based on game phase
        # The GameManager is the authority on rules, so we check the phase here
        in_setup_phase = self._current_game_state.game_phase in [GamePhase.SETUP_FIRST_ROUND, GamePhase.SETUP_SECOND_ROUND]
        
        # If in setup phase, force is_starting to True (free building)
        # Otherwise respect the action parameter (defaulting to False)
        if in_setup_phase:
            is_starting = True
        else:
            is_starting = action.parameters.get('is_starting', False)
        
        # Get the point object from board
        try:
            point = self.game.board.points[coords[0]][coords[1]]
        except (IndexError, TypeError):
            return ActionResult.failure_result(
                f"Invalid coordinates: {coords}",
                "INVALID_COORDS"
            )
        
        # Call the actual Game method
        status = self.game.add_settlement(action.player_id, point, is_starting)
        
        # Update setup progress if successful and in setup phase
        if status == Statuses.ALL_GOOD and in_setup_phase:
            self._setup_turn_progress['settlement'] = True
            
            # Only distribute resources in the second round of setup
            if self._current_game_state.game_phase == GamePhase.SETUP_SECOND_ROUND:
                self._distribute_setup_resources(action.player_id, point)
        
        # Convert Status to ActionResult
        return self._convert_status_to_result(status, self.get_full_state(), [action.player_id])

    def _execute_build_city(self, action: Action) -> ActionResult:
        """Execute city building action."""
        # Extract coordinates from action parameters  
        if 'point_coords' not in action.parameters:
            return ActionResult.failure_result(
                "City action missing point_coords parameter", 
                "MISSING_COORDS"
            )
        
        coords = action.parameters['point_coords']
        
        # Get the point object from board and convert coords to point ID
        try:
            point = self.game.board.points[coords[0]][coords[1]]
            # Try to get the point ID for better user messages
            from pycatan.board_definition import board_definition
            point_id = board_definition.game_coords_to_point_id(coords[0], coords[1])
            location_str = f"point {point_id}" if point_id else f"coordinates {coords}"
        except (IndexError, TypeError):
            return ActionResult.failure_result(
                f"Invalid coordinates: {coords}",
                "INVALID_COORDS"
            )
        
        # Upgrade the settlement to a city
        status = self.game.add_city(point, action.player_id)
        
        # Convert status to ActionResult
        if status == Statuses.ALL_GOOD:
            player = self.game.players[action.player_id]
            return ActionResult.success_result(
                f"City built at {location_str}! Victory Points: {player.get_VP()}",
                "CITY_BUILT"
            )
        elif status == Statuses.ERR_NOT_EXIST:
            return ActionResult.failure_result(
                f"No settlement found at {location_str} to upgrade",
                "NO_SETTLEMENT"
            )
        elif status == Statuses.ERR_BAD_OWNER:
            return ActionResult.failure_result(
                f"You don't own the settlement at {location_str}",
                "NOT_YOUR_SETTLEMENT"
            )
        elif status == Statuses.ERR_UPGRADE_CITY:
            return ActionResult.failure_result(
                f"Already a city at {location_str}",
                "ALREADY_CITY"
            )
        elif status == Statuses.ERR_CARDS:
            return ActionResult.failure_result(
                "Not enough resources. Need: 3 Ore, 2 Wheat",
                "NOT_ENOUGH_RESOURCES"
            )
        else:
            return ActionResult.failure_result(
                f"Failed to build city: {status.name}",
                status.name
            )

    def _execute_build_road(self, action: Action) -> ActionResult:
        """Execute road building action."""
        # Extract coordinates from action parameters
        if 'start_coords' not in action.parameters or 'end_coords' not in action.parameters:
            return ActionResult.failure_result(
                "Road action missing start_coords or end_coords parameters",
                "MISSING_COORDS"
            )
        
        start_coords = action.parameters['start_coords']
        end_coords = action.parameters['end_coords']
        
        # Determine if this is a starting road based on game phase
        # The GameManager is the authority on rules, so we check the phase here
        in_setup_phase = self._current_game_state.game_phase in [GamePhase.SETUP_FIRST_ROUND, GamePhase.SETUP_SECOND_ROUND]
        
        # If in setup phase, force is_starting to True (free building)
        # Otherwise respect the action parameter (defaulting to False)
        if in_setup_phase:
            is_starting = True
        else:
            is_starting = action.parameters.get('is_starting', False)
        
        # Get point objects from board
        try:
            start_point = self.game.board.points[start_coords[0]][start_coords[1]]
            end_point = self.game.board.points[end_coords[0]][end_coords[1]]
        except (IndexError, TypeError):
            return ActionResult.failure_result(
                f"Invalid coordinates: start={start_coords}, end={end_coords}",
                "INVALID_COORDS"
            )
        
        # Call the actual Game method
        status = self.game.add_road(action.player_id, start_point, end_point, is_starting)
        
        # Update setup progress if successful and in setup phase
        if status == Statuses.ALL_GOOD and in_setup_phase:
            self._setup_turn_progress['road'] = True
        
        # Convert Status to ActionResult
        return self._convert_status_to_result(status, self.get_full_state(), [action.player_id])

    def _convert_status_to_result(self, status, game_state, affected_players):
        """Convert Game.Statuses to ActionResult."""
        from pycatan.statuses import Statuses
        
        if status == Statuses.ALL_GOOD:
            return ActionResult.success_result(game_state, affected_players)
        elif status == Statuses.ERR_CARDS:
            return ActionResult.failure_result("Not enough cards", "INSUFFICIENT_RESOURCES")
        elif status == Statuses.ERR_BLOCKED:
            return ActionResult.failure_result("Location is blocked", "LOCATION_BLOCKED")
        elif status == Statuses.ERR_INPUT:
            return ActionResult.failure_result("Invalid input", "INVALID_INPUT")
        elif status == Statuses.ERR_NOT_CON:
            return ActionResult.failure_result("Road points are not connected", "NOT_CONNECTED")
        elif status == Statuses.ERR_ISOLATED:
            return ActionResult.failure_result("Not connected to existing buildings", "ISOLATED")
        else:
            return ActionResult.failure_result(f"Unknown status: {status}", "UNKNOWN_ERROR")
    
    def _handle_trade_action(self, action: Action) -> ActionResult:
        """Handle trade-related actions."""
        if action.action_type == ActionType.TRADE_PROPOSE:
            return self._execute_trade_propose(action)
        elif action.action_type == ActionType.TRADE_BANK:
            return self._execute_trade_bank(action)
        else:
            # TRADE_ACCEPT and TRADE_REJECT should not be called directly
            # They are handled internally by _execute_trade_propose
            return ActionResult.failure_result(
                f"Trade action {action.action_type} cannot be called directly",
                "INVALID_ACTION"
            )
    
    def _execute_trade_propose(self, action: Action) -> ActionResult:
        """
        Execute a trade proposal between players.
        
        This function:
        1. Validates that both players have the required cards
        2. Requests input from the target player (accept/reject)
        3. Executes the trade if accepted
        """
        try:
            proposer_id = action.player_id
            target_id = action.parameters['target_player']
            offer = action.parameters['offer']  # {resource: amount}
            request = action.parameters['request']  # {resource: amount}
            
            # Get player names for messages
            proposer_name = self.users[proposer_id].name
            target_name = self.users[target_id].name
            
            # Convert offer/request dicts to card lists for Game.trade()
            from pycatan.card import ResCard
            
            offer_cards = []
            for resource, amount in offer.items():
                card_type = self._resource_name_to_card(resource)
                offer_cards.extend([card_type] * amount)
            
            request_cards = []
            for resource, amount in request.items():
                card_type = self._resource_name_to_card(resource)
                request_cards.extend([card_type] * amount)
            
            # Validate that both players have the required cards
            if not self.game.players[proposer_id].has_cards(offer_cards):
                print(f"    ✗ You don't have the required cards to offer")
                return ActionResult.failure_result(
                    f"You don't have the required cards to offer",
                    "INSUFFICIENT_RESOURCES"
                )
            
            if not self.game.players[target_id].has_cards(request_cards):
                print(f"    ✗ {target_name} doesn't have the required cards")
                return ActionResult.failure_result(
                    f"{target_name} doesn't have the required cards",
                    "INSUFFICIENT_RESOURCES"
                )
            
            # Format the trade offer message
            offer_str = ", ".join([f"{amt} {res}" for res, amt in offer.items()])
            request_str = ", ".join([f"{amt} {res}" for res, amt in request.items()])
            
            # Ask the target player to accept or reject
            print(f"\n📢 Trade Proposal:")
            print(f"    {proposer_name} offers: {offer_str}")
            print(f"    {proposer_name} wants: {request_str}")
            print(f"    {target_name}, do you accept? (yes/no)")
            
            # Get response from target player
            target_user = self.users[target_id]
            response = target_user.get_input(
                self.get_full_state(),
                f"{target_name}, accept trade?",
                allowed_actions=[ActionType.TRADE_ACCEPT.name, ActionType.TRADE_REJECT.name]
            )
            
            # Handle response
            if response.action_type == ActionType.TRADE_ACCEPT:
                # Execute the trade
                status = self.game.trade(proposer_id, target_id, offer_cards, request_cards)
                
                if status == Statuses.ALL_GOOD:
                    print(f"    ✓ Trade completed between {proposer_name} and {target_name}!")
                    return ActionResult.success_result(
                        self.get_full_state(),
                        affected_players=[proposer_id, target_id]
                    )
                else:
                    return self._map_status_to_result(status)
            else:
                # Trade rejected
                print(f"    ✗ {target_name} rejected the trade")
                return ActionResult.failure_result(
                    f"{target_name} rejected your trade offer",
                    "TRADE_REJECTED"
                )
                
        except Exception as e:
            return ActionResult.failure_result(
                f"Error executing trade: {str(e)}",
                "EXECUTION_ERROR"
            )
    
    def _execute_trade_bank(self, action: Action) -> ActionResult:
        """Execute a trade with the bank."""
        try:
            player_id = action.player_id
            offer = action.parameters['offer']  # {resource: amount}
            request = action.parameters['request']  # {resource: amount}
            
            # Convert to card lists
            from pycatan.card import ResCard
            
            offer_cards = []
            for resource, amount in offer.items():
                card_type = self._resource_name_to_card(resource)
                offer_cards.extend([card_type] * amount)
            
            request_cards = []
            for resource, amount in request.items():
                card_type = self._resource_name_to_card(resource)
                request_cards.extend([card_type] * amount)
            
            # Execute bank trade
            status = self.game.trade_to_bank(player_id, offer_cards, request_cards)
            
            if status == Statuses.ALL_GOOD:
                offer_str = ", ".join([f"{amt} {res}" for res, amt in offer.items()])
                request_str = ", ".join([f"{amt} {res}" for res, amt in request.items()])
                print(f"    ✓ Bank trade: gave {offer_str}, received {request_str}")
                return ActionResult.success_result(
                    self.get_full_state(),
                    affected_players=[player_id]
                )
            else:
                return self._map_status_to_result(status)
                
        except Exception as e:
            return ActionResult.failure_result(
                f"Error executing bank trade: {str(e)}",
                "EXECUTION_ERROR"
            )
    
    def _resource_name_to_card(self, resource_name: str):
        """Convert resource name string to ResCard enum."""
        from pycatan.card import ResCard
        
        resource_map = {
            'wood': ResCard.Wood,
            'brick': ResCard.Brick,
            'sheep': ResCard.Sheep,
            'wheat': ResCard.Wheat,
            'ore': ResCard.Ore
        }
        
        return resource_map.get(resource_name.lower())
    
    def _execute_buy_dev_card(self, action: Action) -> ActionResult:
        """Execute buying a development card."""
        try:
            player_id = action.player_id
            
            # Call the game's build_dev method
            status = self.game.build_dev(player_id)
            
            if status == Statuses.ALL_GOOD:
                # Get the card that was just added (last card in player's dev_cards list)
                player = self.game.players[player_id]
                if player.dev_cards:
                    card_bought = player.dev_cards[-1]
                    print(f"    ✓ Bought development card: {card_bought.name}")
                else:
                    print(f"    ✓ Bought development card")
                
                return ActionResult.success_result(
                    self.get_full_state(),
                    affected_players=[player_id]
                )
            else:
                return self._map_status_to_result(status)
                
        except Exception as e:
            return ActionResult.failure_result(
                f"Error buying development card: {str(e)}",
                "EXECUTION_ERROR"
            )
    
    def _execute_use_dev_card(self, action: Action) -> ActionResult:
        """Execute using a development card - interactive multi-step process."""
        try:
            player_id = action.player_id
            card_type_str = action.parameters.get('card_type')
            
            if not card_type_str:
                return ActionResult.failure_result(
                    "Missing card_type parameter",
                    "MISSING_PARAMETER"
                )
            
            # Convert string to DevCard enum
            from pycatan.card import DevCard
            try:
                card_type = DevCard[card_type_str]
            except KeyError:
                return ActionResult.failure_result(
                    f"Invalid card type: {card_type_str}",
                    "INVALID_CARD_TYPE"
                )
            
            # Check if player has the card
            if not self.game.players[player_id].has_dev_cards([card_type]):
                return ActionResult.failure_result(
                    f"You don't have a {card_type.name} card",
                    "NO_CARD"
                )
            
            # Route to specific card handler
            if card_type == DevCard.Knight:
                return self._use_knight_card(player_id, action)
            elif card_type == DevCard.Road:
                return self._use_road_building_card(player_id, action)
            elif card_type == DevCard.Monopoly:
                return self._use_monopoly_card(player_id, action)
            elif card_type == DevCard.YearOfPlenty:
                return self._use_year_of_plenty_card(player_id, action)
            elif card_type == DevCard.VictoryPoint:
                return ActionResult.failure_result(
                    "Victory Point cards are counted automatically - don't use them!",
                    "CANNOT_USE_VP"
                )
            else:
                return ActionResult.failure_result(
                    f"Unknown card type: {card_type}",
                    "UNKNOWN_CARD"
                )
                
        except Exception as e:
            return ActionResult.failure_result(
                f"Error using development card: {str(e)}",
                "EXECUTION_ERROR"
            )
    
    def _use_road_building_card(self, player_id: int, action: Action) -> ActionResult:
        """Use Road Building card - needs 2 roads."""
        # Check if the action has the required road parameters
        if 'road_one_coords' not in action.parameters or 'road_two_coords' not in action.parameters:
            return ActionResult.failure_result(
                "Road Building card needs 2 roads in one command.\n"
                "    Format: use road rd [point1] [point2] rd [point3] [point4]\n"
                "    Example: use road rd 10 11 rd 12 13",
                "MISSING_PARAMS"
            )
        
        try:
            # Convert coordinates to point objects
            road1_start_coords = action.parameters['road_one_coords']['start']
            road1_end_coords = action.parameters['road_one_coords']['end']
            road2_start_coords = action.parameters['road_two_coords']['start']
            road2_end_coords = action.parameters['road_two_coords']['end']
            
            # Get point objects from board
            road1_start = self.game.board.points[road1_start_coords[0]][road1_start_coords[1]]
            road1_end = self.game.board.points[road1_end_coords[0]][road1_end_coords[1]]
            road2_start = self.game.board.points[road2_start_coords[0]][road2_start_coords[1]]
            road2_end = self.game.board.points[road2_end_coords[0]][road2_end_coords[1]]
            
            # Prepare args for game.use_dev_card
            args = {
                'road_one': {'start': road1_start, 'end': road1_end},
                'road_two': {'start': road2_start, 'end': road2_end}
            }
            
            # Use the card
            result = self.game.use_dev_card(
                player=player_id,
                card=DevCard.Road,
                args=args
            )
            
            if result == Statuses.ALL_GOOD:
                player_name = self.users[player_id].name if hasattr(self.users[player_id], 'name') else f"Player {player_id}"
                return ActionResult.success_result(
                    f"{player_name} used Road Building card and built 2 roads! 🛣️🛣️"
                )
            else:
                return ActionResult.failure_result(
                    f"Failed to use Road Building card: {result.name}",
                    result.name
                )
                
        except Exception as e:
            return ActionResult.failure_result(
                f"Error using Road Building card: {str(e)}",
                "EXECUTION_ERROR"
            )
    
    def _use_knight_card(self, player_id: int, action: Action) -> ActionResult:
        """Use Knight card - move robber and steal."""
        try:
            from pycatan.card import DevCard
            
            # Check if player has the card
            player = self.game.players[player_id]
            player_name = self.users[player_id].name if hasattr(self.users[player_id], 'name') else f"Player {player_id}"
            
            if not player.has_dev_cards([DevCard.Knight]):
                error_msg = f"❌ {player_name}, you don't have a Knight card!"
                print(f"\n{error_msg}")
                return ActionResult.failure_result(error_msg, "NO_CARD")
            
            # Get parameters from action
            tile_coords = action.parameters.get('tile_coords')
            victim_id = action.parameters.get('victim_id')
            
            if not tile_coords:
                error_msg = (
                    "Knight card requires robber tile location.\n"
                    "    Format: use knight tile [tile_id] [steal [player_name]]\n"
                    "    Example: use knight tile 5 steal Bob"
                )
                print(f"\n❌ {error_msg}")
                return ActionResult.failure_result(error_msg, "MISSING_PARAMS")
            
            row, index = tile_coords
            
            # Validate tile exists
            try:
                tile = self.game.board.tiles[row][index]
            except (IndexError, KeyError):
                error_msg = f"❌ Invalid tile coordinates: [{row}, {index}]"
                print(f"\n{error_msg}")
                return ActionResult.failure_result(error_msg, "INVALID_COORDS")
            
            # Check if robber is already there
            current_robber_pos = getattr(self.game.board, 'robber', None)
            if current_robber_pos and current_robber_pos == [row, index]:
                from pycatan.board_definition import board_definition
                hex_id = board_definition.game_coords_to_hex_id(row, index)
                tile_display = f"tile {hex_id}" if hex_id else f"[{row}, {index}]"
                error_msg = f"❌ The robber is already on {tile_display}! Choose a different tile."
                print(f"\n{error_msg}")
                return ActionResult.failure_result(error_msg, "SAME_POSITION")
            
            # If victim_id is None, we'll let the game automatically select
            # or use the first stealable player
            if victim_id is None:
                # Get stealable players
                stealable = self._get_stealable_players(row, index)
                if stealable:
                    # Auto-select first stealable player
                    victim_id = stealable[0]
            
            # Prepare args for game.use_dev_card()
            args = {
                'robber_pos': [row, index],
                'victim': victim_id
            }
            
            # Convert coordinates to hex ID for user-friendly messages
            from pycatan.board_definition import board_definition
            hex_id = board_definition.game_coords_to_hex_id(row, index)
            tile_display = f"tile {hex_id}" if hex_id else f"[{row}, {index}]"
            
            print(f"\n🎴 {player_name} is using Knight card...")
            
            # Execute the knight card
            # NOTE: game.use_dev_card already removes the card at the end - don't remove it again!
            status = self.game.use_dev_card(player_id, DevCard.Knight, args)
            
            if status != Statuses.ALL_GOOD:
                # Provide more specific error message for Knight card failures
                error_msg = "Invalid input"
                if status == Statuses.ERR_INPUT and victim_id is not None:
                    victim_name = self.users[victim_id].name if hasattr(self.users[victim_id], 'name') else f"Player {victim_id}"
                    error_msg = f"Cannot steal from {victim_name} - they have no settlements or cities adjacent to {tile_display}"
                    print(f"\n    ✗ {error_msg}\n")
                
                return self._convert_status_to_result(status, self.get_full_state(), [player_id])
            
            # Card already removed by game.use_dev_card() - no need to remove again!
            
            # Get stolen card info from args (set by game.use_dev_card)
            stolen_card = args.get('stolen_card')
            
            # Update visualizations
            player_name = self.users[player_id].name if hasattr(self.users[player_id], 'name') else f"Player {player_id}"
            
            # Print robber move notification immediately
            robber_msg = f"⚔️ {player_name} used a Knight card! Robber moved to {tile_display}."
            print(f"\n    {robber_msg}")
            
            # Send Knight card usage log to visualizations
            knight_log = create_log_entry(
                event_type=EventType.USE_DEV_CARD,
                turn=self._current_game_state.turn_number,
                player_id=player_id,
                player_name=player_name,
                data={
                    'card': 'Knight',
                    'robber_tile': tile_display,
                    'message': robber_msg
                },
                status="SUCCESS"
            )
            
            if self.visualization_manager:
                self.visualization_manager.log_event(knight_log)
            
            # Notify about robber move
            self._notify_all_users(
                "knight_used",
                robber_msg
            )
            
            # Notify about card steal if victim exists
            if victim_id is not None:
                victim_name = self.users[victim_id].name if hasattr(self.users[victim_id], 'name') else f"Player {victim_id}"
                
                # stolen_card was already retrieved from args above
                if stolen_card:
                    # Map card type to Hebrew/English name
                    card_names = {
                        'wood': 'עץ (Wood)',
                        'brick': 'לבנה (Brick)', 
                        'sheep': 'כבשה (Sheep)',
                        'wheat': 'חיטה (Wheat)',
                        'ore': 'עפרה (Ore)'
                    }
                    card_display = card_names.get(stolen_card.value, stolen_card.value)
                    steal_msg = f"🎯 {player_name} stole {card_display} from {victim_name}!"
                else:
                    steal_msg = f"🎯 {player_name} stole a card from {victim_name}!"
                
                print(f"\n    {steal_msg}")
                
                # Send steal log to visualizations
                steal_log = create_log_entry(
                    event_type=EventType.ROBBER_STEAL,
                    turn=self._current_game_state.turn_number,
                    player_id=player_id,
                    player_name=player_name,
                    data={
                        'victim_id': victim_id,
                        'victim': victim_name,
                        'card': stolen_card.name if stolen_card else 'unknown',  # Use .name to get 'Wood', 'Brick', etc.
                        'message': steal_msg
                    },
                    status="SUCCESS"
                )
                
                if self.visualization_manager:
                    self.visualization_manager.log_event(steal_log)
                
                self._notify_all_users("knight_steal", steal_msg)
            
            # Notify if player got Largest Army
            if self.game.largest_army == player_id:
                knights_count = self.game.players[player_id].knight_cards
                if knights_count >= 3:
                    self._notify_all_users(
                        "largest_army",
                        f"🏆 {player_name} now has the Largest Army! ({knights_count} knights = +2 VP)"
                    )
            
            return ActionResult.success_result(
                self.get_full_state(),
                affected_players=[player_id] if victim_id is None else [player_id, victim_id]
            )
            
        except Exception as e:
            return ActionResult.failure_result(
                f"Error using Knight card: {str(e)}",
                "EXECUTION_ERROR"
            )
    
    def _use_monopoly_card(self, player_id: int, action: Action) -> ActionResult:
        """Use Monopoly card - take all of one resource."""
        try:
            # Get resource type from action parameters
            resource_type = action.parameters.get('resource_type')
            if not resource_type:
                return ActionResult.failure_result(
                    "Resource type not specified.\n"
                    "    💬 Format: use monopoly [resource]\n"
                    "    Example: use monopoly wood",
                    "MISSING_PARAMETER"
                )
            
            # Convert resource name to ResCard enum
            from pycatan.card import ResCard
            resource_map = {
                'Wood': ResCard.Wood,
                'Brick': ResCard.Brick,
                'Sheep': ResCard.Sheep,
                'Wheat': ResCard.Wheat,
                'Ore': ResCard.Ore
            }
            
            card_type = resource_map.get(resource_type)
            if not card_type:
                return ActionResult.failure_result(
                    f"Invalid resource type: {resource_type}",
                    "INVALID_PARAMETER"
                )
            
            # Count how many cards will be stolen BEFORE using the card
            total_stolen = 0
            player = self.game.players[player_id]
            for p in self.game.players:
                if p != player:
                    stolen = p.cards.count(card_type)
                    total_stolen += stolen
            
            # Use the Monopoly card through game.py
            from pycatan.card import DevCard
            status = self.game.use_dev_card(
                player_id,
                DevCard.Monopoly,
                {'card_type': card_type}
            )
            
            if status == Statuses.ALL_GOOD:
                resource_name = resource_type.lower()
                player_name = self.users[player_id].name if hasattr(self.users[player_id], 'name') else f"Player {player_id}"
                
                print(f"    ✓ {player_name} used Monopoly! Took {total_stolen} {resource_name} cards from other players")
                
                return ActionResult.success_result(
                    self.get_full_state(),
                    affected_players=list(range(len(self.game.players)))
                )
            else:
                return self._map_status_to_result(status)
                
        except Exception as e:
            return ActionResult.failure_result(
                f"Error using Monopoly card: {str(e)}",
                "EXECUTION_ERROR"
            )
    
    def _use_year_of_plenty_card(self, player_id: int, action: Action) -> ActionResult:
        """Use Year of Plenty card - take 2 resources from bank."""
        return ActionResult.failure_result(
            "Year of Plenty card usage not yet fully implemented.\n"
            "    💬 You need to specify 2 resource cards to take from the bank.\n"
            "    Example: Take 1 Wood and 1 Brick (or 2 of the same)",
            "NOT_IMPLEMENTED"
        )
    
    def start_game(self) -> bool:
        """
        Start the game session.
        
        Initializes the game state and begins the main game loop.
        
        Returns:
            bool: True if game started successfully
        """
        if self._is_running:
            return False  # Already running
        
        # Initialize game state
        self._is_running = True
        self._is_paused = False
        
        # Notify all users
        self._notify_all_users(
            "game_start",
            f"Game {self.game_id} has started with {self.num_players} players!"
        )
        
        # Display Turn 0 immediately when game starts
        self._display_current_turn_start()
        
        return True
    
    def pause_game(self) -> bool:
        """Pause the game."""
        if not self._is_running or self._is_paused:
            return False
        
        self._is_paused = True
        self._notify_all_users("game_pause", "Game has been paused.")
        return True
    
    def resume_game(self) -> bool:
        """Resume a paused game."""
        if not self._is_running or not self._is_paused:
            return False
        
        self._is_paused = False
        self._notify_all_users("game_resume", "Game has been resumed.")
        return True
    
    def end_game(self) -> bool:
        """End the game session."""
        if not self._is_running:
            return False
        
        self._is_running = False
        self._is_paused = False
        
        # TODO: Calculate final scores, determine winner
        self._notify_all_users("game_end", "Game has ended.")
        return True
    
    def request_user_input(self, user_id: int, prompt: str, 
                          allowed_actions: Optional[List[str]] = None) -> Action:
        """
        Request input from a specific user.
        
        Args:
            user_id: ID of the user to request input from
            prompt: Message explaining what input is needed
            allowed_actions: Optional list of allowed action types
            
        Returns:
            Action: The action chosen by the user
            
        Raises:
            UserInputError: If user input fails
        """
        if user_id >= len(self.users):
            raise UserInputError(f"Invalid user ID: {user_id}")
        
        user = self.users[user_id]
        
        if not user.is_active:
            raise UserInputError(f"User {user_id} is not active")
        
        try:
            return user.get_input(
                self.get_full_state(),
                prompt,
                allowed_actions
            )
        except Exception as e:
            raise UserInputError(f"Failed to get input from user {user_id}: {e}", user)
    
    def _notify_all_users(self, event_type: str, message: str, 
                         affected_players: Optional[List[int]] = None) -> None:
        """Notify all users about a game event."""
        for user in self.users:
            if user.is_active:
                user.notify_game_event(event_type, message, affected_players)
    
    def _notify_user(self, user_id: int, action: Action, success: bool, message: str = "") -> None:
        """Notify a specific user about an action result."""
        if user_id < len(self.users) and self.users[user_id].is_active:
            self.users[user_id].notify_action(action, success, message)
    
    def get_action_history(self) -> List[Action]:
        """Get the complete action history for this game."""
        return self._action_history.copy()
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get a user by their ID."""
        if 0 <= user_id < len(self.users):
            return self.users[user_id]
        return None
    
    def game_loop(self) -> None:
        """
        Main game loop that runs the entire game from start to finish.
        
        This is the central function that orchestrates the entire game flow.
        It manages turn order, requests input from users, executes actions,
        and updates all systems until the game ends.
        
        Flow:
        1. Check if game is running and not paused
        2. Get input from current player
        3. Attempt to execute the action
        4. Update all systems (visualizations, users)
        5. Check win conditions
        6. Move to next turn if needed
        
        The function runs until the game ends or is explicitly stopped.
        """
        # Continue running until game ends or is explicitly stopped
        while self._is_running and not self._check_game_end_conditions():
            
            # If game is paused, wait
            if self._is_paused:
                # In paused state, just continue loop without doing anything
                continue
            
            # Run a single turn for the current player
            try:
                turn_ended = self._handle_single_turn()
                
                # Reset error count on successful turn processing
                self._player_error_count[self.current_player_id] = 0
                
                # Only advance to next player if turn actually ended
                if turn_ended:
                    self._advance_to_next_player()
                    
            except Exception as e:
                # Increment error count for current player
                self._player_error_count[self.current_player_id] += 1
                
                # If error occurred, notify current player
                self._notify_all_users(
                    "error", 
                    f"Error during player {self.current_player_id}'s turn: {str(e)}."
                )
                
                # If too many consecutive errors for this player, skip their turn
                if self._player_error_count[self.current_player_id] >= 3:
                    self._notify_all_users(
                        "player_skip",
                        f"Player {self.current_player_id} had too many errors. Skipping turn."
                    )
                    self._advance_to_next_player()
                else:
                    self._notify_all_users(
                        "retry",
                        f"Player {self.current_player_id} can try again."
                    )
        
        # Game has ended - handle cleanup
        self._handle_game_end()
    
    def _handle_single_turn(self) -> bool:
        """
        Handles a single turn of one player.
        
        This function manages one complete turn of a single player:
        1. Requests an action from the current user
        2. Attempts to execute the action
        3. Updates all systems about the result
        4. Determines if the turn should end or continue
        
        Special handling for discard phase when 7 is rolled:
        - During discard phase, each player who needs to discard gets prompted in turn
        
        Returns:
            bool: True if the turn ended, False if player wants to continue
        """
        # Special handling for discard phase - ask each player who needs to discard
        if self._current_game_state.turn_phase == TurnPhase.DISCARD_PHASE:
            return self._handle_discard_phase_turn()
        
        # Get the current player's action
        action_result = self._process_user_action()
        
        # Update all systems about what happened
        if hasattr(action_result, 'action'):
            self._update_all_systems(action_result.action, action_result)
        
        # Determine if turn should end
        if action_result.success and hasattr(action_result, 'action'):
            action = action_result.action
            
            # END_TURN action explicitly ends the turn
            if action.action_type == ActionType.END_TURN:
                return True
            
            # Auto-end turn in setup phase if both actions are done
            phase = self._current_game_state.game_phase
            if phase in [GamePhase.SETUP_FIRST_ROUND, GamePhase.SETUP_SECOND_ROUND]:
                if self._setup_turn_progress['settlement'] and self._setup_turn_progress['road']:
                    return True
            
            # For other successful actions, player can continue
            return False
        else:
            # If action failed, player can try again (don't end turn)
            return False
    
    def _handle_discard_phase_turn(self) -> bool:
        """
        Handle the discard phase when 7 is rolled.
        
        Each player who needs to discard is prompted in turn order.
        After all players have discarded, the phase moves to robber move.
        
        Returns:
            bool: Always False (don't advance to next player during discard)
        """
        # Find the next player who needs to discard
        players_needing_discard = self._current_game_state.players_must_discard
        
        if not players_needing_discard:
            # All done discarding - this shouldn't happen but handle it
            self._current_game_state.turn_phase = TurnPhase.ROBBER_MOVE
            return False
        
        # Get the first player who still needs to discard
        discard_player_id = min(players_needing_discard.keys())
        discard_count = players_needing_discard[discard_player_id]
        
        # Get the user for this player
        discard_user = self.users[discard_player_id]
        player_name = discard_user.name if hasattr(discard_user, 'name') else f"Player {discard_player_id}"
        
        # Request discard action from this player
        allowed_actions = [ActionType.DISCARD_CARDS.name]
        
        try:
            action = discard_user.get_input(
                self.get_full_state(),
                f"{player_name}, you must discard {discard_count} cards. Use: drop [amount] [resource] ...",
                allowed_actions
            )
            
            # Override the player_id to match the discarding player (not current turn player)
            action.player_id = discard_player_id
            
            # Execute the discard action
            result = self._handle_discard_cards(action)
            
            # Update systems
            self._update_all_systems(action, result)
            
        except Exception as e:
            self._notify_all_users(
                "error",
                f"Error during {player_name}'s discard: {str(e)}"
            )
        
        # Don't end the turn - continue with discard phase or move to robber
        return False
    
    def _process_user_action(self) -> ActionResult:
        """
        Requests an action from the current user and attempts to execute it.
        
        This function:
        1. Identifies the current player
        2. Requests them to choose an action via get_input()
        3. Validates the action
        4. Attempts to execute the action via execute_action()
        5. Returns the result
        
        Returns:
            ActionResult: The result of executing the action
        """
        try:
            # Get the current user
            current_user = self.current_user
            
            # Get allowed actions for current state
            allowed_actions = self.get_available_actions()
            
            # Create context-aware prompt message
            prompt_message = self._get_prompt_message_for_phase()
            
            # Request action from the current user
            action = current_user.get_input(
                self.get_full_state(),
                prompt_message,
                allowed_actions
            )
            
            # Validate that the action is for the current player
            if action.player_id != self.current_player_id:
                return ActionResult.failure_result(
                    f"Action player_id {action.player_id} doesn't match current player {self.current_player_id}",
                    "INVALID_PLAYER_ID"
                )
            
            # Execute the action
            result = self.execute_action(action)
            
            # Add the action to the result for reference
            if hasattr(result, 'action'):
                result.action = action
            else:
                # If ActionResult doesn't have action field, add it dynamically
                setattr(result, 'action', action)
            
            return result
            
        except Exception as e:
            # Handle any errors during action processing
            return ActionResult.failure_result(
                f"Error processing user action: {str(e)}",
                "ACTION_PROCESSING_ERROR"
            )
    
    def _enrich_action_parameters(self, action: Action, result: ActionResult) -> None:
        """
        Enrich action parameters with detailed information for visualization and logging.
        Adds all relevant details like point numbers, costs, card types, etc.
        """
        from .card import ResCard, DevCard
        from .board_definition import board_definition
        
        # Ensure parameters dict exists
        if not hasattr(action, 'parameters') or action.parameters is None:
            action.parameters = {}
        
        params = action.parameters
        
        # Add turn number
        params['turn_number'] = self._current_game_state.turn_number
        
        # Building actions - add point number and costs
        if action.action_type in [ActionType.BUILD_SETTLEMENT, ActionType.PLACE_STARTING_SETTLEMENT]:
            if 'point_coords' in params:
                coords = params['point_coords']
                try:
                    point_id = board_definition.game_coords_to_point_id(coords[0], coords[1])
                    params['point'] = point_id if point_id else f"[{coords[0]},{coords[1]}]"
                except:
                    params['point'] = f"[{coords[0]},{coords[1]}]"
            
            if result.success and action.action_type == ActionType.BUILD_SETTLEMENT:
                params['cost'] = ['WOOD', 'BRICK', 'WHEAT', 'SHEEP']
        
        elif action.action_type == ActionType.BUILD_CITY:
            if 'point_coords' in params:
                coords = params['point_coords']
                try:
                    point_id = board_definition.game_coords_to_point_id(coords[0], coords[1])
                    params['point'] = point_id if point_id else f"[{coords[0]},{coords[1]}]"
                except:
                    params['point'] = f"[{coords[0]},{coords[1]}]"
            
            if result.success:
                params['cost'] = ['ORE', 'ORE', 'ORE', 'WHEAT', 'WHEAT']
        
        elif action.action_type in [ActionType.BUILD_ROAD, ActionType.PLACE_STARTING_ROAD]:
            if 'start_coords' in params and 'end_coords' in params:
                start_coords = params['start_coords']
                end_coords = params['end_coords']
                try:
                    start_id = board_definition.game_coords_to_point_id(start_coords[0], start_coords[1])
                    end_id = board_definition.game_coords_to_point_id(end_coords[0], end_coords[1])
                    params['points'] = [start_id, end_id] if (start_id and end_id) else [start_coords, end_coords]
                except:
                    params['points'] = [start_coords, end_coords]
            
            if result.success and action.action_type == ActionType.BUILD_ROAD:
                params['cost'] = ['WOOD', 'BRICK']
        
        # Dev card actions
        elif action.action_type == ActionType.BUY_DEV_CARD:
            if result.success:
                # Try to get the actual card that was drawn
                player = self.game.players[action.player_id]
                if player.dev_cards:
                    last_card = player.dev_cards[-1]
                    params['card'] = last_card.name if hasattr(last_card, 'name') else str(last_card)
                params['cost'] = ['ORE', 'SHEEP', 'WHEAT']
        
        elif action.action_type == ActionType.USE_DEV_CARD:
            if 'card_type' in params:
                card_type = params['card_type']
                params['card'] = card_type.name if hasattr(card_type, 'name') else str(card_type)
        
        # Dice roll
        elif action.action_type == ActionType.ROLL_DICE:
            if 'dice' in params:
                params['total'] = sum(params['dice'])
        
        # Robber actions
        elif action.action_type == ActionType.ROBBER_MOVE:
            if 'tile_coords' in params:
                params['tile'] = str(params['tile_coords'])
        
        # Trading
        elif action.action_type == ActionType.TRADE_BANK:
            # params should already have 'give' and 'receive'
            pass
        
        elif action.action_type == ActionType.TRADE_PROPOSE:
            if 'target_player' in params:
                target_id = params['target_player']
                target_name = self.users[target_id].name if hasattr(self.users[target_id], 'name') else f"Player {target_id}"
                params['to_player'] = target_name
        
        # End turn - add player state
        elif action.action_type == ActionType.END_TURN:
            player = self.game.players[action.player_id]
            params['player_state'] = {
                'victory_points': player.victory_points,
                'card_count': len(player.cards),
                'roads': len(player.roads) if hasattr(player, 'roads') and player.roads else 0,
                'settlements': len(player.settlements) if hasattr(player, 'settlements') and player.settlements else 0,
                'cities': len(player.cities) if hasattr(player, 'cities') and player.cities else 0
            }
    
    def _update_all_systems(self, action: Action, result: ActionResult) -> None:
        """
        Updates all systems after an action has been executed.
        
        This function ensures that all parts of the system are informed
        about what happened and can update their displays accordingly.
        
        Updates:
        1. Notifies all users about the action and its result
        2. Updates visualizations with new game state
        3. Logs the action for history/debugging
        4. Handles any side effects of the action
        
        Args:
            action: The action that was executed
            result: The result of the action execution
        """
        # Notify the specific user who performed the action
        self._notify_user(
            action.player_id, 
            action, 
            result.success, 
            result.error_message or ""
        )
        
        # If action failed, print error message immediately to console for visibility
        if not result.success and result.error_message:
            player_name = self.users[action.player_id].name if hasattr(self.users[action.player_id], 'name') else f"Player {action.player_id}"
            print(f"\n    ✗ {player_name}: {result.error_message}\n")
        
        # If action was successful, notify all users about the action
        if result.success:
            action_description = self._get_action_description(action)
            self._notify_all_users(
                "action_performed",
                f"Player {action.player_id} {action_description}",
                result.affected_players if hasattr(result, 'affected_players') else [action.player_id]
            )
        
        # Update visualizations if available
        if self.visualization_manager:
            try:
                # Add player name to action parameters for better visualization
                if not hasattr(action, 'parameters') or action.parameters is None:
                    action.parameters = {}
                
                # Add player name if not already present
                if 'player_name' not in action.parameters:
                    player_name = self.users[action.player_id].name if hasattr(self.users[action.player_id], 'name') else f"Player {action.player_id}"
                    action.parameters['player_name'] = player_name
                
                # Enrich action parameters with detailed information for logging
                self._enrich_action_parameters(action, result)
                
                # Display the action result (success or failure)
                self.visualization_manager.display_action(action, result)
                
                current_state = self.get_full_state()
                # Pass GameState object directly so visualizations can extract what they need
                self.visualization_manager.display_game_state(current_state)
            except Exception as e:
                # Log visualization errors
                import traceback
                print(f"Error updating visualizations: {e}")
                print(f"Traceback: {traceback.format_exc()}")
        
        # Log the action and result for debugging
        if self.config.get('debug', False):
            # Only print if debug config is explicitly enabled
            pass

    def _gamestate_to_dict(self, game_state) -> Dict[str, Any]:
        """Convert GameState object to dict format expected by visualizations."""
        try:
            return {
                'game_id': game_state.game_id,
                'turn_number': game_state.turn_number,
                'current_player': game_state.current_player,
                'current_player_name': self.users[game_state.current_player].name if hasattr(self.users[game_state.current_player], 'name') else f"Player {game_state.current_player}",
                'game_phase': game_state.game_phase.name if hasattr(game_state.game_phase, 'name') else str(game_state.game_phase),
                'turn_phase': game_state.turn_phase.name if hasattr(game_state.turn_phase, 'name') else str(game_state.turn_phase),
                'players': [
                    {
                        'id': i,
                        'name': self.users[i].name if hasattr(self.users[i], 'name') else f"Player {i}",
                        'victory_points': player.victory_points,
                        'cards': len(player.cards),
                        'settlements': len(player.settlements),
                        'cities': len(player.cities),
                        'roads': len(player.roads),
                        'longest_road_length': player.longest_road_length,
                        'has_longest_road': player.has_longest_road,
                        'has_largest_army': player.has_largest_army,
                        'knights_played': player.knights_played
                    }
                    for i, player in enumerate(game_state.players_state)
                ],
                'board': {
                    'tiles_count': len(game_state.board_state.tiles),
                    'robber_position': game_state.board_state.robber_position,
                    'buildings_count': len(game_state.board_state.buildings),
                    'roads_count': len(game_state.board_state.roads)
                }
            }
        except Exception as e:
            # Fallback dict if conversion fails
            return {
                'turn_number': getattr(game_state, 'turn_number', 0),
                'current_player': getattr(game_state, 'current_player', 0),
                'current_player_name': f"Player {getattr(game_state, 'current_player', 0)}",
                'game_phase': 'UNKNOWN',
                'players': [],
                'board': {}
            }
    
    def _get_action_description(self, action: Action) -> str:
        """
        Get a human-readable description of an action.
        
        Args:
            action: The action to describe
            
        Returns:
            str: Human-readable description
        """
        if action.action_type == ActionType.BUILD_SETTLEMENT:
            return "built a settlement"
        elif action.action_type == ActionType.BUILD_CITY:
            return "built a city"
        elif action.action_type == ActionType.BUILD_ROAD:
            return "built a road"
        elif action.action_type == ActionType.END_TURN:
            return "ended their turn"
        elif action.action_type == ActionType.TRADE_PROPOSE:
            return "proposed a trade"
        else:
            return f"performed action: {action.action_type}"
    
    def _advance_to_next_player(self) -> None:
        """
        Advances the game to the next player's turn.
        
        This function handles the transition between players,
        updating turn counters and notifying all users.
        It implements the "Snake Draft" order for setup phase:
        Round 1: 0 -> 1 -> ... -> N-1
        Round 2: N-1 -> N-2 -> ... -> 0
        """
        # Reset setup progress for the new turn
        self._setup_turn_progress = {'settlement': False, 'road': False}
        
        # Reset dice_rolled for the new turn (important for normal play!)
        self._current_game_state.dice_rolled = None

        # Increment turn number
        self._current_game_state.turn_number += 1
        turn = self._current_game_state.turn_number
        
        # Handle Setup Phase Logic
        if self._current_game_state.game_phase == GamePhase.SETUP_FIRST_ROUND:
            if turn < self.num_players:
                # Still in first round, standard order
                self._current_game_state.current_player = turn
            else:
                # Switch to second round
                self._current_game_state.game_phase = GamePhase.SETUP_SECOND_ROUND
                # The first player of second round is the last player of first round
                self._current_game_state.current_player = self.num_players - 1
                self._notify_all_users("phase_change", "First round of setup complete! Starting second round (reverse order).")
                
        elif self._current_game_state.game_phase == GamePhase.SETUP_SECOND_ROUND:
            # Check if setup is done
            if turn >= self.num_players * 2:
                self._current_game_state.game_phase = GamePhase.NORMAL_PLAY
                self._current_game_state.current_player = 0
                self._notify_all_users("phase_change", "Setup complete! Entering Normal Play phase.")
            else:
                # Calculate reverse order for snake draft
                # Formula: (2 * num_players - 1) - turn
                self._current_game_state.current_player = (2 * self.num_players - 1) - turn
        
        else: # Normal Play
             self._current_game_state.current_player = (self._current_game_state.current_player + 1) % self.num_players
        
        # Display turn start
        self._display_current_turn_start()
    
    def _display_current_turn_start(self) -> None:
        """Display turn start notification for the current player and turn."""
        # Notify all users about the turn change
        self._notify_all_users(
            "turn_change", 
            f"Turn {self._current_game_state.turn_number}: Player {self._current_game_state.current_player}'s turn begins."
        )
        
        # Notify visualization
        if self.visualization_manager:
            player_id = self._current_game_state.current_player
            player_name = self.users[player_id].name if hasattr(self.users[player_id], 'name') else f"Player {player_id + 1}"
            self.visualization_manager.display_turn_start(player_name, self._current_game_state.turn_number)
    
    def _handle_game_end(self) -> None:
        """
        Handles the end of the game.
        
        This function is called when the game loop exits,
        either due to win conditions or explicit termination.
        """
        # Set game as not running
        self._is_running = False
        self._is_paused = False
        
        # TODO: Calculate final scores and determine winner
        # For now, just notify that game ended
        self._notify_all_users("game_end", "Game has ended.")
        
        # TODO: Cleanup resources, save game state, etc.
    
    def _check_game_end_conditions(self) -> bool:
        """
        Checks if the game has ended based on win conditions.
        
        This function examines the current game state to determine
        if any player has achieved victory conditions.
        
        Standard Catan win conditions:
        1. First player to reach 10 victory points wins
        2. Victory points come from: settlements (1), cities (2), 
           development cards (1 each), longest road (2), largest army (2)
        
        Returns:
            bool: True if game has ended (someone won), False if game continues
        """
        # Check victory points for each player
        for player_id in range(self.num_players):
            player = self.game.players[player_id]
            
            # Calculate total victory points for this player
            # We include dev cards because we want to know if they actually won
            victory_points = player.get_VP(include_dev=True)
            
            # Check if this player has won (10+ victory points)
            if victory_points >= 10:
                self._announce_winner(player_id, victory_points)
                return True
        
        # No player has won yet
        return False
    
    def _announce_winner(self, player_id: int, victory_points: int) -> None:
        """
        Announces the winner of the game.
        
        Args:
            player_id: ID of the winning player
            victory_points: Number of victory points the winner achieved
        """
        winner_name = self.users[player_id].name if hasattr(self.users[player_id], 'name') else f"Player {player_id}"
        
        self._notify_all_users(
            "game_winner",
            f"🎉 {winner_name} has won the game with {victory_points} victory points! 🎉"
        )
        
        # Log the victory for debugging/statistics
        print(f"[GAME END] Player {player_id} ({winner_name}) won with {victory_points} victory points")
    
    def _handle_roll_dice(self, action: Action) -> ActionResult:
        """Handle dice rolling."""
        # Check game phase
        if self._current_game_state.game_phase != GamePhase.NORMAL_PLAY:
             return ActionResult.failure_result(
                 f"Cannot roll dice in {self._current_game_state.game_phase.name} phase.\n"
                 "💡 Hint: In setup phase, use 'settlement <point> starting' and 'road <p1> <p2> starting'.", 
                 "INVALID_PHASE"
             )

        # Check if dice already rolled this turn
        if self._current_game_state.dice_rolled:
             return ActionResult.failure_result("Dice already rolled this turn", "ALREADY_ROLLED")
             
        # Roll dice
        die1 = random.randint(1, 6)
        die2 = random.randint(1, 6)
        total = die1 + die2
        
        # Update action parameters for logging/visualization
        if not hasattr(action, 'parameters') or action.parameters is None:
            action.parameters = {}
        action.parameters['dice'] = [die1, die2]
        action.parameters['total'] = total
        
        # Update state
        self._current_game_state.dice_rolled = (die1, die2)
        
        # Distribute resources or handle robber
        if total != 7:
            distribution = self.game.add_yield_for_roll(total)
            
            # Add distribution to action parameters for logging
            action.parameters['distribution'] = distribution
            
            # Send individual log events for each resource distribution
            if distribution and self.visualization_manager:
                from .log_events import EventType, create_log_entry
                
                for player_key, resources in distribution.items():
                    if resources:  # Only log if player actually got resources
                        # Extract player ID from "Player X" format or match by name
                        player_id = None
                        player_name = None
                        
                        # Try to extract player ID from "Player X" format
                        if player_key.startswith("Player "):
                            try:
                                player_id = int(player_key.split()[-1]) - 1  # "Player 1" -> 0
                                if 0 <= player_id < len(self.users):
                                    player_name = self.users[player_id].name if hasattr(self.users[player_id], 'name') else player_key
                            except:
                                pass
                        
                        # Fallback: try to match by name
                        if player_id is None:
                            for i, user in enumerate(self.users):
                                if hasattr(user, 'name') and user.name == player_key:
                                    player_id = i
                                    player_name = player_key
                                    break
                        
                        # If still not found, skip this entry
                        if player_id is None:
                            continue
                        
                        # Count resources by type
                        resource_counts = {}
                        for res in resources:
                            resource_counts[res] = resource_counts.get(res, 0) + 1
                        
                        # Create log entry
                        log_entry = create_log_entry(
                            event_type=EventType.RESOURCE_DIST,
                            turn=self._current_game_state.turn_number,
                            player_id=player_id,
                            player_name=player_name,
                            data={
                                'resources': resource_counts,
                                'total': len(resources),
                                'dice_roll': total
                            }
                        )
                        
                        # Send to visualizations
                        if self.visualization_manager:
                            self.visualization_manager.log_event(log_entry)
            
            if distribution:
                message = f"Rolled {total} ({die1}+{die2}). Resources distributed."
            else:
                message = f"Rolled {total} ({die1}+{die2}). No settlements on this number."
        else:
            # Rolled 7! Handle robber sequence
            message = f"Rolled 7 ({die1}+{die2})! 🏴‍☠️ Robber activated!"
            self._handle_rolled_seven()
            
        # Notify
        self._notify_all_users("dice_roll", message)
        
        return ActionResult.success_result(
            self.get_full_state()
        )
    
    def _handle_rolled_seven(self) -> None:
        """
        Handle the effects of rolling a 7:
        1. Check which players have more than 7 cards and need to discard
        2. Set up the discard phase if needed
        3. Prepare for robber movement
        """
        # Check which players need to discard (more than 7 cards)
        players_must_discard = {}
        
        for player_id, player in enumerate(self.game.players):
            card_count = len(player.cards)
            if card_count > 7:
                # Must discard half, rounded down
                discard_count = card_count // 2
                players_must_discard[player_id] = discard_count
                
                player_name = self.users[player_id].name if hasattr(self.users[player_id], 'name') else f"Player {player_id}"
                self._notify_all_users(
                    "discard_required",
                    f"⚠️ {player_name} has {card_count} cards and must discard {discard_count}."
                )
        
        # Store the discard requirements in game state
        self._current_game_state.players_must_discard = players_must_discard
        self._current_game_state.robber_moved = False
        self._current_game_state.steal_pending = False
        
        # Set the appropriate turn phase
        if players_must_discard:
            self._current_game_state.turn_phase = TurnPhase.DISCARD_PHASE
        else:
            # No one needs to discard, go straight to robber move
            self._current_game_state.turn_phase = TurnPhase.ROBBER_MOVE
            self._notify_all_users(
                "robber",
                f"🏴‍☠️ {self.users[self.current_player_id].name} must move the robber!"
            )
    
    def _handle_discard_cards(self, action: Action) -> ActionResult:
        """
        Handle a player discarding cards (when 7 is rolled).
        
        The action must contain:
        - cards: List of card names to discard
        """
        player_id = action.player_id
        cards_to_discard = action.parameters.get('cards', [])
        
        # Check if this player needs to discard
        required_discard = self._current_game_state.players_must_discard.get(player_id, 0)
        
        if required_discard == 0:
            return ActionResult.failure_result(
                "You don't need to discard any cards.",
                "NO_DISCARD_REQUIRED"
            )
        
        # Check if they're discarding the right amount
        if len(cards_to_discard) != required_discard:
            return ActionResult.failure_result(
                f"You must discard exactly {required_discard} cards, but you're trying to discard {len(cards_to_discard)}.",
                "WRONG_DISCARD_COUNT"
            )
        
        # Convert card names to ResCard enum and verify player has them
        from pycatan.card import ResCard
        
        player = self.game.players[player_id]
        cards_enum = []
        
        for card_name in cards_to_discard:
            try:
                card = ResCard[card_name]
                cards_enum.append(card)
            except KeyError:
                return ActionResult.failure_result(
                    f"Unknown card type: {card_name}",
                    "INVALID_CARD"
                )
        
        # Check if player has all these cards
        if not player.has_cards(cards_enum):
            return ActionResult.failure_result(
                "You don't have all the cards you're trying to discard.",
                "MISSING_CARDS"
            )
        
        # Remove the cards from player
        player.remove_cards(cards_enum)
        
        # Update discard tracking
        del self._current_game_state.players_must_discard[player_id]
        
        player_name = self.users[player_id].name if hasattr(self.users[player_id], 'name') else f"Player {player_id}"
        self._notify_all_users(
            "discard_complete",
            f"✓ {player_name} discarded {len(cards_to_discard)} cards."
        )
        
        # Check if all players have finished discarding
        if not self._current_game_state.players_must_discard:
            # All discards complete, move to robber phase
            self._current_game_state.turn_phase = TurnPhase.ROBBER_MOVE
            current_player_name = self.users[self.current_player_id].name if hasattr(self.users[self.current_player_id], 'name') else f"Player {self.current_player_id}"
            self._notify_all_users(
                "robber",
                f"🏴‍☠️ {current_player_name} must now move the robber!"
            )
        
        return ActionResult.success_result(self.get_full_state())
    
    def _handle_robber_move(self, action: Action) -> ActionResult:
        """
        Handle moving the robber to a new tile.
        
        The action must contain:
        - tile_coords: [row, index] of the new robber position
        """
        tile_coords = action.parameters.get('tile_coords')
        
        if not tile_coords:
            return ActionResult.failure_result(
                "Robber move requires tile coordinates.",
                "MISSING_COORDS"
            )
        
        row, index = tile_coords
        
        # Validate the tile exists
        try:
            tile = self.game.board.tiles[row][index]
        except (IndexError, KeyError):
            return ActionResult.failure_result(
                f"Invalid tile coordinates: [{row}, {index}]",
                "INVALID_COORDS"
            )
        
        # Can't place robber on desert (already there) - check if it's the same position
        current_robber_pos = getattr(self.game.board, 'robber', None)
        if current_robber_pos and current_robber_pos == [row, index]:
            return ActionResult.failure_result(
                "You must move the robber to a different tile.",
                "SAME_POSITION"
            )
        
        # Move the robber
        # First, remove robber from current position
        if current_robber_pos:
            old_row, old_index = current_robber_pos
            try:
                self.game.board.tiles[old_row][old_index].has_robber = False
            except (IndexError, AttributeError):
                pass
        
        # Place robber on new position
        tile.has_robber = True
        self.game.board.robber = [row, index]  # Use the Board's robber attribute
        
        self._current_game_state.robber_moved = True
        
        # Find players adjacent to this tile who can be stolen from
        stealable_players = self._get_stealable_players(row, index)
        
        player_name = self.users[action.player_id].name if hasattr(self.users[action.player_id], 'name') else f"Player {action.player_id}"
        self._notify_all_users(
            "robber_moved",
            f"🏴‍☠️ {player_name} moved the robber to [{row}, {index}]."
        )
        
        if stealable_players:
            # Check if there's only one player to steal from
            if len(stealable_players) == 1:
                # Auto-steal from the only available player
                target_player = stealable_players[0]
                
                # Steal a random card
                import random
                target = self.game.players[target_player]
                stolen_card = random.choice(target.cards)
                target.remove_cards([stolen_card])
                self.game.players[action.player_id].add_cards([stolen_card])
                
                # Notify
                thief_name = self.users[action.player_id].name if hasattr(self.users[action.player_id], 'name') else f"Player {action.player_id}"
                victim_name = self.users[target_player].name if hasattr(self.users[target_player], 'name') else f"Player {target_player}"
                
                self._notify_all_users(
                    "steal_complete",
                    f"🎯 {thief_name} stole a card from {victim_name} (only adjacent player)."
                )
                
                # Notify the thief specifically what they got
                self._notify_user(
                    action.player_id,
                    None,
                    True,
                    f"You stole a {stolen_card.name}!"
                )
                
                # Proceed to normal play
                self._current_game_state.turn_phase = TurnPhase.PLAYER_ACTIONS
                self._current_game_state.steal_pending = False
            else:
                # Multiple players - ask user to choose
                self._current_game_state.turn_phase = TurnPhase.ROBBER_STEAL
                self._current_game_state.steal_pending = True
                
                stealable_names = [self.users[pid].name for pid in stealable_players]
                self._notify_all_users(
                    "steal_available",
                    f"🎯 {player_name} can steal from: {', '.join(stealable_names)}"
                )
        else:
            # No one to steal from, proceed to normal play
            self._current_game_state.turn_phase = TurnPhase.PLAYER_ACTIONS
            self._notify_all_users(
                "robber_complete",
                "No players with cards adjacent to robber. Proceeding with turn."
            )
        
        return ActionResult.success_result(self.get_full_state())
    
    def _get_stealable_players(self, tile_row: int, tile_index: int) -> List[int]:
        """
        Get list of player IDs who have settlements/cities adjacent to the given tile
        and have at least 1 card (excluding the current player).
        """
        stealable = []
        current_player = self.current_player_id
        
        try:
            tile = self.game.board.tiles[tile_row][tile_index]
        except (IndexError, KeyError):
            return []
        
        # Get all points adjacent to this tile
        adjacent_points = tile.points if hasattr(tile, 'points') else []
        
        for point in adjacent_points:
            if point.building is not None:
                owner_id = point.building.owner
                # Don't include current player, and don't include players with no cards
                if owner_id != current_player and owner_id not in stealable:
                    if len(self.game.players[owner_id].cards) > 0:
                        stealable.append(owner_id)
        
        return stealable
    
    def _handle_steal_card(self, action: Action) -> ActionResult:
        """
        Handle stealing a card from a player adjacent to the robber.
        
        The action must contain:
        - target_player: Player ID to steal from (or None if no one to steal from)
        """
        target_player = action.parameters.get('target_player')
        
        if target_player is None:
            # No one to steal from
            self._current_game_state.turn_phase = TurnPhase.PLAYER_ACTIONS
            self._current_game_state.steal_pending = False
            return ActionResult.success_result(self.get_full_state())
        
        # Validate target player
        if target_player < 0 or target_player >= self.num_players:
            return ActionResult.failure_result(
                f"Invalid player ID: {target_player}",
                "INVALID_PLAYER"
            )
        
        if target_player == action.player_id:
            return ActionResult.failure_result(
                "You cannot steal from yourself!",
                "STEAL_SELF"
            )
        
        # Check target has cards
        target = self.game.players[target_player]
        if len(target.cards) == 0:
            return ActionResult.failure_result(
                f"Player {target_player} has no cards to steal.",
                "NO_CARDS"
            )
        
        # Check target is adjacent to robber
        robber_pos = getattr(self.game.board, 'robber', None)
        if robber_pos:
            stealable = self._get_stealable_players(robber_pos[0], robber_pos[1])
            if target_player not in stealable:
                return ActionResult.failure_result(
                    f"Player {target_player} is not adjacent to the robber.",
                    "NOT_ADJACENT"
                )
        
        # Steal a random card
        import random
        stolen_card = random.choice(target.cards)
        target.remove_cards([stolen_card])
        self.game.players[action.player_id].add_cards([stolen_card])
        
        # Update state
        self._current_game_state.turn_phase = TurnPhase.PLAYER_ACTIONS
        self._current_game_state.steal_pending = False
        
        # Notify (don't reveal what card was stolen to everyone)
        thief_name = self.users[action.player_id].name if hasattr(self.users[action.player_id], 'name') else f"Player {action.player_id}"
        victim_name = self.users[target_player].name if hasattr(self.users[target_player], 'name') else f"Player {target_player}"
        
        self._notify_all_users(
            "steal_complete",
            f"🎯 {thief_name} stole a card from {victim_name}!"
        )
        
        # Notify the thief specifically what they got
        self._notify_user(
            action.player_id,
            action,
            True,
            f"You stole a {stolen_card.name}!"
        )
        
        return ActionResult.success_result(self.get_full_state())
    
    def _get_prompt_message_for_phase(self) -> str:
        """
        Get a context-appropriate prompt message based on current game phase.
        
        Returns:
            str: A helpful message explaining what the player should do
        """
        phase = self._current_game_state.turn_phase
        
        if phase == TurnPhase.ROBBER_STEAL:
            # Get the list of stealable players
            robber_pos = getattr(self.game.board, 'robber', None)
            if robber_pos:
                stealable_players = self._get_stealable_players(robber_pos[0], robber_pos[1])
                if stealable_players:
                    stealable_names = []
                    for pid in stealable_players:
                        name = self.users[pid].name if hasattr(self.users[pid], 'name') else f"Player {pid}"
                        stealable_names.append(f"{name} (id: {pid})")
                    
                    names_str = ", ".join(stealable_names)
                    return f"Choose a player to steal from: {names_str}. Use: steal <name_or_id>"
            
            return "Choose a player to steal from. Use: steal <name_or_id>"
        
        elif phase == TurnPhase.DISCARD_PHASE:
            # Find how many cards this player needs to discard
            players_must_discard = self._current_game_state.players_must_discard
            if self.current_player_id in players_must_discard:
                count = players_must_discard[self.current_player_id]
                return f"You must discard {count} cards. Use: drop <amount> <resource> ..."
            return "Waiting for other players to discard cards..."
        
        elif phase == TurnPhase.ROBBER_MOVE:
            return "Move the robber to a tile. Use: robber <tile_id> (click tiles in web view to see IDs)"
        
        elif phase == TurnPhase.ROLL_DICE:
            return "Roll the dice to start your turn. Use: roll"
        
        elif phase == TurnPhase.PLAYER_ACTIONS:
            return "Your turn - build, trade, or end turn. Type 'help' for commands."
        
        else:
            # Default message
            return f"Choose your action. Type 'help' for available commands."
    
    def __str__(self) -> str:
        """String representation of the GameManager."""
        status = "running" if self._is_running else "stopped"
        if self._is_paused:
            status = "paused"
        
        return f"GameManager(id={self.game_id[:8]}, players={self.num_players}, status={status})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the GameManager."""
        return (f"GameManager(game_id='{self.game_id}', "
                f"players={self.num_players}, "
                f"current_player={self.current_player_id}, "
                f"turn={self._current_game_state.turn_number}, "
                f"running={self._is_running}, "
                f"paused={self._is_paused})")