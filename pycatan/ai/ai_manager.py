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
from pycatan.ai.schemas import ResponseType, SchemaVersion, get_schema_for_response_type
from pycatan.ai.agent_state import AgentState, compute_state_hash
from pycatan.ai.ai_logger import AILogger
from pycatan.ai.agent_tools import AgentTools
from pycatan.ai.tool_executor import ToolExecutor
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
        
        # Update agent tools with current game state
        self.agent_tools.update_game_state(game_state)
        
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
                response = self._send_to_llm(
                    prompt, schema, ResponseType.ACTIVE_TURN,
                    player_name=player_name,
                    prompt_number=log_info["number"]
                )
                
                if response and response.success and response.content:
                    self.logger.log_llm_communication(f"Received response for {player_name} ({response.total_tokens} tokens)", "RECV")
                    llm_suggestion = self._parse_response(response, ResponseType.ACTIVE_TURN)
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
                    error_msg = response.error if response else "No response"
                    self.logger.log_llm_communication(f"LLM error: {error_msg}", "ERROR")
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
                "example_parameters": "{\"offer\": {\"wood\": X}, \"request\": {\"brick\": Y}}"
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
        
        # Always add WAIT_FOR_RESPONSE as an option (for communication)
        if "WAIT_FOR_RESPONSE" not in allowed_actions:
            result.append(action_templates["WAIT_FOR_RESPONSE"])
        
        return result
    
    def _build_what_happened(self, agent: AgentState) -> str:
        """
        Build the 'what happened' message - only the LAST action in clear format.
        
        Args:
            agent: The agent to build message for
            
        Returns:
            Clear description of the most recent action relevant to this agent
        """
        if not agent.recent_events:
            return "Game is starting. Place your first settlement."
        
        # Get only the last event and format it clearly
        last_event = agent.recent_events[-1]
        return self._format_event_for_agent(last_event, agent)
    
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
            
            # Broadcast thinking status
            if iteration == 1:
                self._broadcast_status(player_name, "thinking", "Analyzing situation...")
            else:
                self._broadcast_status(player_name, "thinking", f"Re-evaluating (iteration {iteration})...")
            
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
                
                # Broadcast processing status after tool execution
                self._broadcast_status(player_name, "processing", "Analyzing results...")
                
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
