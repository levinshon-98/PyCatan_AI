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
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

from pycatan.ai.config import AIConfig
from pycatan.ai.prompt_manager import PromptManager
from pycatan.ai.llm_client import LLMResponse, StreamChunk, create_llm_client, GeminiClient
from pycatan.ai.response_parser import ResponseParser, ParseResult
from pycatan.ai.schemas import ResponseType, SchemaVersion, get_schema_for_response_type
from pycatan.ai.agent_state import AgentState, compute_state_hash
from pycatan.ai.ai_logger import AILogger
from pycatan.ai.agent_tools import AgentTools
from pycatan.ai.tool_executor import ToolExecutor
from pycatan.ai.stream_broadcaster import StreamBroadcaster
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
        
        # Agent tools and executor
        self.agent_tools = AgentTools()
        self.tool_executor = ToolExecutor(self.agent_tools)
        
        # Stream broadcaster for real-time web updates
        self.stream_broadcaster = StreamBroadcaster()
        
        # LLM client (created lazily when needed)
        self._llm_client: Optional[GeminiClient] = None
        
        # Agent state management
        self.agents: Dict[str, AgentState] = {}
        
        # Chat history (shared between all agents)
        self.chat_history: List[Dict[str, Any]] = []
        self.max_chat_history: int = 20
        self.trade_history: List[Dict[str, Any]] = []
        
        # Current game state (updated by AIUser)
        self._current_game_state: Optional[Dict[str, Any]] = None
        self._current_allowed_actions: Optional[List[str]] = None
        
        # Callback for manual input (when manual_actions is True)
        self._input_callback: Optional[Callable[[str, Dict], str]] = None
        
        # Last LLM response (for display)
        self._last_llm_response: Optional[Dict[str, Any]] = None
        
        # Streaming callbacks
        self._stream_callback: Optional[Callable[[str, StreamChunk], None]] = None  # (player_name, chunk)
        
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
        
        # Update agent tools with current game state
        self.agent_tools.update_game_state(game_state)
        
        # Build "what happened" from recent events plus the current phase prompt.
        what_happened = self._build_what_happened(agent, prompt_message)
        
        # Create prompt
        prompt, schema = self._create_prompt(
            agent=agent,
            game_state=game_state,
            what_happened=what_happened,
            allowed_actions=allowed_actions,
            is_active_turn=True
        )
        
        # Get tool schemas for logging
        tool_schemas = self.agent_tools.get_tools_schema()
        
        # Log the prompt (with tools schema)
        log_info = self.logger.log_prompt(
            player_name=player_name,
            prompt=prompt,
            schema=schema,
            is_active=True,
            what_happened=what_happened,
            allowed_actions=self._format_allowed_actions(allowed_actions),
            tools_schema=tool_schemas
        )
        
        # Mark request sent
        agent.mark_request_sent()
        
        # Send to LLM if enabled
        response = None
        llm_suggestion = None
        
        if self.send_to_llm:
            try:
                self.logger.log_llm_communication(f"Sending prompt #{log_info['number']} for {player_name}", "SEND")
                
                # 🌊 Use streaming if enabled in config
                use_streaming = getattr(self.config.llm, 'enable_streaming', True)  # Default to True
                
                if use_streaming:
                    response = self._send_to_llm_stream(
                        prompt, schema, ResponseType.ACTIVE_TURN,
                        player_name=player_name,
                        prompt_number=log_info["number"]
                    )
                else:
                    response = self._send_to_llm(
                        prompt, schema, ResponseType.ACTIVE_TURN,
                        player_name=player_name,
                        prompt_number=log_info["number"]
                    )
                
                if response and response.success and response.content:
                    self.logger.log_llm_communication(f"Received response for {player_name} ({response.total_tokens} tokens)", "RECV")
                    llm_suggestion = self._parse_response(response, ResponseType.ACTIVE_TURN)
                    if llm_suggestion is None:
                        llm_suggestion = self._fallback_decision_from_unparsed_response(
                            response.content,
                            allowed_actions,
                            game_state
                        )
                        if llm_suggestion:
                            self.logger.log_llm_communication(
                                f"Recovered fallback decision after parse failure: {llm_suggestion}",
                                "WARNING"
                            )
                    self._last_llm_response = llm_suggestion
                    
                    # Log the action suggestion with details
                    if llm_suggestion:
                        # Broadcast reasoning/thinking to web visualization
                        thinking = llm_suggestion.get("internal_thinking", "")
                        if thinking:
                            # Show abbreviated thinking in the status flow
                            thinking_preview = thinking[:80] + "..." if len(thinking) > 80 else thinking
                            self._broadcast_status(player_name, "reasoning", thinking_preview, min_display_time=0.5)
                        
                        action = llm_suggestion.get("action_type", "unknown")
                        params = llm_suggestion.get("parameters", {})
                        self.logger.log_llm_communication(f"LLM suggests: {action} {params}", "RECV")
                    
                    # Broadcast done after reasoning is shown
                    self._broadcast_status(player_name, "done")
                else:
                    # Only log error if there actually is one
                    if response and response.error:
                        self.logger.log_llm_communication(f"LLM error: {response.error}", "ERROR")
                    elif not response:
                        self.logger.log_llm_communication("LLM error: No response received", "ERROR")
                    elif not response.content:
                        self.logger.log_llm_communication("LLM error: Empty response content", "ERROR")
                    self._broadcast_status(player_name, "done")
                
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
        
        # Merge LLM's memory/chat with the action (even if action was manual)
        # This ensures note_to_self and say_outloud are preserved from LLM
        if llm_suggestion and parsed:
            # If parsed doesn't have note_to_self, use LLM's
            if not parsed.get("note_to_self") and llm_suggestion.get("note_to_self"):
                parsed["note_to_self"] = llm_suggestion["note_to_self"]
            # If parsed doesn't have say_outloud, use LLM's
            if not parsed.get("say_outloud") and llm_suggestion.get("say_outloud"):
                parsed["say_outloud"] = llm_suggestion["say_outloud"]
        
        if parsed:
            # Update memory
            note_to_self = parsed.get("note_to_self")
            agent.update_memory(note_to_self)
            
            # Save memories to file for web viewer (real-time update)
            if note_to_self:
                self.logger.save_agent_memories(self.agents)
            
            # Clear events since they've been processed
            agent.clear_events()
            
            # Handle chat message if present
            if parsed.get("say_outloud"):
                self._broadcast_chat(player_name, parsed["say_outloud"])
        
        if parsed:
            return parsed

        agent.add_event(
            "response_parse_failed",
            "Your previous response could not be parsed as valid JSON. "
            f"Use exactly one of these allowed actions: {allowed_actions}.",
            {"allowed_actions": allowed_actions}
        )
        fallback_action = self._fallback_decision_from_allowed_actions(allowed_actions)
        if fallback_action:
            return fallback_action

        if len(allowed_actions) == 1:
            return {
                "internal_thinking": "Unable to recover full parameters after parse failure; retrying the required action.",
                "action_type": self._action_name_for_allowed(allowed_actions[0]),
                "parameters": {},
            }

        return {
            "internal_thinking": "Unable to recover a safe action after parse failure.",
            "action_type": "end_turn",
            "parameters": {},
        }

    def _fallback_decision_from_unparsed_response(
        self,
        raw_content: str,
        allowed_actions: List[str],
        game_state: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Recover a minimal action from a truncated response when it is safe."""
        if not raw_content or not allowed_actions:
            return None

        action_text = self._action_name_for_allowed(allowed_actions[0])
        if len(allowed_actions) != 1:
            return None

        if allowed_actions[0] in {"PLACE_STARTING_SETTLEMENT", "BUILD_SETTLEMENT"}:
            node_id = self._extract_legal_node_id(raw_content, game_state)
            if node_id is not None:
                return {
                    "internal_thinking": "Recovered from an incomplete JSON response by using a legal node explicitly discussed.",
                    "action_type": action_text,
                    "parameters": {"node": node_id},
                }

        if allowed_actions[0] == "PLACE_STARTING_ROAD":
            road = self._extract_legal_starting_road(raw_content, game_state)
            if road is not None:
                from_node, to_node = road
                return {
                    "internal_thinking": "Recovered from an incomplete JSON response by using a legal starting road explicitly discussed.",
                    "action_type": action_text,
                    "parameters": {"from": from_node, "to": to_node},
                }

        return None

    def _fallback_decision_from_allowed_actions(
        self,
        allowed_actions: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Return a no-parameter fallback only when the allowed action is safe."""
        if len(allowed_actions) != 1:
            return None

        no_param_actions = {
            "ROLL_DICE",
            "BUY_DEV_CARD",
            "END_TURN",
            "TRADE_ACCEPT",
            "TRADE_REJECT",
        }
        if allowed_actions[0] not in no_param_actions:
            return None

        return {
            "internal_thinking": "Fallback after parse failure.",
            "action_type": self._action_name_for_allowed(allowed_actions[0]),
            "parameters": {},
        }

    def _extract_legal_node_id(
        self,
        text: str,
        game_state: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """Extract the first mentioned node that is not already blocked."""
        candidates = [
            int(match.group(1))
            for match in re.finditer(r"\bnode\s+(\d+)\b", text, flags=re.IGNORECASE)
        ]
        if not candidates:
            return None

        blocked_nodes = self._blocked_settlement_nodes(game_state)
        for node_id in candidates:
            if node_id not in blocked_nodes:
                return node_id

        return None

    def _extract_legal_starting_road(
        self,
        text: str,
        game_state: Optional[Dict[str, Any]] = None
    ) -> Optional[tuple[int, int]]:
        """Extract a legal setup road from mentioned nodes and compact state."""
        if not text or not game_state:
            return None

        current_player = game_state.get("meta", {}).get("curr")
        nodes = game_state.get("N", [])
        state = game_state.get("state", {})
        buildings = state.get("bld", [])
        roads = state.get("rds", [])

        own_settlements = [
            building[0]
            for building in buildings
            if isinstance(building, list)
            and len(building) >= 2
            and building[1] == current_player
            and isinstance(building[0], int)
        ]
        if not own_settlements:
            return None

        all_road_edges = set()
        own_road_edges = set()
        for road in roads:
            if not isinstance(road, list) or len(road) < 2:
                continue
            edge = road[0]
            if isinstance(edge, (list, tuple)) and len(edge) == 2:
                normalized_edge = tuple(sorted(edge))
                all_road_edges.add(normalized_edge)
                if road[1] == current_player:
                    own_road_edges.add(normalized_edge)

        candidate_sources = [
            node_id
            for node_id in own_settlements
            if not any(node_id in edge for edge in own_road_edges)
        ] or list(reversed(own_settlements))

        mentioned_nodes = [
            int(match.group(1))
            for match in re.finditer(r"\bnode\s+(\d+)\b", text, flags=re.IGNORECASE)
        ]

        def is_valid_edge(from_node: int, to_node: int) -> bool:
            if from_node <= 0 or from_node >= len(nodes) or not nodes[from_node]:
                return False
            if to_node not in nodes[from_node][0]:
                return False
            return tuple(sorted((from_node, to_node))) not in all_road_edges

        for source in candidate_sources:
            for target in reversed(mentioned_nodes):
                if is_valid_edge(source, target):
                    return source, target

        for source in candidate_sources:
            if source <= 0 or source >= len(nodes) or not nodes[source]:
                continue
            for target in nodes[source][0]:
                if is_valid_edge(source, target):
                    return source, target

        return None

    def _blocked_settlement_nodes(self, game_state: Optional[Dict[str, Any]]) -> set[int]:
        """Return occupied nodes and their neighbors from compact AI state."""
        if not game_state:
            return set()

        buildings = game_state.get("state", {}).get("bld", [])
        nodes = game_state.get("N", [])
        blocked = set()
        for building in buildings:
            if not building:
                continue
            node_id = building[0]
            blocked.add(node_id)
            if isinstance(node_id, int) and 0 <= node_id < len(nodes) and nodes[node_id]:
                blocked.update(nodes[node_id][0])

        return blocked

    def _action_name_for_allowed(self, allowed_action: str) -> str:
        """Convert engine action names to AI-facing action names."""
        action = self._format_allowed_actions([allowed_action])
        return action[0]["type"] if action else allowed_action.lower()
    
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
            recent_notes = [
                note.get("note", str(note))
                for note in getattr(agent, "memory_history", [])[-self.config.memory.short_term_turns:]
            ]
            agent_memory = {
                "note_from_last_turn": agent.memory,
                "recent_notes": recent_notes
            }
        
        # Create prompt through PromptManager
        prompt = self.prompt_manager.create_prompt(
            player_num=agent.player_id,
            player_name=agent.player_name,
            player_color=agent.player_color,
            game_state=game_state,
            what_happened=what_happened,
            available_actions=formatted_actions,
            chat_history=self.chat_history[-self.max_chat_history:] if self.chat_history else None,
            agent_memory=agent_memory,
            pending_trades=self._get_relevant_trades(agent.player_name)
        )
        
        # Get appropriate schema based on config version
        schema_version = SchemaVersion.V2  # Default
        if hasattr(self.config, 'llm') and hasattr(self.config.llm, 'schema_version'):
            version_str = self.config.llm.schema_version.lower()
            if version_str == 'v1':
                schema_version = SchemaVersion.V1
            elif version_str == 'v2':
                schema_version = SchemaVersion.V2
        
        response_type = ResponseType.ACTIVE_TURN if is_active_turn else ResponseType.OBSERVING
        schema = get_schema_for_response_type(response_type, schema_version)
        
        return prompt, schema
    
    def _format_allowed_actions(self, allowed_actions: List[str]) -> List[Dict[str, Any]]:
        """Convert action type strings to formatted action dicts."""
        # Map action type names to example parameters
        action_templates = {
            "BUILD_SETTLEMENT": {
                "type": "build_settlement",
                "description": "Build a settlement at a node",
                "example_parameters": "{\"node\": X}"
            },
            "BUILD_CITY": {
                "type": "build_city",
                "description": "Upgrade a settlement to a city",
                "example_parameters": "{\"node\": X}"
            },
            "BUILD_ROAD": {
                "type": "build_road",
                "description": "Build a road between two nodes",
                "example_parameters": "{\"from\": X, \"to\": Y}"
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
                "description": (
                    "Play a development card. Use exact card_type values: "
                    "knight, road_building, monopoly, year_of_plenty. "
                    "Victory points are counted automatically."
                ),
                "example_parameters": (
                    "{\"card_type\": \"knight\", \"hex\": X, \"target_player\": \"Bob\"} OR "
                    "{\"card_type\": \"road_building\", \"road_1\": [A, B], \"road_2\": [C, D]} OR "
                    "{\"card_type\": \"monopoly\", \"resource\": \"wheat\"} OR "
                    "{\"card_type\": \"year_of_plenty\", \"resources\": [\"wood\", \"brick\"]}"
                )
            },
            "TRADE_BANK": {
                "type": "trade_bank",
                "description": "Trade resources with the bank",
                "example_parameters": "{\"give\": \"wood\", \"receive\": \"brick\"}"
            },
            "TRADE_PROPOSE": {
                "type": "trade_propose",
                "description": "Propose a trade to other players",
                "example_parameters": "{\"target_player\": \"Charlie\", \"offer\": {\"wood\": X}, \"request\": {\"brick\": Y}}"
            },
            "ROBBER_MOVE": {
                "type": "robber_move",
                "description": "Move the robber to a hex",
                "example_parameters": "{\"hex\": X}"
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
                "example_parameters": "{\"node\": X}"
            },
            "PLACE_STARTING_ROAD": {
                "type": "place_starting_road",
                "description": "Place your starting road",
                "example_parameters": "{\"from\": X, \"to\": Y}"
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
        
        return result
    
    def _build_what_happened(self, agent: AgentState, prompt_message: str = "") -> str:
        """
        Build the 'what happened' message for the next prompt.

        Recent events explain what changed; the phase prompt explains what the
        engine needs right now. Both matter after forced actions such as robber
        steal and after failed actions.
        
        Args:
            agent: The agent to build message for
            
        Returns:
            Clear description of the most recent action relevant to this agent
        """
        phase_prompt = (prompt_message or "").strip()
        if not agent.recent_events:
            return phase_prompt or "It's your turn."
        
        # Get only the last event and format it clearly
        last_event = agent.recent_events[-1]
        event_summary = self._format_event_for_agent(last_event, agent)

        if phase_prompt and phase_prompt not in event_summary:
            return f"{event_summary}\nCurrent required action: {phase_prompt}"

        return event_summary
    
    def _format_event_for_agent(self, event: Dict[str, Any], agent: AgentState) -> str:
        """
        Format a single event into a clear, agent-focused message.
        
        Args:
            event: Event dict with 'type' and 'message' keys
            agent: The agent receiving this message
            
        Returns:
            Clear, concise description of what happened
        """
        event_type = event.get('type', '')
        message = event.get('message', '')
        
        # Replace "Player X" with actual player name
        message = self._replace_player_numbers_with_names(message)

        if event_type == "action_failed":
            return message
        
        # Parse common event patterns and make them clearer
        if 'PLACE_STARTING_SETTLEMENT' in message:
            if agent.player_name in message:
                return "You just placed your starting settlement. Now place your starting road adjacent to it."
            else:
                return message.replace('ActionType.PLACE_STARTING_SETTLEMENT', 'placed their starting settlement')
        
        if 'PLACE_STARTING_ROAD' in message:
            if agent.player_name in message:
                return "You just placed your starting road."
            else:
                return message.replace('ActionType.PLACE_STARTING_ROAD', 'placed their starting road')
        
        if 'BUILD_SETTLEMENT' in message:
            if agent.player_name in message:
                return "You just built a settlement."
            else:
                return message.replace('ActionType.BUILD_SETTLEMENT', 'built a settlement')
        
        if 'BUILD_ROAD' in message:
            if agent.player_name in message:
                return "You just built a road."
            else:
                return message.replace('ActionType.BUILD_ROAD', 'built a road')
        
        if 'BUILD_CITY' in message:
            if agent.player_name in message:
                return "You just upgraded to a city."
            else:
                return message.replace('ActionType.BUILD_CITY', 'upgraded to a city')
        
        if 'ROLL_DICE' in message:
            # Extract dice result if present in message
            # Try to make it more informative
            if agent.player_name in message:
                return message.replace('ActionType.ROLL_DICE', 'rolled the dice')
            else:
                return message.replace('ActionType.ROLL_DICE', 'rolled the dice')
        
        if 'turn begins' in message.lower():
            if agent.player_name in message:
                return "It's your turn."
            else:
                return message
        
        # Default: clean up ActionType formatting
        cleaned = message.replace('ActionType.', '').replace('_', ' ').lower()
        return cleaned
    
    def _replace_player_numbers_with_names(self, message: str) -> str:
        """
        Replace 'Player X' with actual player names in a message.
        
        Args:
            message: Message with player numbers
            
        Returns:
            Message with player names
        """
        import re
        
        # Find all "Player X" patterns
        pattern = r'Player (\d+)'
        
        def replace_func(match):
            player_id = int(match.group(1))
            # Find agent with this player_id
            for agent_name, agent in self.agents.items():
                if agent.player_id == player_id:
                    return agent_name
            return match.group(0)  # Keep original if not found
        
        return re.sub(pattern, replace_func, message)
    
    def _send_to_llm(
        self,
        prompt: Dict[str, Any],
        schema: Dict[str, Any],
        response_type: ResponseType,
        player_name: str = "unknown",
        prompt_number: int = 0
    ) -> LLMResponse:
        """
        Send prompt to LLM and get response.
        
        Handles tool calling loop:
        1. Send prompt with tools
        2. If LLM requests tools, execute them
        3. Send results back to LLM
        4. Repeat until final answer
        
        Args:
            prompt: The prompt dictionary
            schema: Response schema
            response_type: Type of response expected
            player_name: Name of the player (for logging)
            prompt_number: The prompt number (for logging)
        """
        # Convert prompt to string
        prompt_str = json.dumps(prompt, indent=2, ensure_ascii=False)
        
        # Get tool schemas
        tool_schemas = self.agent_tools.get_tools_schema()
        
        # Build generation kwargs
        kwargs = {
            "response_schema": schema,
            "tools": tool_schemas,  # Enable function calling
            "enable_thinking": self.config.llm.enable_thinking,
            "max_tokens": self.config.llm.max_tokens,
        }
        
        # Determine thinking budgets and max iterations
        if self.config.llm.thinking_budgets:
            # Use dynamic budgets from config
            thinking_budgets = self.config.llm.thinking_budgets
            max_tool_iterations = len(thinking_budgets)
        else:
            # Fallback to single budget, default 3 iterations
            thinking_budgets = [self.config.llm.thinking_budget] * 3
            max_tool_iterations = 3
        
        # Tool calling loop
        iteration = 0
        conversation_context = prompt_str
        
        # Accumulated tokens across all iterations
        accumulated_prompt_tokens = 0
        accumulated_completion_tokens = 0
        accumulated_thinking_tokens = 0
        accumulated_tool_tokens = 0
        final_response = None
        
        while iteration < max_tool_iterations:
            iteration += 1
            is_tool_followup = iteration > 1
            
            # Set thinking budget for this iteration
            if self.config.llm.enable_thinking:
                current_budget = thinking_budgets[iteration - 1] if iteration <= len(thinking_budgets) else thinking_budgets[-1]
                kwargs["thinking_budget"] = current_budget
                self.logger.log_llm_communication(
                    f"💭 Thinking budget for iteration {iteration}: {current_budget} tokens",
                    "INFO"
                )
            
            # Log API call start with running index
            current_tools = kwargs.get("tools", [])
            api_call_id = self.logger.log_api_call_start(
                player_name=player_name,
                prompt_number=prompt_number,
                iteration=iteration,
                tools_schema=current_tools if current_tools else None,
                is_tool_followup=is_tool_followup
            )
            
            # Send request to LLM
            response = self.llm_client.generate(
                conversation_context,
                **kwargs
            )
            
            # Accumulate tokens from this iteration
            accumulated_prompt_tokens += response.prompt_tokens
            accumulated_completion_tokens += response.completion_tokens
            accumulated_thinking_tokens += response.thinking_tokens
            
            # Log API call end
            self.logger.log_api_call_end(
                call_id=api_call_id,
                success=response.success,
                tokens=response.total_tokens,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                has_tool_calls=bool(response.tool_calls),
                tool_calls_count=len(response.tool_calls) if response.tool_calls else 0,
                error=response.error
            )
            
            if not response.success:
                # Update response with accumulated tokens before returning
                response.prompt_tokens = accumulated_prompt_tokens
                response.completion_tokens = accumulated_completion_tokens
                response.thinking_tokens = accumulated_thinking_tokens
                response.total_tokens = accumulated_prompt_tokens + accumulated_completion_tokens + accumulated_thinking_tokens + accumulated_tool_tokens
                return response
            
            # Check if LLM requested tools
            if response.tool_calls:
                # Log this intermediate response (with tool_calls)
                self.logger.log_intermediate_response(
                    player_name=player_name,
                    request_number=prompt_number,
                    iteration=iteration,
                    response=response
                )
                
                # Broadcast each tool call with parameters
                try:
                    for tc in response.tool_calls[:3]:
                        if isinstance(tc, dict):
                            tool_name = tc.get('name', 'unknown')
                            tool_params = tc.get('parameters', {})
                        else:
                            tool_name = tc.name if hasattr(tc, 'name') else str(tc)
                            tool_params = tc.parameters if hasattr(tc, 'parameters') else {}
                        
                        # Format parameters for display - show full reasoning
                        if tool_params:
                            # Extract reasoning separately for better display
                            reasoning = tool_params.get('reasoning', '')
                            other_params = {k: v for k, v in tool_params.items() if k != 'reasoning'}
                            
                            params_str = json.dumps(other_params, ensure_ascii=False)
                            if len(params_str) > 10000:
                                params_str = params_str[:9997] + "..."
                            
                            # Include reasoning in full (up to 200 chars)
                            if reasoning:
                                if len(reasoning) > 200:
                                    reasoning = reasoning[:197] + "..."
                                tool_display = f"{tool_name}({params_str})\n💭 {reasoning}"
                            else:
                                tool_display = f"{tool_name}({params_str})"
                        else:
                            tool_display = f"{tool_name}()"
                        
                        self._broadcast_status(player_name, "tool_call", tool_display, min_display_time=0.8)
                    
                    if len(response.tool_calls) > 3:
                        self._broadcast_status(player_name, "tool_call", f"+{len(response.tool_calls) - 3} more tools...")
                except Exception as e:
                    self._broadcast_status(player_name, "tool_call", f"Using {len(response.tool_calls)} tool(s)")
                
                self.logger.log_llm_communication(
                    f"🔧 LLM requested {len(response.tool_calls)} tool(s) (iteration {iteration})",
                    "TOOL_REQUEST"
                )
                
                # Execute tools
                batch = self.tool_executor.execute_tool_calls(response.tool_calls)
                
                # Log tool execution
                self.logger.log_tool_execution(batch)
                
                # Add tool tokens to accumulated count
                accumulated_tool_tokens += batch.total_tokens
                
                # Add tool tokens to stats
                self.llm_client.stats.add_tool_tokens(batch.total_tokens)
                
                # Format results for LLM
                tool_results = self.tool_executor.format_tool_results_for_llm(batch)
                
                # Add tool results to conversation
                conversation_context = f"{conversation_context}\n\n{tool_results}\n\nNow provide your final answer based on the tool results:"
                
                # Check if this is the last iteration
                if iteration >= max_tool_iterations:
                    # Remove tools and send ONE FINAL request for structured answer
                    kwargs["tools"] = []
                    self.logger.log_llm_communication(
                        f"🔒 Tools disabled - sending final request for structured answer",
                        "INFO"
                    )
                    
                    # Log the final prompt
                    self.logger.log_tool_followup_prompt(
                        player_name=player_name,
                        original_prompt_number=prompt_number,
                        iteration=iteration + 1,
                        conversation_context=conversation_context,
                        tool_results=tool_results,
                        tools_schema=None,  # No tools
                        schema=schema
                    )
                    
                    # Send final request (without tools)
                    final_api_call_id = self.logger.log_api_call_start(
                        player_name=player_name,
                        prompt_number=prompt_number,
                        iteration=iteration + 1,
                        tools_schema=None,
                        is_tool_followup=True
                    )
                    
                    final_response = self.llm_client.generate(
                        conversation_context,
                        **kwargs
                    )
                    
                    # Accumulate tokens from final request
                    accumulated_prompt_tokens += final_response.prompt_tokens
                    accumulated_completion_tokens += final_response.completion_tokens
                    accumulated_thinking_tokens += final_response.thinking_tokens
                    
                    self.logger.log_api_call_end(
                        call_id=final_api_call_id,
                        success=final_response.success,
                        tokens=final_response.total_tokens,
                        prompt_tokens=final_response.prompt_tokens,
                        completion_tokens=final_response.completion_tokens,
                        has_tool_calls=bool(final_response.tool_calls),
                        tool_calls_count=0,
                        error=final_response.error
                    )
                    
                    # Update final response with accumulated tokens
                    final_response.prompt_tokens = accumulated_prompt_tokens
                    final_response.completion_tokens = accumulated_completion_tokens
                    final_response.thinking_tokens = accumulated_thinking_tokens
                    final_response.total_tokens = accumulated_prompt_tokens + accumulated_completion_tokens + accumulated_thinking_tokens + accumulated_tool_tokens
                    
                    return final_response
                else:
                    # More iterations available - continue the loop
                    next_tools = tool_schemas
                    
                    # Log the tool follow-up prompt that will be sent
                    self.logger.log_tool_followup_prompt(
                        player_name=player_name,
                        original_prompt_number=prompt_number,
                        iteration=iteration + 1,
                        conversation_context=conversation_context,
                        tool_results=tool_results,
                        tools_schema=next_tools,
                        schema=schema
                    )
                    
                    self.logger.log_llm_communication(
                        f"✅ Tool results sent back to LLM ({batch.total_tokens} tokens)",
                        "TOOL_RESULTS"
                    )
                
            else:
                # No tool calls - this is the final structured answer
                # Gemini 3 supports tools + JSON schema together, so response is already structured
                # Update response with accumulated tokens before returning
                response.prompt_tokens = accumulated_prompt_tokens
                response.completion_tokens = accumulated_completion_tokens
                response.thinking_tokens = accumulated_thinking_tokens
                response.total_tokens = accumulated_prompt_tokens + accumulated_completion_tokens + accumulated_thinking_tokens + accumulated_tool_tokens
                # Note: "done" status will be broadcast by the caller after processing reasoning
                return response
        
        # Should not reach here normally, but return last response as fallback
        self.logger.log_llm_communication(
            f"⚠️ Loop ended unexpectedly after {iteration} iterations",
            "WARNING"
        )
        return response
    
    def _send_to_llm_stream(
        self,
        prompt: Dict[str, Any],
        schema: Dict[str, Any],
        response_type: ResponseType,
        player_name: str = "unknown",
        prompt_number: int = 0
    ) -> LLMResponse:
        """
        Send prompt to LLM with STREAMING support.
        
        This version broadcasts real-time updates:
        - Thoughts as they arrive
        - Function calls as they're made  
        - Text chunks as they're generated
        
        Same tool calling loop as _send_to_llm but with streaming.
        """
        self.logger.log_llm_communication("🌊 Streaming mode ACTIVE", "INFO")
        
        # Convert prompt to string
        prompt_str = json.dumps(prompt, indent=2, ensure_ascii=False)
        
        # Get tool schemas
        tool_schemas = self.agent_tools.get_tools_schema()
        
        # Build generation kwargs
        kwargs = {
            "response_schema": schema,
            "tools": tool_schemas,
            "enable_thinking": self.config.llm.enable_thinking,
            "max_tokens": self.config.llm.max_tokens,
        }
        
        # Determine thinking budgets and max iterations
        if self.config.llm.thinking_budgets:
            thinking_budgets = self.config.llm.thinking_budgets
            max_tool_iterations = len(thinking_budgets)
        else:
            thinking_budgets = [self.config.llm.thinking_budget] * 3
            max_tool_iterations = 3
        
        # Tool calling loop
        iteration = 0
        conversation_context = prompt_str
        
        # Accumulated tokens across all iterations
        accumulated_prompt_tokens = 0
        accumulated_completion_tokens = 0
        accumulated_thinking_tokens = 0
        accumulated_tool_tokens = 0
        response = None
        
        while iteration < max_tool_iterations:
            iteration += 1
            is_tool_followup = iteration > 1
            
            # Set thinking budget for this iteration
            if self.config.llm.enable_thinking:
                current_budget = thinking_budgets[iteration - 1] if iteration <= len(thinking_budgets) else thinking_budgets[-1]
                kwargs["thinking_budget"] = current_budget
                self.logger.log_llm_communication(
                    f"💭 Thinking budget for iteration {iteration}: {current_budget} tokens",
                    "INFO"
                )
            
            # Log API call start
            current_tools = kwargs.get("tools", [])
            api_call_id = self.logger.log_api_call_start(
                player_name=player_name,
                prompt_number=prompt_number,
                iteration=iteration,
                tools_schema=current_tools if current_tools else None,
                is_tool_followup=is_tool_followup
            )
            
            # Broadcast initial thinking status IMMEDIATELY after sending API call
            self._broadcast_status(player_name, "thinking", "Thinking...")
            
            # === STREAMING: Use generate_stream instead of generate ===
            accumulated_text = ""
            accumulated_thoughts = ""
            tool_calls = []
            
            # Define callback for each chunk
            def on_chunk(chunk: StreamChunk):
                nonlocal accumulated_text, accumulated_thoughts
                
                # Broadcast chunk (this logs and sends to web viewer)
                self._broadcast_stream_chunk(player_name, chunk)
                
                # Also accumulate for final response
                if chunk.chunk_type == 'thought' and chunk.content:
                    accumulated_thoughts += chunk.content
                elif chunk.chunk_type == 'text' and chunk.content:
                    accumulated_text += chunk.content
            
            # Stream the response
            try:
                stream_generator = self.llm_client.generate_stream(
                    conversation_context,
                    on_chunk=on_chunk,
                    **kwargs
                )
                
                # Consume the generator to get all chunks and final response
                final_chunk = None
                for chunk in stream_generator:
                    final_chunk = chunk
                    if chunk.chunk_type == 'function_call' and chunk.function_call:
                        tool_calls.append(chunk.function_call)
                
                # Get the final response from the generator
                # The generator returns LLMResponse at the end
                if hasattr(stream_generator, 'gi_retval'):
                    response = stream_generator.gi_retval
                else:
                    # Build response from accumulated data
                    response = LLMResponse(
                        success=True,
                        content=accumulated_text,
                        tool_calls=tool_calls,
                        model=self.llm_client.model,
                        prompt_tokens=self.llm_client._estimate_tokens(conversation_context),
                        completion_tokens=self.llm_client._estimate_tokens(accumulated_text),
                        thinking_tokens=self.llm_client._estimate_tokens(accumulated_thoughts),
                        total_tokens=0  # Will be calculated
                    )
                    response.total_tokens = response.prompt_tokens + response.completion_tokens + response.thinking_tokens
                
                # Make sure tool_calls are in response
                if tool_calls and not response.tool_calls:
                    response.tool_calls = tool_calls
                    
            except Exception as e:
                self.logger.log_llm_communication(f"❌ Streaming error: {e}", "ERROR")
                response = LLMResponse(
                    success=False,
                    error=str(e),
                    model=self.llm_client.model
                )
            
            # Accumulate tokens from this iteration
            accumulated_prompt_tokens += response.prompt_tokens
            accumulated_completion_tokens += response.completion_tokens
            accumulated_thinking_tokens += response.thinking_tokens
            
            # Log API call end
            self.logger.log_api_call_end(
                call_id=api_call_id,
                success=response.success,
                tokens=response.total_tokens,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                has_tool_calls=bool(response.tool_calls),
                tool_calls_count=len(response.tool_calls) if response.tool_calls else 0,
                error=response.error
            )
            
            if not response.success:
                response.prompt_tokens = accumulated_prompt_tokens
                response.completion_tokens = accumulated_completion_tokens
                response.thinking_tokens = accumulated_thinking_tokens
                response.total_tokens = accumulated_prompt_tokens + accumulated_completion_tokens + accumulated_thinking_tokens + accumulated_tool_tokens
                return response
            
            # Check if LLM requested tools
            if response.tool_calls:
                # Log intermediate response
                self.logger.log_intermediate_response(
                    player_name=player_name,
                    request_number=prompt_number,
                    iteration=iteration,
                    response=response
                )
                
                self.logger.log_llm_communication(
                    f"🔧 LLM requested {len(response.tool_calls)} tool(s) (iteration {iteration})",
                    "TOOL_REQUEST"
                )
                
                # Broadcast tool execution status
                tool_names = [tc.get('name', 'unknown') for tc in response.tool_calls[:3]]
                if len(response.tool_calls) > 3:
                    tool_msg = f"Executing {', '.join(tool_names)} + {len(response.tool_calls)-3} more..."
                else:
                    tool_msg = f"Executing {', '.join(tool_names)}..."
                self._broadcast_status(player_name, "executing_tools", tool_msg, min_display_time=0.5)
                
                # Execute tools
                batch = self.tool_executor.execute_tool_calls(response.tool_calls)
                
                # Log tool execution
                self.logger.log_tool_execution(batch)
                
                # Add tool tokens
                accumulated_tool_tokens += batch.total_tokens
                self.llm_client.stats.add_tool_tokens(batch.total_tokens)
                
                # Format results for LLM
                tool_results = self.tool_executor.format_tool_results_for_llm(batch)
                
                # Add tool results to conversation
                conversation_context = f"{conversation_context}\n\n{tool_results}\n\nNow provide your final answer based on the tool results:"
                
                self.logger.log_llm_communication(
                    f"✅ Tool results sent back to LLM ({batch.total_tokens} tokens)",
                    "TOOL_RESULTS"
                )
                
            else:
                # No tool calls - this is the final answer
                response.prompt_tokens = accumulated_prompt_tokens
                response.completion_tokens = accumulated_completion_tokens
                response.thinking_tokens = accumulated_thinking_tokens
                response.total_tokens = accumulated_prompt_tokens + accumulated_completion_tokens + accumulated_thinking_tokens + accumulated_tool_tokens
                
                # Send done chunk
                done_chunk = StreamChunk(chunk_type='done', is_complete=True)
                self._broadcast_stream_chunk(player_name, done_chunk)
                
                return response
        
        # Loop ended unexpectedly
        self.logger.log_llm_communication(
            f"⚠️ Streaming loop ended after {iteration} iterations",
            "WARNING"
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
        # 🐛 FIX: Prevent duplicate events when multiple AI players call this
        # Each AIUser calls this, but we only want to add the event once
        # Check if this exact event was already added recently
        for agent_name, agent in self.agents.items():
            # Check if the last event is identical (duplicate)
            if (agent.recent_events and 
                agent.recent_events[-1].get('message') == message and
                agent.recent_events[-1].get('type') == event_type):
                # Skip - event already added
                continue
            
            # Add event to all agents (they all see what happens)
            agent.add_event(event_type, message)

    def record_trade_offer(
        self,
        trade_id: str,
        proposer: str,
        target: str,
        offer: Dict[str, Any],
        request: Dict[str, Any]
    ) -> None:
        """Record a structured player-to-player trade offer for prompts."""
        existing = next((trade for trade in self.trade_history if trade.get("trade_id") == trade_id), None)
        trade = {
            "trade_id": trade_id,
            "from": proposer,
            "to": target,
            "offer": offer,
            "request": request,
            "status": "pending",
            "timestamp": time.time(),
        }

        if existing:
            existing.update(trade)
        else:
            self.trade_history.append(trade)
            self.trade_history = self.trade_history[-20:]

        message = (
            f"Trade offer {trade_id}: {proposer} offers "
            f"{self._format_resource_bundle(offer)} to {target} for "
            f"{self._format_resource_bundle(request)}."
        )
        for agent in self.agents.values():
            if not agent.recent_events or agent.recent_events[-1].get("message") != message:
                agent.add_event("trade_offer", message, {"trade_id": trade_id})

    def record_trade_response(self, trade_id: str, status: str, responder: str) -> None:
        """Record acceptance or rejection of a structured trade offer."""
        trade = next((item for item in self.trade_history if item.get("trade_id") == trade_id), None)
        if trade:
            trade["status"] = status
            trade["responded_by"] = responder
            trade["resolved_at"] = time.time()

        message = f"Trade {trade_id} was {status} by {responder}."
        for agent in self.agents.values():
            if not agent.recent_events or agent.recent_events[-1].get("message") != message:
                agent.add_event("trade_response", message, {"trade_id": trade_id, "status": status})

    def _get_relevant_trades(self, player_name: str) -> List[Dict[str, Any]]:
        """Return recent/pending trades relevant to a prompt."""
        relevant = []
        for trade in self.trade_history[-10:]:
            if (
                trade.get("status") == "pending"
                or trade.get("from") == player_name
                or trade.get("to") == player_name
            ):
                relevant.append(trade)
        return relevant[-5:]

    def _format_resource_bundle(self, resources: Dict[str, Any]) -> str:
        """Format a resource-count dict for event messages."""
        if not resources:
            return "nothing"
        return ", ".join(f"{amount} {resource}" for resource, amount in resources.items())
    
    def _broadcast_chat(self, from_player: str, message: str) -> None:
        """
        Broadcast a chat message from an agent.
        
        Args:
            from_player: Name of player sending message
            message: The chat message
        """
        # Add to chat history (no timestamp - cleaner for LLM)
        chat_entry = {
            "from": from_player,
            "message": message
        }
        self.chat_history.append(chat_entry)
        
        # Trim history if needed
        if len(self.chat_history) > self.max_chat_history * 2:
            self.chat_history = self.chat_history[-self.max_chat_history:]
        
        # Log the chat
        self.logger.log_chat(from_player, message)
        
        # Call chat callback if registered (for web visualization)
        if hasattr(self, '_chat_callback') and self._chat_callback:
            self._chat_callback(from_player, message)
        
        # Display to console
        print(f"[CHAT] {from_player}: \"{message}\"")
    
    def set_chat_callback(self, callback) -> None:
        """
        Set callback for chat messages (e.g., for web visualization).
        
        Args:
            callback: Function(player_name, message) to call on chat
        """
        self._chat_callback = callback
    
    def set_status_callback(self, callback) -> None:
        """
        Set callback for AI status updates (e.g., for web visualization).
        
        Args:
            callback: Function(player_name, status, details) to call on status change
        """
        self._status_callback = callback
        self._last_status_time = 0  # Track last status broadcast time
    
    def _broadcast_status(self, player_name: str, status: str, details: str = "", min_display_time: float = 1.5) -> None:
        """Broadcast AI status update to callback if registered.
        
        Args:
            player_name: Name of the player
            status: Status type ('thinking', 'tool_call', 'done', etc.)
            details: Optional details about what's happening
            min_display_time: Minimum time to wait since last status (seconds)
        """
        import time
        
        if hasattr(self, '_status_callback') and self._status_callback:
            # Ensure minimum display time for previous status
            if hasattr(self, '_last_status_time') and self._last_status_time > 0:
                elapsed = time.time() - self._last_status_time
                if elapsed < min_display_time and status != 'done':
                    time.sleep(min_display_time - elapsed)
            
            self._status_callback(player_name, status, details)
            self._last_status_time = time.time()
            
            # Give Flask time to actually send the SSE event before we block on API call
            time.sleep(0.1)
    
    def _broadcast_stream_chunk(self, player_name: str, chunk: StreamChunk) -> None:
        """Broadcast streaming chunk to callback and status system.
        
        Args:
            player_name: Name of the player
            chunk: StreamChunk object
        """
        # Log the chunk to file
        self.logger.log_stream_chunk(
            player_name=player_name,
            chunk_type=chunk.chunk_type,
            content=chunk.content,
            function_call=chunk.function_call
        )
        
        # Send to web viewer via HTTP
        self.stream_broadcaster.broadcast(player_name, chunk)
        
        # Broadcast as status update for UI
        if chunk.chunk_type == 'thought':
            # Real thinking from Gemini 2.0 Thinking
            if chunk.content:
                preview = chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
                self._broadcast_status(player_name, "thinking", preview, min_display_time=0.3)
        
        elif chunk.chunk_type == 'function_call' and chunk.function_call:
            # Extract reasoning if present
            params = chunk.function_call.get('parameters', {})
            reasoning = params.get('reasoning', '')
            
            if reasoning:
                # Show reasoning first (without emoji - UI adds it)
                reasoning_preview = reasoning[:120] + "..." if len(reasoning) > 120 else reasoning
                self._broadcast_status(player_name, "reasoning", reasoning_preview, min_display_time=0.5)
            
            # Show function call
            fn_name = chunk.function_call.get('name', 'unknown')
            params_clean = {k: v for k, v in params.items() if k != 'reasoning'}
            
            if params_clean:
                # Format parameters nicely
                params_display = ', '.join(f"{k}={v}" for k, v in list(params_clean.items())[:3])
                if len(params_clean) > 3:
                    params_display += ', ...'
                display = f"{fn_name}({params_display})"
            else:
                display = f"{fn_name}()"
            
            self._broadcast_status(player_name, "tool_call", display, min_display_time=0.5)
        
        elif chunk.chunk_type == 'text' and chunk.content:
            # Streaming text response - update continuously in a box
            self._broadcast_status(player_name, "text_stream", chunk.content, min_display_time=0.0)
        
        elif chunk.chunk_type == 'done':
            # Stream complete
            self._broadcast_status(player_name, "stream_done", "", min_display_time=0.3)
        
        # Also call local callback if registered
        if hasattr(self, '_stream_callback') and self._stream_callback:
            self._stream_callback(player_name, chunk)
    
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
