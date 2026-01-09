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
from pycatan.ai.state_optimizer import game_state_to_dict, optimize_state_for_ai
from pycatan.config.board_definition import board_definition

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
            return self._decision_to_action(decision, allowed_actions)
    
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
                
                # Get LLM response (for memory/chat even if action is manual)
                llm_response = self.ai_manager._last_llm_response
                
                # If empty and we have LLM suggestion, use it
                if not user_input:
                    if llm_response:
                        print(f"    [OK] Using LLM suggestion")
                        # Save memory and chat from LLM response
                        self._save_llm_memory_and_chat(llm_response)
                        return self._decision_to_action(llm_response, allowed_actions)
                    else:
                        print(f"    [!] No input and no LLM suggestion")
                        continue
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                # Parse the input
                decision = self.ai_manager.parse_manual_action(user_input)
                action = self._decision_to_action(decision, allowed_actions)
                
                # Validate against allowed actions
                if allowed_actions and action.action_type.name not in allowed_actions:
                    print(f"    [X] '{action.action_type.name}' is not allowed right now.")
                    print(f"    Allowed: {allowed_actions}")
                    continue
                
                # Even with manual action, save LLM's memory and chat if available
                if llm_response:
                    self._save_llm_memory_and_chat(llm_response)
                
                return action
                
            except ValueError as e:
                print(f"    [X] Error: {e}")
            except KeyboardInterrupt:
                print("\n    Game interrupted.")
                return Action(ActionType.END_TURN, self.user_id)
    
    def _save_llm_memory_and_chat(self, llm_response: Dict[str, Any]) -> None:
        """
        Save memory and chat from LLM response to agent state.
        
        This ensures note_to_self and say_outloud are preserved even when
        the user provides a manual action override.
        """
        agent = self.ai_manager.get_agent(self.name)
        if not agent:
            return
        
        # Save note_to_self to agent memory
        note_to_self = llm_response.get("note_to_self")
        if note_to_self:
            agent.update_memory(note_to_self)
            # Save memories to file for web viewer
            self.ai_manager.logger.save_agent_memories(self.ai_manager.agents)
        
        # Broadcast say_outloud to chat
        say_outloud = llm_response.get("say_outloud")
        if say_outloud:
            self.ai_manager._broadcast_chat(self.name, say_outloud)
    
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
    
    def _decision_to_action(self, decision: Dict[str, Any], allowed_actions: Optional[List[str]] = None) -> Action:
        """
        Convert AI decision dict to Action object.
        
        Args:
            decision: Dict with 'action_type' and 'parameters'
            allowed_actions: List of allowed action type names (for auto-detection)
            
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
        
        # Auto-detect setup phase: if only PLACE_STARTING_SETTLEMENT is allowed, use it
        if action_type_str.lower() in ["s", "settlement", "build_settlement"]:
            if allowed_actions and "PLACE_STARTING_SETTLEMENT" in allowed_actions and "BUILD_SETTLEMENT" not in allowed_actions:
                action_type_str = "place_starting_settlement"
        
        # Auto-detect setup phase for roads
        if action_type_str.lower() in ["rd", "road", "build_road"]:
            if allowed_actions and "PLACE_STARTING_ROAD" in allowed_actions and "BUILD_ROAD" not in allowed_actions:
                action_type_str = "place_starting_road"
        
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
            # AI uses "node" (point ID), GameManager uses "point_coords" ([row, col])
            if "node" in parameters:
                node_id = parameters["node"]
                # Convert node ID to game coordinates
                coords = board_definition.point_id_to_game_coords(node_id)
                if coords is None:
                    # Invalid node ID - return as-is, GameManager will handle error
                    return {"point_coords": node_id}
                return {"point_coords": list(coords)}
            elif "point_coords" in parameters:
                return parameters
            else:
                return parameters
        
        elif action_type in [ActionType.BUILD_ROAD, ActionType.PLACE_STARTING_ROAD]:
            # AI uses "from"/"to" (node IDs), GameManager uses "start_coords"/"end_coords" ([row, col])
            result = {}
            if "from" in parameters:
                from_id = parameters["from"]
                coords = board_definition.point_id_to_game_coords(from_id)
                result["start_coords"] = list(coords) if coords else from_id
            elif "start_coords" in parameters:
                result["start_coords"] = parameters["start_coords"]
            
            if "to" in parameters:
                to_id = parameters["to"]
                coords = board_definition.point_id_to_game_coords(to_id)
                result["end_coords"] = list(coords) if coords else to_id
            elif "end_coords" in parameters:
                result["end_coords"] = parameters["end_coords"]
            
            return result
        
        elif action_type == ActionType.ROBBER_MOVE:
            # AI uses "hex" (hex ID), GameManager uses "tile_coords" ([row, col])
            if "hex" in parameters:
                hex_id = parameters["hex"]
                coords = board_definition.hex_id_to_game_coords(hex_id)
                return {"tile_coords": list(coords) if coords else hex_id}
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
        Convert GameState object to optimized compact dictionary for AIManager.
        
        Uses game_state_to_dict to convert to captured_game.json format,
        then optimize_state_for_ai to create compact format.
        
        Args:
            game_state: GameState object
            
        Returns:
            Optimized compact state dictionary (H, N, state, players, meta)
        """
        # Step 1: Convert GameState to captured_game.json format
        verbose_state = game_state_to_dict(game_state)
        
        # Step 2: Optimize to compact format
        optimized_state = optimize_state_for_ai(verbose_state)
        
        return optimized_state
    
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
