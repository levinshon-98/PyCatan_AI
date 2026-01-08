"""
AI Manager - Central Coordinator for AI Agents

This is the main orchestrator for all AI agent activities:
- Manages agent state and lifecycle
- Creates and sends prompts
- Processes responses from LLM
- Handles chat and game events
- Coordinates with the logging system

The AIManager bridges between GameManager (through AIUser) and the LLM.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

from pycatan.ai.config import AIConfig
from pycatan.ai.prompt_manager import PromptManager
from pycatan.ai.llm_client import LLMResponse, create_llm_client, GeminiClient
from pycatan.ai.response_parser import ResponseParser, ParseResult
from pycatan.ai.schemas import ResponseType, ACTIVE_TURN_RESPONSE_SCHEMA, OBSERVING_RESPONSE_SCHEMA
from pycatan.ai.agent_state import AgentState, compute_state_hash
from pycatan.ai.ai_logger import AILogger
from pycatan.management.actions import Action, ActionType


class AIManager:
    """
    Central manager for all AI agents in a game.
    
    Responsibilities:
    - Register and manage AI agents
    - Create prompts from game state
    - Send prompts to LLM
    - Parse and validate responses
    - Track agent memory and events
    - Log all interactions
    
    The AIManager does NOT know about game rules - it only
    transforms game state into prompts and responses into actions.
    """
    
    def __init__(
        self,
        config: Optional[AIConfig] = None,
        session_dir: Optional[Path] = None,
        auto_send_to_llm: bool = False,
        send_to_llm: bool = True,
        manual_actions: bool = True
    ):
        """
        Initialize the AI Manager.
        
        Args:
            config: AI configuration (uses defaults if None)
            session_dir: Directory for logging (auto-creates if None)
            auto_send_to_llm: DEPRECATED - use send_to_llm + manual_actions
            send_to_llm: If True, sends prompts to LLM and shows response
            manual_actions: If True, user enters actions manually (even if LLM responds)
        """
        self.config = config or AIConfig()
        self.send_to_llm = send_to_llm
        self.manual_actions = manual_actions
        # Legacy support
        if auto_send_to_llm:
            self.send_to_llm = True
            self.manual_actions = False
        
        # Core components
        self.prompt_manager = PromptManager(self.config)
        self.response_parser = ResponseParser()
        self.logger = AILogger(session_dir=session_dir)
        
        # LLM client (created lazily when needed)
        self._llm_client: Optional[GeminiClient] = None
        
        # Agent state management
        self.agents: Dict[str, AgentState] = {}
        
        # Chat history (shared between all agents)
        self.chat_history: List[Dict[str, Any]] = []
        self.max_chat_history: int = 20
        
        # Current game state (updated by AIUser)
        self._current_game_state: Optional[Dict[str, Any]] = None
        self._current_allowed_actions: Optional[List[str]] = None
        
        # Callback for manual input (when manual_actions is True)
        self._input_callback: Optional[Callable[[str, Dict], str]] = None
        
        # Last LLM response (for display)
        self._last_llm_response: Optional[Dict[str, Any]] = None
        
        print(f"[AI] AIManager initialized")
        print(f"   Session: {self.logger.get_session_path()}")
        print(f"   Send to LLM: {self.send_to_llm}")
        print(f"   Manual actions: {self.manual_actions}")
    
    @property
    def llm_client(self) -> GeminiClient:
        """Get or create the LLM client."""
        if self._llm_client is None:
            api_key = self._get_api_key()
            self._llm_client = create_llm_client(
                provider=self.config.llm.provider,
                model=self.config.llm.model_name,
                api_key=api_key,
                temperature=self.config.llm.temperature,
                max_tokens=self.config.llm.max_tokens
            )
        return self._llm_client
    
    def _get_api_key(self) -> str:
        """Get API key from environment."""
        import os
        key = os.environ.get(self.config.llm.api_key_env_var, "")
        if not key:
            raise ValueError(
                f"API key not found! Set environment variable: {self.config.llm.api_key_env_var}"
            )
        return key
    
    # === Agent Management ===
    
    def register_agent(
        self,
        player_name: str,
        player_id: int,
        player_color: str = ""
    ) -> AgentState:
        """
        Register a new AI agent.
        
        Args:
            player_name: Display name for the player
            player_id: Player ID (0-based)
            player_color: Color assigned to player
            
        Returns:
            The created AgentState
        """
        if player_name in self.agents:
            print(f"[!] Agent '{player_name}' already registered, updating...")
        
        agent = AgentState(
            player_name=player_name,
            player_id=player_id,
            player_color=player_color
        )
        self.agents[player_name] = agent
        
        print(f"[AI] Registered AI agent: {player_name} (ID: {player_id}, Color: {player_color})")
        return agent
    
    def get_agent(self, player_name: str) -> Optional[AgentState]:
        """Get agent state by name."""
        return self.agents.get(player_name)
    
    def unregister_agent(self, player_name: str) -> None:
        """Remove an agent."""
        if player_name in self.agents:
            del self.agents[player_name]
            print(f"[AI] Unregistered agent: {player_name}")
    
    # === Core Processing ===
    
    def process_agent_turn(
        self,
        player_name: str,
        game_state: Dict[str, Any],
        prompt_message: str,
        allowed_actions: List[str]
    ) -> Dict[str, Any]:
        """
        Process an agent's turn.
        
        This is the main entry point called by AIUser.get_input().
        
        Args:
            player_name: Name of the agent
            game_state: Current game state
            prompt_message: Prompt from GameManager
            allowed_actions: List of allowed action types
            
        Returns:
            Dictionary with the agent's decision:
            {
                "action_type": str,
                "parameters": dict,
                "thinking": str,
                "note_to_self": str,
                "say_outloud": str
            }
        """
        agent = self.get_agent(player_name)
        if not agent:
            raise ValueError(f"Agent '{player_name}' not registered!")
        
        # Update current state
        self._current_game_state = game_state
        self._current_allowed_actions = allowed_actions
        
        # Build "what happened" from recent events
        what_happened = self._build_what_happened(agent)
        
        # Create prompt
        prompt, schema = self._create_prompt(
            agent=agent,
            game_state=game_state,
            what_happened=what_happened,
            allowed_actions=allowed_actions,
            is_active_turn=True
        )
        
        # Log the prompt
        log_info = self.logger.log_prompt(
            player_name=player_name,
            prompt=prompt,
            schema=schema,
            is_active=True,
            what_happened=what_happened,
            allowed_actions=self._format_allowed_actions(allowed_actions)
        )
        
        # Mark request sent
        agent.mark_request_sent()
        
        # Send to LLM if enabled
        response = None
        llm_suggestion = None
        
        if self.send_to_llm:
            try:
                self.logger.log_llm_communication(f"Sending prompt #{log_info['number']} for {player_name}", "SEND")
                response = self._send_to_llm(prompt, schema, ResponseType.ACTIVE_TURN)
                
                if response and response.success and response.content:
                    self.logger.log_llm_communication(f"Received response for {player_name} ({response.total_tokens} tokens)", "RECV")
                    llm_suggestion = self._parse_response(response, ResponseType.ACTIVE_TURN)
                    self._last_llm_response = llm_suggestion
                    
                    # Log the action suggestion with details
                    if llm_suggestion:
                        action = llm_suggestion.get("action_type", "unknown")
                        params = llm_suggestion.get("parameters", {})
                        thinking = llm_suggestion.get("internal_thinking", "")[:100]
                        self.logger.log_llm_communication(f"LLM suggests: {action} {params}", "RECV")
                        if thinking:
                            self.logger.log_llm_communication(f"  Thinking: {thinking}...", "RECV")
                else:
                    error_msg = response.error if response else "No response"
                    self.logger.log_llm_communication(f"LLM error: {error_msg}", "ERROR")
                
                # Log response
                self.logger.log_response(
                    player_name=player_name,
                    request_number=log_info["number"],
                    response=response,
                    parsed=llm_suggestion
                )
                
                # LLM suggestion logged to communication log only
                
            except Exception as e:
                self.logger.log_llm_communication(f"Exception: {str(e)}", "ERROR")
                llm_suggestion = None
        
        # Get final action
        if self.manual_actions:
            # Manual mode - show info and wait for human input
            parsed = self._wait_for_manual_input(agent, prompt, log_info["number"], llm_suggestion)
        else:
            # Auto mode - use LLM response directly
            parsed = llm_suggestion
        
        # Update agent state
        agent.mark_request_complete(
            success=parsed is not None,
            tokens=response.total_tokens if response else 0
        )
        
        if parsed:
            # Update memory
            agent.update_memory(parsed.get("note_to_self"))
            
            # Clear events since they've been processed
            agent.clear_events()
            
            # Handle chat message if present
            if parsed.get("say_outloud"):
                self._broadcast_chat(player_name, parsed["say_outloud"])
        
        return parsed or {"action_type": "end_turn", "parameters": {}}
    
    def _display_llm_response(
        self,
        agent: AgentState,
        response: Dict[str, Any],
        request_number: int
    ):
        """Display the LLM response - minimal in main console, details in log file."""
        # All LLM communication goes to LLM Logger Console only
        pass
    
    def _wait_for_manual_input(
        self,
        agent: AgentState,
        prompt: Dict[str, Any],
        request_number: int,
        llm_suggestion: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Wait for manual input from terminal.
        
        In manual mode, we:
        1. Display the prompt info (and LLM suggestion if available)
        2. Wait for human to input the agent's decision
        3. Parse and return the response
        """
        # If we have LLM suggestion, show minimal hint
        if llm_suggestion:
            print("[TIP] LLM suggestion available. Press ENTER to accept, or type your own command")
        
        # Store suggestion for later use
        self._last_llm_response = llm_suggestion
        return None
    
    def parse_manual_action(self, input_str: str) -> Dict[str, Any]:
        """
        Parse a manual action input string.
        
        Supports both full format and shortcuts:
        - Full: build_settlement {"node": 14}
        - Shortcut: s 14 (settlement at node 14)
        - Shortcut: rd 14 15 (road from 14 to 15)
        
        Args:
            input_str: String like "build_settlement {\"node\": 14}" or "s 14"
            
        Returns:
            Parsed action dict
        """
        parts = input_str.strip().split()
        
        if not parts:
            return {"action_type": "end_turn", "parameters": {}}
        
        action_type = parts[0].lower()
        parameters = {}
        
        # Handle shortcuts with simple numeric parameters
        shortcut_map = {
            "s": ("build_settlement", "node"),
            "settlement": ("build_settlement", "node"),
            "c": ("build_city", "node"),
            "city": ("build_city", "node"),
            "r": ("roll_dice", None),
            "roll": ("roll_dice", None),
            "e": ("end_turn", None),
            "end": ("end_turn", None),
            "pass": ("end_turn", None),
            "dev": ("buy_dev_card", None),
            "buy": ("buy_dev_card", None),
        }
        
        # Handle road shortcut: rd 14 15
        if action_type == "rd" and len(parts) >= 3:
            try:
                return {
                    "action_type": "build_road",
                    "parameters": {"from": int(parts[1]), "to": int(parts[2])},
                    "internal_thinking": "(Manual input)",
                    "note_to_self": None,
                    "say_outloud": None
                }
            except ValueError:
                pass
        
        # Handle simple shortcuts
        if action_type in shortcut_map:
            full_action, param_name = shortcut_map[action_type]
            action_type = full_action
            if param_name and len(parts) > 1:
                try:
                    parameters[param_name] = int(parts[1])
                except ValueError:
                    parameters[param_name] = parts[1]
        
        # Handle JSON parameters
        elif len(parts) > 1:
            # Try to parse as JSON
            param_str = " ".join(parts[1:])
            try:
                parameters = json.loads(param_str)
            except json.JSONDecodeError:
                # Try simple key=value format
                if "=" in param_str:
                    for kv in param_str.split():
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            try:
                                parameters[k] = int(v)
                            except ValueError:
                                parameters[k] = v
                else:
                    # Just a single value, assume it's "node" for settlements
                    try:
                        parameters["node"] = int(parts[1])
                    except ValueError:
                        pass
        
        return {
            "action_type": action_type,
            "parameters": parameters,
            "internal_thinking": "(Manual input)",
            "note_to_self": None,
            "say_outloud": None
        }
    
    def _create_prompt(
        self,
        agent: AgentState,
        game_state: Dict[str, Any],
        what_happened: str,
        allowed_actions: List[str],
        is_active_turn: bool
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Create a prompt for an agent.
        
        Returns:
            Tuple of (prompt_dict, schema_dict)
        """
        # Format allowed actions
        formatted_actions = self._format_allowed_actions(allowed_actions)
        
        # Get agent's memory
        agent_memory = None
        if agent.memory:
            agent_memory = {"note_from_last_turn": agent.memory}
        
        # Create prompt through PromptManager
        prompt = self.prompt_manager.create_prompt(
            player_num=agent.player_id,
            player_name=agent.player_name,
            player_color=agent.player_color,
            game_state=game_state,
            what_happened=what_happened,
            available_actions=formatted_actions,
            chat_history=self.chat_history[-self.max_chat_history:] if self.chat_history else None,
            agent_memory=agent_memory
        )
        
        # Get appropriate schema
        if is_active_turn:
            schema = ACTIVE_TURN_RESPONSE_SCHEMA
        else:
            schema = OBSERVING_RESPONSE_SCHEMA
        
        return prompt, schema
    
    def _format_allowed_actions(self, allowed_actions: List[str]) -> List[Dict[str, Any]]:
        """Convert action type strings to formatted action dicts."""
        # Map action type names to example parameters
        action_templates = {
            "BUILD_SETTLEMENT": {
                "type": "build_settlement",
                "description": "Build a settlement at a node",
                "example_parameters": "{\"node\": 14}"
            },
            "BUILD_CITY": {
                "type": "build_city",
                "description": "Upgrade a settlement to a city",
                "example_parameters": "{\"node\": 14}"
            },
            "BUILD_ROAD": {
                "type": "build_road",
                "description": "Build a road between two nodes",
                "example_parameters": "{\"from\": 14, \"to\": 15}"
            },
            "ROLL_DICE": {
                "type": "roll_dice",
                "description": "Roll the dice",
                "example_parameters": "{}"
            },
            "END_TURN": {
                "type": "end_turn",
                "description": "End your turn",
                "example_parameters": "{}"
            },
            "BUY_DEV_CARD": {
                "type": "buy_dev_card",
                "description": "Buy a development card",
                "example_parameters": "{}"
            },
            "USE_DEV_CARD": {
                "type": "use_dev_card",
                "description": "Play a development card",
                "example_parameters": "{\"card_type\": \"knight\"}"
            },
            "TRADE_BANK": {
                "type": "trade_bank",
                "description": "Trade resources with the bank",
                "example_parameters": "{\"give\": \"wood\", \"receive\": \"brick\"}"
            },
            "TRADE_PROPOSE": {
                "type": "trade_propose",
                "description": "Propose a trade to other players",
                "example_parameters": "{\"offer\": {\"wood\": 1}, \"request\": {\"brick\": 1}}"
            },
            "ROBBER_MOVE": {
                "type": "robber_move",
                "description": "Move the robber to a hex",
                "example_parameters": "{\"hex\": 7}"
            },
            "STEAL_CARD": {
                "type": "steal_card",
                "description": "Steal a card from a player",
                "example_parameters": "{\"target_player\": \"Red\"}"
            },
            "DISCARD_CARDS": {
                "type": "discard_cards",
                "description": "Discard cards (when 7 is rolled)",
                "example_parameters": "{\"cards\": [\"wood\", \"brick\"]}"
            },
            "PLACE_STARTING_SETTLEMENT": {
                "type": "place_starting_settlement",
                "description": "Place your starting settlement",
                "example_parameters": "{\"node\": 14}"
            },
            "PLACE_STARTING_ROAD": {
                "type": "place_starting_road",
                "description": "Place your starting road",
                "example_parameters": "{\"from\": 14, \"to\": 15}"
            },
            "WAIT_FOR_RESPONSE": {
                "type": "wait_for_response",
                "description": "Do nothing on the board, just wait or communicate. Use this when you want to talk, negotiate, or think without taking a game action.",
                "example_parameters": "{}"
            }
        }
        
        result = []
        for action_name in allowed_actions:
            if action_name in action_templates:
                result.append(action_templates[action_name])
            else:
                # Unknown action - create basic template
                result.append({
                    "type": action_name.lower(),
                    "description": action_name.replace("_", " ").title(),
                    "example_parameters": {}
                })
        
        # Always add WAIT_FOR_RESPONSE as an option (for communication)
        if "WAIT_FOR_RESPONSE" not in allowed_actions:
            result.append(action_templates["WAIT_FOR_RESPONSE"])
        
        return result
    
    def _build_what_happened(self, agent: AgentState) -> str:
        """
        Build the 'what happened' message from recent events.
        
        Args:
            agent: The agent to build message for
            
        Returns:
            Human-readable summary of recent events
        """
        if not agent.recent_events:
            return "Game is starting."
        
        lines = []
        for event in agent.recent_events:
            lines.append(f"• {event['message']}")
        
        return "\n".join(lines)
    
    def _send_to_llm(
        self,
        prompt: Dict[str, Any],
        schema: Dict[str, Any],
        response_type: ResponseType
    ) -> LLMResponse:
        """Send prompt to LLM and get response."""
        # Convert prompt to string
        prompt_str = json.dumps(prompt, indent=2, ensure_ascii=False)
        
        # Send to LLM with schema and thinking mode (if enabled)
        kwargs = {
            "response_schema": schema,
            "enable_thinking": self.config.llm.enable_thinking,
        }
        
        if self.config.llm.enable_thinking:
            kwargs["thinking_budget"] = self.config.llm.thinking_budget
        
        response = self.llm_client.generate(
            prompt_str,
            **kwargs
        )
        
        return response
    
    def _parse_response(
        self,
        response: LLMResponse,
        response_type: ResponseType
    ) -> Optional[Dict[str, Any]]:
        """Parse LLM response into structured data."""
        if not response.success or not response.content:
            return None
        
        result = self.response_parser.parse(
            response.content,
            response_type
        )
        
        if result.success and result.data:
            # Convert schema format to internal format
            data = result.data
            parsed = {
                "internal_thinking": data.get("internal_thinking", ""),
                "note_to_self": data.get("note_to_self"),
                "say_outloud": data.get("say_outloud"),
            }
            
            # Extract action (action.type + action.parameters)
            action = data.get("action", {})
            if action:
                parsed["action_type"] = action.get("type", "end_turn")
                # Parameters might be JSON string or dict
                params = action.get("parameters", {})
                if isinstance(params, str):
                    try:
                        params = json.loads(params) if params else {}
                    except json.JSONDecodeError:
                        params = {}
                parsed["parameters"] = params if params else {}
            else:
                parsed["action_type"] = "end_turn"
                parsed["parameters"] = {}
            
            # Log detailed response
            self.logger.log_llm_communication(
                f"Thinking: {parsed['internal_thinking'][:100]}...",
                "RECV"
            )
            
            return parsed
        else:
            print(f"[!] Parse error: {result.error_message}")
            return None
    
    # === Event Handling ===
    
    def on_game_event(
        self,
        event_type: str,
        message: str,
        affected_players: Optional[List[int]] = None
    ) -> None:
        """
        Handle a game event notification.
        
        Called by AIUser.notify_game_event().
        Stores the event for all relevant agents.
        
        Args:
            event_type: Type of event
            message: Human-readable description
            affected_players: List of affected player IDs
        """
        for agent_name, agent in self.agents.items():
            # Add event to all agents (they all see what happens)
            agent.add_event(event_type, message)
    
    def _broadcast_chat(self, from_player: str, message: str) -> None:
        """
        Broadcast a chat message from an agent.
        
        Args:
            from_player: Name of player sending message
            message: The chat message
        """
        # Add to chat history
        chat_entry = {
            "from": from_player,
            "message": message,
            "timestamp": time.time()
        }
        self.chat_history.append(chat_entry)
        
        # Trim history if needed
        if len(self.chat_history) > self.max_chat_history * 2:
            self.chat_history = self.chat_history[-self.max_chat_history:]
        
        # Log the chat
        self.logger.log_chat(from_player, message)
        
        # Display to console
        print(f"[CHAT] {from_player}: \"{message}\"")
    
    # === Utilities ===
    
    def get_session_path(self) -> Path:
        """Get the current session directory path."""
        return self.logger.get_session_path()
    
    def save_session(self) -> None:
        """Save the session state."""
        self.logger.save_session_summary(
            agents=self.agents,
            game_state=self._current_game_state
        )
        print(f"[SAVE] Session saved to: {self.logger.get_session_path()}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all agents."""
        return {
            name: agent.get_stats()
            for name, agent in self.agents.items()
        }
