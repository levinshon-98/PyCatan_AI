"""
AI User - Wrapper for AI Agents

This module provides AIUser, which implements the User interface
and delegates all decision-making to the AIManager.

AIUser is the bridge between GameManager and the AI system:
- GameManager sees AIUser as a regular User
- AIUser delegates to AIManager for actual decisions
- AIManager handles all AI logic (prompts, LLM, parsing)
"""

from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union
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
        
        # Process the turn (may send to LLM). The per-agent lock prevents an
        # async social reaction for this same player from overlapping their
        # actual turn prompt.
        with self.ai_manager.get_agent_request_lock(self.name):
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
        Save memory from an LLM response to agent state.
        
        Active-turn say_outloud is intentionally not broadcast here: it is
        attached to the eventual Action and only spoken after that action
        succeeds.
        """
        agent = self.ai_manager.get_agent(self.name)
        if not agent:
            return
        
        # Save note_to_self to agent memory
        note_to_self = llm_response.get("note_to_self")
        if note_to_self:
            agent.update_memory(note_to_self)
            self.ai_manager._maybe_compact_agent_memory(agent)
            # Save memories to file for web viewer
            self.ai_manager.logger.save_agent_memories(self.ai_manager.agents)

    def _show_help(self):
        """Show help for manual input."""
        print("""
    === Manual AI Input Help ===
    
    Format: <action_type> [parameters]
    
    Examples:
      roll_dice                           - Roll the dice
      end_turn                            - End your turn
      end_game                            - Leave the post-game conversation
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
            "end_game": ActionType.END_GAME,
            "wait_for_response": ActionType.END_TURN,
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
                allowed_display = f" Allowed actions: {allowed_actions}" if allowed_actions else ""
                raise ValueError(f"Unknown action type: {action_type_str}.{allowed_display}")
        
        # Convert parameters to expected format
        converted_params = self._convert_parameters(action_type, parameters)
        if "say_outloud" in decision and decision.get("say_outloud") is not None:
            converted_params["_ai_say_outloud"] = str(decision.get("say_outloud") or "")
        
        return Action(
            action_type=action_type,
            player_id=self.user_id,
            parameters=converted_params
        )

    def react_to_game_event(
        self,
        game_state: GameState,
        prompt_message: str,
        source_player: Optional[str] = None,
        event_group_id: Optional[str] = None
    ) -> None:
        """
        Give this AI a no-board-action opportunity to react socially.

        The GameManager passes the real current GameState here, so reactions use
        the same filtered/compact board view as normal turns.
        """
        state_dict = self._game_state_to_dict(game_state)
        self.ai_manager.process_agent_reaction(
            player_name=self.name,
            game_state=state_dict,
            prompt_message=prompt_message,
            source_player=source_player,
            event_group_id=event_group_id,
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
            result = {}
            if "hex" in parameters:
                hex_id = parameters["hex"]
                coords = board_definition.hex_id_to_game_coords(hex_id)
                result["tile_coords"] = list(coords) if coords else hex_id
            elif "tile_coords" in parameters:
                result["tile_coords"] = parameters["tile_coords"]
            if parameters.get("confirm_self_block") is True:
                result["confirm_self_block"] = True
            return result or parameters
        
        elif action_type == ActionType.STEAL_CARD:
            # AI uses "target_player" or "victim"
            if "target_player" in parameters:
                return {"target_player": self._resolve_player_identifier(parameters["target_player"])}
            elif "victim" in parameters:
                return {"target_player": self._resolve_player_identifier(parameters["victim"])}
            else:
                return parameters

        elif action_type == ActionType.TRADE_PROPOSE:
            result = dict(parameters)
            for key in ("target_player", "target", "to", "player"):
                if key in result:
                    result["target_player"] = self._resolve_player_identifier(result.pop(key))
                    break
            if "offer" in result:
                result["offer"] = self._normalize_resource_bundle(result["offer"])
            if "request" in result:
                result["request"] = self._normalize_resource_bundle(result["request"])
            return result
        
        elif action_type == ActionType.TRADE_BANK:
            if "give" in parameters or "receive" in parameters:
                offer_resource = self._normalize_resource_name(parameters.get("give"))
                request_resource = self._normalize_resource_name(parameters.get("receive"))
                offer_amount = int(parameters.get("give_amount", parameters.get("amount", 4)))
                request_amount = int(parameters.get("receive_amount", 1))
                result = {}
                if offer_resource:
                    result["offer"] = {offer_resource: offer_amount}
                if request_resource:
                    result["request"] = {request_resource: request_amount}
                return result
            result = dict(parameters)
            if "offer" in result:
                result["offer"] = self._normalize_resource_bundle(result["offer"])
            if "request" in result:
                result["request"] = self._normalize_resource_bundle(result["request"])
            return result
        
        elif action_type == ActionType.USE_DEV_CARD:
            return self._normalize_dev_card_parameters(parameters)
        
        elif action_type == ActionType.DISCARD_CARDS:
            # Keep cards list
            return parameters
        
        return parameters

    def _normalize_dev_card_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize AI-facing development-card params to GameManager format."""
        result = dict(parameters)

        card_type = self._normalize_dev_card_name(result.get("card_type") or result.get("card"))
        if card_type:
            result["card_type"] = card_type

        if card_type == "Road":
            road_one = result.pop("road_1", None) or result.pop("road_one", None)
            road_two = result.pop("road_2", None) or result.pop("road_two", None)
            roads = result.pop("roads", None)
            if roads and isinstance(roads, list):
                if len(roads) > 0 and road_one is None:
                    road_one = roads[0]
                if len(roads) > 1 and road_two is None:
                    road_two = roads[1]

            if road_one is not None:
                result["road_one_coords"] = self._road_param_to_coords(road_one)
            if road_two is not None:
                result["road_two_coords"] = self._road_param_to_coords(road_two)

        elif card_type == "Knight":
            if "hex" in result and "tile_coords" not in result:
                coords = board_definition.hex_id_to_game_coords(result.pop("hex"))
                if coords:
                    result["tile_coords"] = list(coords)
            for key in ("target_player", "victim", "steal_from"):
                if key in result and "victim_id" not in result:
                    result["victim_id"] = self._resolve_player_identifier(result.pop(key))
                    break

        elif card_type == "Monopoly":
            resource = (
                result.get("resource_type")
                or result.get("resource")
                or result.get("target_resource")
            )
            normalized = self._normalize_resource_name(resource)
            if normalized:
                result["resource_type"] = normalized.title()

        elif card_type == "YearOfPlenty":
            resources = result.pop("resources", None)
            if isinstance(resources, list):
                if len(resources) > 0 and "resource1" not in result:
                    result["resource1"] = resources[0]
                if len(resources) > 1 and "resource2" not in result:
                    result["resource2"] = resources[1]

            for key in ("resource1", "resource2"):
                normalized = self._normalize_resource_name(result.get(key))
                if normalized:
                    result[key] = normalized.title()

        return result

    def _normalize_dev_card_name(self, card_type: Any) -> Optional[str]:
        """Accept prompt-facing and natural dev-card names."""
        if card_type is None:
            return None

        key = str(card_type).strip().lower().replace("-", "_").replace(" ", "_")
        mapping = {
            "k": "Knight",
            "knight": "Knight",
            "road": "Road",
            "road_building": "Road",
            "roadbuilding": "Road",
            "roads": "Road",
            "monopoly": "Monopoly",
            "year": "YearOfPlenty",
            "plenty": "YearOfPlenty",
            "year_of_plenty": "YearOfPlenty",
            "yearofplenty": "YearOfPlenty",
            "victory": "VictoryPoint",
            "victory_point": "VictoryPoint",
            "victorypoint": "VictoryPoint",
        }
        return mapping.get(key, str(card_type))

    def _road_param_to_coords(self, road: Any) -> Dict[str, Any]:
        """Convert AI road references like [45, 35] to GameManager coord dicts."""
        start_node = None
        end_node = None

        if isinstance(road, dict):
            start_node = road.get("from") or road.get("start") or road.get("start_node")
            end_node = road.get("to") or road.get("end") or road.get("end_node")
        elif isinstance(road, (list, tuple)) and len(road) >= 2:
            start_node, end_node = road[0], road[1]

        def convert(node: Any) -> Any:
            if isinstance(node, (list, tuple)) and len(node) == 2:
                return list(node)
            coords = board_definition.point_id_to_game_coords(node)
            return list(coords) if coords else node

        return {
            "start": convert(start_node),
            "end": convert(end_node),
        }

    def _normalize_resource_bundle(self, resources: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize AI-facing resource keys to engine-facing lowercase names."""
        if not isinstance(resources, dict):
            return resources

        normalized: Dict[str, Any] = {}
        for resource, amount in resources.items():
            resource_name = self._normalize_resource_name(resource)
            if not resource_name:
                resource_name = str(resource).lower()
            normalized[resource_name] = normalized.get(resource_name, 0) + int(amount)
        return normalized

    def _normalize_resource_name(self, resource: Any) -> Optional[str]:
        """Accept compact prompt codes and natural names for resources."""
        if resource is None:
            return None

        key = str(resource).strip().lower()
        mapping = {
            "w": "wood",
            "wood": "wood",
            "lumber": "wood",
            "b": "brick",
            "brick": "brick",
            "s": "sheep",
            "sheep": "sheep",
            "wool": "sheep",
            "wh": "wheat",
            "wheat": "wheat",
            "grain": "wheat",
            "o": "ore",
            "ore": "ore",
            "stone": "ore",
        }
        return mapping.get(key)

    def _resolve_player_identifier(self, value: Union[int, str]) -> int:
        """
        Resolve an AI-facing player identifier to the numeric player id expected
        by GameManager.

        The LLM is often prompted with human names/colors, while the engine uses
        zero-based ids. Accept both to keep prompts natural and actions valid.
        """
        if isinstance(value, int):
            return value

        if isinstance(value, str):
            raw = value.strip()
            if raw.isdigit():
                return int(raw)

            normalized = raw.lower()
            if normalized.startswith("player "):
                suffix = normalized.replace("player ", "", 1).strip()
                if suffix.isdigit():
                    return int(suffix) - 1

            for agent in self.ai_manager.agents.values():
                if agent.player_name.lower() == normalized:
                    return agent.player_id
                if agent.player_color and agent.player_color.lower() == normalized:
                    return agent.player_id

        print(f"    [!] Unknown player identifier for target_player: {value!r}")
        return -1
    
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
    
    def notify_action(self, action: Optional[Action], success: bool, message: str = "") -> None:
        """
        Notify about an action result.
        
        Args:
            action: The action that was performed
            success: Whether it succeeded
            message: Additional message
        """
        action_player_id = getattr(action, "player_id", None)
        action_parameters = getattr(action, "parameters", {})

        if success:
            if action_player_id != self.user_id:
                return
            say_outloud = ""
            if isinstance(action_parameters, dict):
                if action_parameters.get("_ai_say_outloud_public"):
                    return
                say_outloud = (action_parameters.get("_ai_say_outloud") or "").strip()
            if say_outloud:
                self.ai_manager._broadcast_chat(self.name, say_outloud)
                if isinstance(action_parameters, dict):
                    action_parameters["_ai_say_outloud_public"] = True
            return

        if message:
            print(f"    [!] Action failed: {message}")
            agent = self.ai_manager.get_agent(self.name)
            if agent:
                action_type = getattr(action, "action_type", None)
                action_name = action_type.name if hasattr(action_type, "name") else str(action_type)
                if str(message).startswith("ARE YOU SURE?"):
                    agent.add_event(
                        "action_failed",
                        message,
                        {
                            "action_type": action_name,
                            "parameters": action_parameters,
                            "confirmation_required": True,
                        },
                    )
                    return
                speech_note = "The say_outloud from that failed attempt was not said publicly; choose a new legal action."
                if isinstance(action_parameters, dict) and action_parameters.get("_ai_say_outloud_public"):
                    speech_note = "Your say_outloud was already said publicly; choose a new legal action."
                agent.add_event(
                    "action_failed",
                    (
                        f"Your previous action failed: {action_name} {action_parameters}. Error: {message}. "
                        f"{speech_note}"
                    ),
                    {
                        "action_type": action_name,
                        "parameters": action_parameters,
                        "error": message,
                    }
                )

    def notify_action_processing_error(
        self,
        message: str,
        decision: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Notify the agent about a failure that happened before an Action object
        could be created, such as missing required parameters.
        """
        print(f"    [!] Action processing failed: {message}")
        agent = self.ai_manager.get_agent(self.name)
        if not agent:
            return

        agent.add_event(
            "action_failed",
            f"Your previous action could not be processed. Error: {message}. "
            "Correct the action type and required parameters before trying again.",
            {
                "error": message,
                "decision": decision or {},
            }
        )

    def notify_trade_offer(
        self,
        trade_id: str,
        proposer: str,
        target: str,
        offer: Dict[str, Any],
        request: Dict[str, Any]
    ) -> None:
        """Forward structured trade offer information to the shared AI manager."""
        self.ai_manager.record_trade_offer(trade_id, proposer, target, offer, request)

    def notify_invalid_trade_attempt(
        self,
        proposer: str,
        target: str,
        offer: Dict[str, Any],
        request: Dict[str, Any],
        reason: str
    ) -> None:
        """
        Record a private event when someone tried to trade with this player
        but the trade was not legally possible.
        """
        agent = self.ai_manager.get_agent(self.name)
        if not agent:
            return

        offer_text = self._format_resource_bundle(offer)
        request_text = self._format_resource_bundle(request)
        agent.add_event(
            "trade_attempt_failed",
            (
                f"{proposer} tried to propose a trade to you: "
                f"[{offer_text}] for [{request_text}], but {reason}. "
                "No trade is pending; you do not need to accept or reject it."
            ),
            {
                "proposer": proposer,
                "target": target,
                "offer": offer,
                "request": request,
                "reason": reason,
            }
        )

    def notify_trade_response(self, trade_id: str, status: str, responder: str) -> None:
        """Forward structured trade response information to the shared AI manager."""
        self.ai_manager.record_trade_response(trade_id, status, responder)

    def _format_resource_bundle(self, resources: Dict[str, Any]) -> str:
        """Format a resource-count dict for private event messages."""
        if not resources:
            return "nothing"
        return ", ".join(f"{amount}x {resource}" for resource, amount in resources.items())
    
    def __str__(self) -> str:
        return f"AIUser(name='{self.name}', id={self.user_id}, color='{self.color}')"
