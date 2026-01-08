"""
AI User - Wrapper for AI Agents

This module provides AIUser, which implements the User interface
and delegates all decision-making to the AIManager.

AIUser is the bridge between GameManager and the AI system:
- GameManager sees AIUser as a regular User
- AIUser delegates to AIManager for actual decisions
- AIManager handles all AI logic (prompts, LLM, parsing)
"""

from typing import List, Optional, Dict, Any, TYPE_CHECKING
from pycatan.players.user import User
from pycatan.management.actions import Action, ActionType, GameState

if TYPE_CHECKING:
    from pycatan.ai.ai_manager import AIManager


class AIUser(User):
    """
    AI User implementation that wraps AIManager.
    
    This class implements the User interface expected by GameManager
    and delegates all AI-related work to the AIManager.
    
    Key responsibilities:
    - Translate GameState to dict for AIManager
    - Convert AI responses back to Action objects
    - Forward game events to AIManager
    """
    
    def __init__(
        self,
        name: str,
        user_id: int,
        ai_manager: 'AIManager',
        color: str = ""
    ):
        """
        Initialize an AI User.
        
        Args:
            name: Display name for this player
            user_id: Player ID (0-based)
            ai_manager: Reference to the shared AIManager
            color: Player color for display
        """
        super().__init__(name, user_id)
        self.ai_manager = ai_manager
        self.color = color
        
        # Register with AIManager
        ai_manager.register_agent(name, user_id, color)
    
    def get_input(
        self,
        game_state: GameState,
        prompt_message: str,
        allowed_actions: Optional[List[str]] = None
    ) -> Action:
        """
        Get action from AI agent.
        
        This is called by GameManager when it's this player's turn.
        
        Args:
            game_state: Current game state
            prompt_message: Context message from GameManager
            allowed_actions: List of allowed action type names
            
        Returns:
            Action object to execute
        """
        # Convert GameState to dict for AIManager
        state_dict = self._game_state_to_dict(game_state)
        
        # Process the turn (may send to LLM)
        decision = self.ai_manager.process_agent_turn(
            player_name=self.name,
            game_state=state_dict,
            prompt_message=prompt_message,
            allowed_actions=allowed_actions or []
        )
        
        # If manual actions mode, get input from human
        if self.ai_manager.manual_actions:
            action = self._get_manual_input(allowed_actions)
            return action
        else:
            # Auto mode - use LLM response directly
            return self._decision_to_action(decision)
    
    def _get_manual_input(self, allowed_actions: Optional[List[str]]) -> Action:
        """
        Get manual input from the human operator.
        
        Shows options and parses the human's input as the AI's action.
        If LLM suggestion is available, pressing Enter uses it.
        """
        print(f"\n>>> AI Turn for: {self.name}")
        if allowed_actions:
            formatted = [a.lower().replace("_", " ") for a in allowed_actions]
            print(f"    Allowed: {' | '.join(formatted)}")
        
        while True:
            try:
                user_input = input(f"    {self.name} (AI) > ").strip()
                
                # If empty and we have LLM suggestion, use it
                if not user_input:
                    llm_response = self.ai_manager._last_llm_response
                    if llm_response:
                        print(f"    [OK] Using LLM suggestion")
                        return self._decision_to_action(llm_response)
                    else:
                        print(f"    [!] No input and no LLM suggestion")
                        continue
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                # Parse the input
                decision = self.ai_manager.parse_manual_action(user_input)
                action = self._decision_to_action(decision)
                
                # Validate against allowed actions
                if allowed_actions and action.action_type.name not in allowed_actions:
                    print(f"    [X] '{action.action_type.name}' is not allowed right now.")
                    print(f"    Allowed: {allowed_actions}")
                    continue
                
                return action
                
            except ValueError as e:
                print(f"    [X] Error: {e}")
            except KeyboardInterrupt:
                print("\n    Game interrupted.")
                return Action(ActionType.END_TURN, self.user_id)
    
    def _show_help(self):
        """Show help for manual input."""
        print("""
    === Manual AI Input Help ===
    
    Format: <action_type> [parameters]
    
    Examples:
      roll_dice                           - Roll the dice
      end_turn                            - End your turn
      build_settlement {"node": 14}       - Build settlement at node 14
      build_road {"from": 14, "to": 15}   - Build road from node 14 to 15
      build_city {"node": 14}             - Upgrade settlement to city
      buy_dev_card                         - Buy a development card
      trade_bank {"give": "wheat", "receive": "ore"}
      robber_move {"hex": 5}              - Move robber to hex 5
      steal_card {"target_player": "Bob"} - Steal from Bob
      discard_cards {"cards": ["wood", "brick"]}
    
    Shortcuts:
      s 14           -> build_settlement {"node": 14}
      rd 14 15       -> build_road {"from": 14, "to": 15}
      r              -> roll_dice
      e              -> end_turn
        """)
    
    def _decision_to_action(self, decision: Dict[str, Any]) -> Action:
        """
        Convert AI decision dict to Action object.
        
        Args:
            decision: Dict with 'action_type' and 'parameters'
            
        Returns:
            Action object
        """
        action_type_str = decision.get("action_type", "end_turn")
        parameters = decision.get("parameters", {})
        
        # Map common action type strings to ActionType enum
        action_map = {
            "build_settlement": ActionType.BUILD_SETTLEMENT,
            "build_city": ActionType.BUILD_CITY,
            "build_road": ActionType.BUILD_ROAD,
            "roll_dice": ActionType.ROLL_DICE,
            "end_turn": ActionType.END_TURN,
            "buy_dev_card": ActionType.BUY_DEV_CARD,
            "use_dev_card": ActionType.USE_DEV_CARD,
            "trade_bank": ActionType.TRADE_BANK,
            "trade_propose": ActionType.TRADE_PROPOSE,
            "trade_accept": ActionType.TRADE_ACCEPT,
            "trade_reject": ActionType.TRADE_REJECT,
            "robber_move": ActionType.ROBBER_MOVE,
            "steal_card": ActionType.STEAL_CARD,
            "discard_cards": ActionType.DISCARD_CARDS,
            "place_starting_settlement": ActionType.PLACE_STARTING_SETTLEMENT,
            "place_starting_road": ActionType.PLACE_STARTING_ROAD,
            # Shortcuts
            "s": ActionType.BUILD_SETTLEMENT,
            "settlement": ActionType.BUILD_SETTLEMENT,
            "c": ActionType.BUILD_CITY,
            "city": ActionType.BUILD_CITY,
            "rd": ActionType.BUILD_ROAD,
            "road": ActionType.BUILD_ROAD,
            "r": ActionType.ROLL_DICE,
            "roll": ActionType.ROLL_DICE,
            "e": ActionType.END_TURN,
            "end": ActionType.END_TURN,
            "pass": ActionType.END_TURN,
            "dev": ActionType.BUY_DEV_CARD,
            "buy": ActionType.BUY_DEV_CARD,
        }
        
        # Handle setup phase shortcuts
        if action_type_str.lower() in ["s", "settlement", "build_settlement"]:
            # Could be either BUILD_SETTLEMENT or PLACE_STARTING_SETTLEMENT
            # This will be determined by GameManager validation
            pass
        
        action_type = action_map.get(action_type_str.lower())
        
        if action_type is None:
            # Try to find by enum name
            try:
                action_type = ActionType[action_type_str.upper()]
            except KeyError:
                print(f"    [!] Unknown action type: {action_type_str}, using END_TURN")
                action_type = ActionType.END_TURN
        
        # Convert parameters to expected format
        converted_params = self._convert_parameters(action_type, parameters)
        
        return Action(
            action_type=action_type,
            player_id=self.user_id,
            parameters=converted_params
        )
    
    def _convert_parameters(
        self,
        action_type: ActionType,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert AI parameters to GameManager expected format.
        
        Args:
            action_type: The action type
            parameters: Raw parameters from AI
            
        Returns:
            Converted parameters
        """
        # Map AI parameter names to GameManager names
        if action_type in [ActionType.BUILD_SETTLEMENT, ActionType.BUILD_CITY,
                          ActionType.PLACE_STARTING_SETTLEMENT]:
            # AI uses "node", GameManager uses "point_coords"
            if "node" in parameters:
                return {"point_coords": parameters["node"]}
            elif "point_coords" in parameters:
                return parameters
            else:
                return parameters
        
        elif action_type in [ActionType.BUILD_ROAD, ActionType.PLACE_STARTING_ROAD]:
            # AI uses "from"/"to", GameManager uses "start_coords"/"end_coords"
            result = {}
            if "from" in parameters:
                result["start_coords"] = parameters["from"]
            elif "start_coords" in parameters:
                result["start_coords"] = parameters["start_coords"]
            
            if "to" in parameters:
                result["end_coords"] = parameters["to"]
            elif "end_coords" in parameters:
                result["end_coords"] = parameters["end_coords"]
            
            return result
        
        elif action_type == ActionType.ROBBER_MOVE:
            # AI uses "hex", GameManager uses "tile_coords"
            if "hex" in parameters:
                return {"tile_coords": parameters["hex"]}
            elif "tile_coords" in parameters:
                return parameters
            else:
                return parameters
        
        elif action_type == ActionType.STEAL_CARD:
            # AI uses "target_player" or "victim"
            if "target_player" in parameters:
                return {"target_player": parameters["target_player"]}
            elif "victim" in parameters:
                return {"target_player": parameters["victim"]}
            else:
                return parameters
        
        elif action_type == ActionType.TRADE_BANK:
            # Keep give/receive format
            return parameters
        
        elif action_type == ActionType.USE_DEV_CARD:
            # Keep card_type
            return parameters
        
        elif action_type == ActionType.DISCARD_CARDS:
            # Keep cards list
            return parameters
        
        return parameters
    
    def _game_state_to_dict(self, game_state: GameState) -> Dict[str, Any]:
        """
        Convert GameState object to dictionary for AIManager.
        
        Args:
            game_state: GameState object
            
        Returns:
            Dictionary representation
        """
        # Basic conversion - can be enhanced
        return {
            "game_id": game_state.game_id,
            "turn_number": game_state.turn_number,
            "current_player": game_state.current_player,
            "game_phase": game_state.game_phase.name if hasattr(game_state.game_phase, 'name') else str(game_state.game_phase),
            "turn_phase": game_state.turn_phase.name if hasattr(game_state.turn_phase, 'name') else str(game_state.turn_phase),
            "dice_rolled": game_state.dice_rolled,
            "allowed_actions": game_state.allowed_actions,
            # Board state
            "board_state": {
                "tiles": game_state.board_state.tiles if hasattr(game_state.board_state, 'tiles') else [],
                "robber_position": game_state.board_state.robber_position if hasattr(game_state.board_state, 'robber_position') else None,
            } if game_state.board_state else {},
            # Players state
            "players_state": [
                {
                    "player_id": p.player_id,
                    "name": p.name,
                    "cards": p.cards,
                    "dev_cards": p.dev_cards,
                    "settlements": p.settlements,
                    "cities": p.cities,
                    "roads": p.roads,
                    "victory_points": p.victory_points,
                    "has_longest_road": p.has_longest_road,
                    "has_largest_army": p.has_largest_army,
                    "knights_played": p.knights_played
                }
                for p in game_state.players_state
            ] if game_state.players_state else []
        }
    
    def notify_game_event(
        self,
        event_type: str,
        message: str,
        affected_players: Optional[List[int]] = None
    ) -> None:
        """
        Notify about a game event.
        
        Called by GameManager to inform about dice rolls, builds, etc.
        
        Args:
            event_type: Type of event
            message: Human-readable description
            affected_players: List of affected player IDs
        """
        # Forward to AIManager for storage
        self.ai_manager.on_game_event(event_type, message, affected_players)
    
    def notify_action(self, action: Action, success: bool, message: str = "") -> None:
        """
        Notify about an action result.
        
        Args:
            action: The action that was performed
            success: Whether it succeeded
            message: Additional message
        """
        # Could be used for learning or logging
        if not success and message:
            print(f"    [!] Action failed: {message}")
    
    def __str__(self) -> str:
        return f"AIUser(name='{self.name}', id={self.user_id}, color='{self.color}')"
