"""
AI Logger for PyCatan AI Agents

This module handles all logging for the AI system:
- Prompt logging (JSON + TXT files)
- Response logging (JSON files)
- Player MD logs (human-readable)
- Session management

Maintains compatibility with existing log formats while providing
a cleaner interface for the new AIManager.
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from pycatan.ai.llm_client import LLMResponse

# Gemini 3 Flash Preview pricing (per million tokens)
GEMINI_FLASH_INPUT_PRICE = 0.50  # $0.50 per 1M tokens
GEMINI_FLASH_OUTPUT_PRICE = 3.00  # $3.00 per 1M tokens


class AILogger:
    """
    Centralized logging for AI agents.
    
    Creates and manages:
    - Session directories with timestamps
    - Per-player log files (MD format)
    - Prompt and response JSON files
    - Summary statistics
    
    Directory Structure:
        session_YYYYMMDD_HHMMSS/
        ├── player_name/
        │   ├── prompts/
        │   │   ├── prompt_1.json
        │   │   ├── prompt_1.txt
        │   │   └── ...
        │   ├── responses/
        │   │   ├── response_1.json
        │   │   └── ...
        │   └── player_name.md
        ├── chat_history.json
        └── session_summary.json
    """
    
    def __init__(self, session_dir: Optional[Path] = None, base_dir: Optional[Path] = None):
        """
        Initialize the AI logger.
        
        Args:
            session_dir: Explicit session directory path. If None, auto-creates.
            base_dir: Base directory for sessions. Default: examples/ai_testing/my_games/
        """
        self.base_dir = base_dir or Path("examples/ai_testing/my_games")
        
        if session_dir is not None:
            self.session_dir = Path(session_dir)
        else:
            self.session_dir = self._create_session_dir()
        
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Track request numbers per player
        self.request_counters: Dict[str, int] = {}
        
        # Global API call index (across all players/tool iterations)
        self.api_call_index: int = 0
        
        # Track pending API calls (sent but not yet received)
        self.pending_api_calls: Dict[int, Dict[str, Any]] = {}
        
        # Track cumulative costs
        self.cumulative_input_tokens: int = 0
        self.cumulative_output_tokens: int = 0
        self.cumulative_cost: float = 0.0
        
        # Session start time
        self.start_time = datetime.now()
        
        # Initialize session
        self._init_session()
    
    def _create_session_dir(self) -> Path:
        """Create a new session directory with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = self.base_dir / f"session_{timestamp}"
        return session_dir
    
    def _init_session(self) -> None:
        """Initialize the session with metadata."""
        metadata = {
            "session_id": self.session_dir.name,
            "start_time": self.start_time.isoformat(),
            "version": "2.0"
        }
        
        metadata_file = self.session_dir / "session_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        # Create LLM communication log file
        self.llm_log_file = self.session_dir / "llm_communication.log"
        with open(self.llm_log_file, 'w', encoding='utf-8') as f:
            f.write(f"=== LLM Communication Log ===\n")
            f.write(f"Session: {self.session_dir.name}\n")
            f.write(f"Started: {self.start_time.isoformat()}\n")
            f.write("=" * 50 + "\n\n")
        
        # Save session path for other tools (like web_viewer)
        current_session_file = self.base_dir / "current_session.txt"
        with open(current_session_file, 'w', encoding='utf-8') as f:
            f.write(self.session_dir.name)
    
    def log_api_call_start(
        self,
        player_name: str,
        prompt_number: int,
        iteration: int,
        prompt_content: Optional[str] = None,
        tools_schema: Optional[List[Dict]] = None,
        is_tool_followup: bool = False
    ) -> int:
        """
        Log the start of an API call to LLM. Returns the API call index.
        
        Args:
            player_name: Name of the player making the call
            prompt_number: The prompt number (within this player's session)
            iteration: Tool iteration number (1, 2, 3...)
            prompt_content: The prompt content being sent (for logging)
            tools_schema: The tools schema being sent with the call
            is_tool_followup: Whether this is a follow-up call after tool execution
            
        Returns:
            The global API call index assigned to this call
        """
        self.api_call_index += 1
        call_id = self.api_call_index
        
        # Track pending call
        self.pending_api_calls[call_id] = {
            "player_name": player_name,
            "prompt_number": prompt_number,
            "iteration": iteration,
            "start_time": datetime.now().isoformat(),
            "is_tool_followup": is_tool_followup
        }
        
        # Log to communication file
        call_type = "TOOL_FOLLOWUP" if is_tool_followup else "INITIAL"
        msg = f"📤 API Call #{call_id} SENT [{call_type}] - Player: {player_name}, Prompt: {prompt_number}, Iteration: {iteration}"
        self.log_llm_communication(msg, "API_SEND")
        
        # Log tools being sent
        if tools_schema:
            tool_names = [t.get("name", "unknown") for t in tools_schema]
            self.log_llm_communication(f"   🔧 Tools enabled: {tool_names}", "API_SEND")
        
        return call_id
    
    def log_api_call_end(
        self,
        call_id: int,
        success: bool,
        tokens: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        has_tool_calls: bool = False,
        tool_calls_count: int = 0,
        error: Optional[str] = None
    ) -> None:
        """
        Log the completion of an API call.
        
        Args:
            call_id: The API call index returned by log_api_call_start
            success: Whether the call succeeded
            tokens: Total tokens used
            prompt_tokens: Input tokens (for cost calculation)
            completion_tokens: Output tokens (for cost calculation)
            has_tool_calls: Whether the response includes tool calls
            tool_calls_count: Number of tool calls requested
            error: Error message if failed
        """
        # Get pending call info
        call_info = self.pending_api_calls.pop(call_id, {})
        player_name = call_info.get("player_name", "unknown")
        iteration = call_info.get("iteration", 0)
        
        if success:
            # Calculate cost
            input_cost = (prompt_tokens / 1_000_000) * GEMINI_FLASH_INPUT_PRICE
            output_cost = (completion_tokens / 1_000_000) * GEMINI_FLASH_OUTPUT_PRICE
            total_cost = input_cost + output_cost
            
            # Update cumulative totals
            self.cumulative_input_tokens += prompt_tokens
            self.cumulative_output_tokens += completion_tokens
            self.cumulative_cost += total_cost
            
            if has_tool_calls:
                msg = f"📥 API Call #{call_id} RECEIVED ✅ - {tokens} tokens (in:{prompt_tokens} out:{completion_tokens}), {tool_calls_count} tool request(s) | 💰 ${total_cost:.6f}"
            else:
                msg = f"📥 API Call #{call_id} RECEIVED ✅ - {tokens} tokens (in:{prompt_tokens} out:{completion_tokens}) (final response) | 💰 ${total_cost:.6f}"
            self.log_llm_communication(msg, "API_RECV")
            
            # Update cumulative summary at top of log file
            self._update_cumulative_header()
        else:
            msg = f"📥 API Call #{call_id} FAILED ❌ - Error: {error}"
            self.log_llm_communication(msg, "API_RECV")
        
        # Show pending calls status
        if self.pending_api_calls:
            pending_ids = list(self.pending_api_calls.keys())
            self.log_llm_communication(f"   ⏳ Still pending: API Call(s) {pending_ids}", "API_STATUS")
    
    def log_llm_communication(self, message: str, msg_type: str = "INFO") -> None:
        """
        Log a message to the LLM communication log file.
        
        Args:
            message: The message to log
            msg_type: Type of message (SEND, RECV, ERROR, INFO, API_SEND, API_RECV, API_STATUS)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{msg_type}] {message}\n"
        
        with open(self.llm_log_file, 'a', encoding='utf-8') as f:
            f.write(line)
            f.flush()  # Ensure immediate write
    
    def _update_cumulative_header(self) -> None:
        """
        Update the cumulative cost summary at the top of the log file.
        Rewrites the header section with updated totals.
        """
        import re
        
        # Read current content
        with open(self.llm_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find where the actual log entries start (lines starting with [HH:MM:SS])
        # Everything before that is header
        log_entry_match = re.search(r'^\[\d{2}:\d{2}:\d{2}\]', content, re.MULTILINE)
        if log_entry_match:
            log_content = content[log_entry_match.start():]
        else:
            log_content = ""
        
        # Create new header with cumulative totals
        new_header = f"""=== LLM Communication Log ===
Session: {self.session_dir.name}
Started: {self.start_time.isoformat()}
{'=' * 50}

💰 CUMULATIVE COST: ${self.cumulative_cost:.6f}
   Input:  {self.cumulative_input_tokens:,} tokens (${(self.cumulative_input_tokens / 1_000_000) * GEMINI_FLASH_INPUT_PRICE:.6f})
   Output: {self.cumulative_output_tokens:,} tokens (${(self.cumulative_output_tokens / 1_000_000) * GEMINI_FLASH_OUTPUT_PRICE:.6f})
{'=' * 50}

"""
        
        # Write updated file
        with open(self.llm_log_file, 'w', encoding='utf-8') as f:
            f.write(new_header + log_content)
    
    def _ensure_player_dirs(self, player_name: str) -> Dict[str, Path]:
        """
        Ensure directories exist for a player.
        
        Returns:
            Dict with 'root', 'prompts', 'responses', 'iterations', 'intermediate' paths
        """
        player_dir = self.session_dir / player_name
        prompts_dir = player_dir / "prompts"
        responses_dir = player_dir / "responses"
        iterations_dir = prompts_dir / "iterations"
        intermediate_dir = responses_dir / "intermediate"
        
        player_dir.mkdir(parents=True, exist_ok=True)
        prompts_dir.mkdir(exist_ok=True)
        responses_dir.mkdir(exist_ok=True)
        iterations_dir.mkdir(exist_ok=True)
        intermediate_dir.mkdir(exist_ok=True)
        
        return {
            "root": player_dir,
            "prompts": prompts_dir,
            "responses": responses_dir,
            "iterations": iterations_dir,
            "intermediate": intermediate_dir
        }
    
    def _get_request_number(self, player_name: str) -> int:
        """Get and increment request number for player."""
        if player_name not in self.request_counters:
            self.request_counters[player_name] = 0
        self.request_counters[player_name] += 1
        return self.request_counters[player_name]
    
    def log_prompt(
        self,
        player_name: str,
        prompt: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
        is_active: bool = True,
        what_happened: str = "",
        allowed_actions: Optional[List[Dict]] = None,
        tools_schema: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Log a prompt for a player.
        
        Args:
            player_name: Name of the player
            prompt: The prompt dictionary
            schema: Response schema (for reference)
            is_active: Whether this is an active turn prompt
            what_happened: Description of what happened
            allowed_actions: List of allowed actions
            tools_schema: List of tool schemas being sent with this prompt
            
        Returns:
            Dict with 'number', 'json_path', 'txt_path'
        """
        dirs = self._ensure_player_dirs(player_name)
        num = self._get_request_number(player_name)
        
        # Prepare full prompt document
        prompt_doc = {
            "request_number": num,
            "timestamp": datetime.now().isoformat(),
            "player_name": player_name,
            "is_active_turn": is_active,
            "prompt": prompt
        }
        
        if schema:
            prompt_doc["response_schema"] = schema
        if what_happened:
            prompt_doc["what_happened"] = what_happened
        if allowed_actions:
            prompt_doc["allowed_actions"] = allowed_actions
        if tools_schema:
            prompt_doc["tools_schema"] = tools_schema
        
        # Save JSON file
        json_path = dirs["prompts"] / f"prompt_{num}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(prompt_doc, f, indent=2, ensure_ascii=False)
        
        # Save TXT file (just the prompt content as string)
        txt_path = dirs["prompts"] / f"prompt_{num}.txt"
        prompt_str = json.dumps(prompt, indent=2, ensure_ascii=False)
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False) if schema else "N/A"
        
        # Format tools schema for TXT
        tools_str = "N/A"
        if tools_schema:
            tools_summary = []
            for tool in tools_schema:
                tool_name = tool.get("name", "unknown")
                tool_desc = tool.get("description", "")[:80]
                tools_summary.append(f"  - {tool_name}: {tool_desc}...")
            tools_str = "\n".join(tools_summary)
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"=== Prompt #{num} for {player_name} ===\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Active Turn: {is_active}\n")
            f.write(f"\n--- What Happened ---\n{what_happened}\n")
            f.write(f"\n--- Tools Available ---\n{tools_str}\n")
            f.write(f"\n--- Response Schema ---\n{schema_str}\n")
            f.write(f"\n--- Prompt Content ---\n{prompt_str}\n")
        
        # Update MD log
        self._append_prompt_to_md(player_name, num, prompt, is_active, what_happened, tools_schema)
        
        return {
            "number": num,
            "json_path": json_path,
            "txt_path": txt_path
        }
    
    def log_tool_followup_prompt(
        self,
        player_name: str,
        original_prompt_number: int,
        iteration: int,
        conversation_context: str,
        tool_results: str,
        tools_schema: Optional[List[Dict[str, Any]]] = None,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Log a follow-up prompt sent after tool execution.
        
        This creates a new prompt file that shows what was sent back to LLM
        after tool execution, including the tool results.
        
        Args:
            player_name: Name of the player
            original_prompt_number: The original request number
            iteration: Tool iteration number (2, 3, etc.)
            conversation_context: Full conversation context being sent
            tool_results: Formatted tool results string
            tools_schema: Tools still available (may be empty on last iteration)
            schema: Response schema
            
        Returns:
            Dict with 'path' to the saved file
        """
        dirs = self._ensure_player_dirs(player_name)
        
        # Create iterations subdirectory
        iterations_dir = dirs["prompts"] / "iterations"
        iterations_dir.mkdir(exist_ok=True)
        
        # Use naming like prompt_1_iter2.json
        filename = f"prompt_{original_prompt_number}_iter{iteration}"
        
        prompt_doc = {
            "original_request_number": original_prompt_number,
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "player_name": player_name,
            "type": "tool_followup",
            "tool_results": tool_results,
            "full_context_sent": conversation_context,
        }
        
        if tools_schema:
            prompt_doc["tools_schema"] = tools_schema
            prompt_doc["tools_enabled"] = True
        else:
            prompt_doc["tools_enabled"] = False
            
        if schema:
            prompt_doc["response_schema"] = schema
        
        # Save JSON in iterations folder
        json_path = iterations_dir / f"{filename}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(prompt_doc, f, indent=2, ensure_ascii=False)
        
        # Save TXT in iterations folder
        txt_path = iterations_dir / f"{filename}.txt"
        tools_enabled = "Yes" if tools_schema else "No (final iteration)"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"=== Tool Follow-up #{iteration} for Prompt #{original_prompt_number} ===\n")
            f.write(f"Player: {player_name}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Tools Enabled: {tools_enabled}\n")
            f.write(f"\n--- Tool Results Appended ---\n")
            f.write(tool_results)
            f.write(f"\n\n--- Full Context Sent to LLM ---\n")
            f.write(conversation_context[:5000])  # Truncate for readability
            if len(conversation_context) > 5000:
                f.write(f"\n... (truncated, full length: {len(conversation_context)} chars)")
        
        # Update MD log
        self._append_tool_followup_to_md(player_name, original_prompt_number, iteration, tool_results)
        
        return {
            "path": json_path,
            "txt_path": txt_path
        }

    def log_intermediate_response(
        self,
        player_name: str,
        request_number: int,
        iteration: int,
        response: LLMResponse
    ) -> Path:
        """
        Log an intermediate response from the LLM (when it requests tools).
        
        Args:
            player_name: Name of the player
            request_number: The request number this responds to
            iteration: The iteration number (1, 2, etc.)
            response: The LLMResponse object with tool_calls
            
        Returns:
            Path to the intermediate response JSON file
        """
        dirs = self._ensure_player_dirs(player_name)
        
        # Prepare intermediate response document
        response_doc = {
            "request_number": request_number,
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "player_name": player_name,
            "type": "intermediate",
            "success": response.success,
            "raw_content": response.content,
            "has_tool_calls": bool(response.tool_calls),
            "tool_calls": response.tool_calls if response.tool_calls else [],
            "model": response.model,
            "tokens": {
                "prompt": response.prompt_tokens,
                "completion": response.completion_tokens,
                "thinking": response.thinking_tokens if hasattr(response, 'thinking_tokens') else 0,
                "total": response.total_tokens
            },
            "latency_seconds": response.latency_seconds,
            "error": response.error
        }
        
        # Save JSON file in intermediate directory
        json_path = dirs["intermediate"] / f"response_{request_number}_iter{iteration}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(response_doc, f, indent=2, ensure_ascii=False)
        
        return json_path
    
    def log_response(
        self,
        player_name: str,
        request_number: int,
        response: LLMResponse,
        parsed: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Log a response from the LLM.
        
        Args:
            player_name: Name of the player
            request_number: The request number this responds to
            response: The LLMResponse object
            parsed: Parsed response data
            
        Returns:
            Path to the response JSON file
        """
        dirs = self._ensure_player_dirs(player_name)
        
        # Prepare response document
        response_doc = {
            "request_number": request_number,
            "timestamp": datetime.now().isoformat(),
            "player_name": player_name,
            "type": "final",
            "success": response.success,
            "raw_content": response.content,
            "parsed": parsed,
            "model": response.model,
            "tokens": {
                "prompt": response.prompt_tokens,
                "completion": response.completion_tokens,
                "thinking": response.thinking_tokens if hasattr(response, 'thinking_tokens') else 0,
                "total": response.total_tokens
            },
            "latency_seconds": response.latency_seconds,
            "error": response.error
        }
        
        # Save JSON file
        json_path = dirs["responses"] / f"response_{request_number}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(response_doc, f, indent=2, ensure_ascii=False)
        
        # Update MD log
        self._append_response_to_md(player_name, request_number, response, parsed)
        
        return json_path
    
    def _init_player_md(self, player_name: str, model: str = "gemini-2.0-flash") -> None:
        """Initialize MD file for a player."""
        dirs = self._ensure_player_dirs(player_name)
        md_path = dirs["root"] / f"{player_name}.md"
        
        if md_path.exists():
            return  # Already initialized
        
        header = f"""# AI Agent Log: {player_name}

**Session:** {self.session_dir.name}  
**Started:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}  
**Model:** {model}

---

"""
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(header)
    
    def _append_prompt_to_md(
        self,
        player_name: str,
        num: int,
        prompt: Dict[str, Any],
        is_active: bool,
        what_happened: str,
        tools_schema: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Append prompt section to MD file."""
        dirs = self._ensure_player_dirs(player_name)
        md_path = dirs["root"] / f"{player_name}.md"
        
        # Initialize if needed
        if not md_path.exists():
            self._init_player_md(player_name)
        
        turn_type = "🎯 ACTIVE TURN" if is_active else "👀 OBSERVING"
        
        # Format tools info
        tools_info = ""
        if tools_schema:
            tool_names = [t.get("name", "unknown") for t in tools_schema]
            tools_info = f"\n**Tools:** {', '.join(tool_names)}\n"
        
        section = f"""
## Request #{num} - {turn_type}

**Time:** {datetime.now().strftime('%H:%M:%S')}{tools_info}

### What Happened
{what_happened if what_happened else "(No events)"}

### Prompt Sent
See: [prompt_{num}.json](prompts/prompt_{num}.json)

"""
        with open(md_path, 'a', encoding='utf-8') as f:
            f.write(section)
    
    def _append_tool_followup_to_md(
        self,
        player_name: str,
        original_prompt_number: int,
        iteration: int,
        tool_results: str
    ) -> None:
        """Append tool follow-up section to MD file."""
        dirs = self._ensure_player_dirs(player_name)
        md_path = dirs["root"] / f"{player_name}.md"
        
        section = f"""
### 🔧 Tool Follow-up (Iteration {iteration})

**Time:** {datetime.now().strftime('%H:%M:%S')}

**Tool Results:**
```
{tool_results}
```

See: [prompt_{original_prompt_number}_iter{iteration}.json](prompts/iterations/prompt_{original_prompt_number}_iter{iteration}.json)

"""
        with open(md_path, 'a', encoding='utf-8') as f:
            f.write(section)

    def _append_response_to_md(
        self,
        player_name: str,
        num: int,
        response: LLMResponse,
        parsed: Optional[Dict[str, Any]]
    ) -> None:
        """Append response section to MD file."""
        dirs = self._ensure_player_dirs(player_name)
        md_path = dirs["root"] / f"{player_name}.md"
        
        if response.success and parsed:
            # Extract key fields
            thinking = parsed.get("internal_thinking", "N/A")
            note = parsed.get("note_to_self", "")
            say = parsed.get("say_outloud", "")
            
            # Handle both action formats: old (action object) and new (action_type + parameters)
            action_type = parsed.get("action_type") or (parsed.get("action", {}).get("type") if parsed.get("action") else None)
            action_params = parsed.get("parameters") or (parsed.get("action", {}).get("parameters") if parsed.get("action") else None)
            
            action_str = ""
            if action_type:
                action_str = f"**{action_type}**"
                if action_params:
                    action_str += f" - {json.dumps(action_params)}"
            
            # Calculate cost
            input_cost = (response.prompt_tokens / 1_000_000) * GEMINI_FLASH_INPUT_PRICE
            output_cost = (response.completion_tokens / 1_000_000) * GEMINI_FLASH_OUTPUT_PRICE
            total_cost = input_cost + output_cost
            
            section = f"""### Response Received ✅

**Latency:** {response.latency_seconds:.2f}s | **Tokens:** {response.total_tokens} (in:{response.prompt_tokens} out:{response.completion_tokens}) | **Cost:** ${total_cost:.6f}

**Thinking:** {thinking}

"""
            if note:
                section += f"**Note to Self:** {note}\n\n"
            if say:
                section += f'**Says:** "{say}"\n\n'
            if action_str:
                section += f"**Action:** {action_str}\n\n"
            
        else:
            # Error response
            section = f"""### Response Failed ❌

**Error:** {response.error or 'Unknown error'}
**Latency:** {response.latency_seconds:.2f}s

"""
        
        section += "---\n"
        
        with open(md_path, 'a', encoding='utf-8') as f:
            f.write(section)
    
    def log_chat(self, from_player: str, message: str, to_player: Optional[str] = None) -> None:
        """
        Log a chat message.
        
        Args:
            from_player: Player who sent the message
            message: The chat message
            to_player: Target player (None = broadcast)
        """
        chat_file = self.session_dir / "chat_history.json"
        
        # Load existing chat
        chat_data = {"messages": []}
        if chat_file.exists():
            with open(chat_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Support both formats: {"messages": [...]} or [...]
                if isinstance(loaded, dict):
                    chat_data = loaded
                else:
                    chat_data = {"messages": loaded}
        
        # Add new message
        chat_data["messages"].append({
            "timestamp": datetime.now().isoformat(),
            "from": from_player,
            "to": to_player or "all",
            "message": message
        })
        
        # Save (wrapped in object for viewer)
        with open(chat_file, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, indent=2, ensure_ascii=False)
    
    def save_agent_memories(self, agents: Dict[str, Any]) -> None:
        """
        Save current agent memories to file (for real-time web viewer updates).
        
        Args:
            agents: Dictionary of AgentState objects
        """
        memories = {}
        for name, agent in agents.items():
            if hasattr(agent, 'memory') and agent.memory:
                memories[name] = {
                    "note_to_self": agent.memory,
                    "last_updated": datetime.now().isoformat()
                }
        
        memory_file = self.session_dir / "agent_memories.json"
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump(memories, f, indent=2, ensure_ascii=False)
    
    def log_error(self, player_name: str, error: str, context: Optional[Dict] = None) -> None:
        """Log an error for a player."""
        dirs = self._ensure_player_dirs(player_name)
        md_path = dirs["root"] / f"{player_name}.md"
        
        section = f"""
### ⚠️ Error

**Time:** {datetime.now().strftime('%H:%M:%S')}
**Error:** {error}

"""
        if context:
            section += f"**Context:** {json.dumps(context, indent=2)}\n\n"
        
        section += "---\n"
        
        with open(md_path, 'a', encoding='utf-8') as f:
            f.write(section)
    
    def save_session_summary(self, agents: Dict[str, Any], game_state: Optional[Dict] = None) -> None:
        """
        Save session summary at the end.
        
        Args:
            agents: Dictionary of AgentState objects
            game_state: Final game state
        """
        summary = {
            "session_id": self.session_dir.name,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "agents": {
                name: agent.to_dict() if hasattr(agent, 'to_dict') else str(agent)
                for name, agent in agents.items()
            }
        }
        
        if game_state:
            summary["final_game_state"] = game_state
        
        summary_file = self.session_dir / "session_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # Save agent memories separately for web viewer
        memories = {}
        for name, agent in agents.items():
            if hasattr(agent, 'memory') and agent.memory:
                memories[name] = agent.memory
        
        if memories:
            memory_file = self.session_dir / "agent_memories.json"
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memories, f, indent=2, ensure_ascii=False)
    
    def get_session_path(self) -> Path:
        """Get the session directory path."""
        return self.session_dir
    
    def get_player_log_path(self, player_name: str) -> Path:
        """Get the MD log path for a player."""
        return self.session_dir / player_name / f"{player_name}.md"
    
    def log_tool_execution(self, batch) -> None:
        """
        Log tool execution batch with detailed information.
        
        Args:
            batch: ToolExecutionBatch object with tool call results
        """
        # Log to communication file
        self.log_llm_communication(
            f"=== Tool Execution Batch ({batch.total_calls} calls) ===",
            "TOOL"
        )
        
        for call in batch.tool_calls:
            status = "✅" if call.success else "❌"
            
            # Extract reasoning if present
            reasoning = call.parameters.get("reasoning", "")
            params_without_reasoning = {k: v for k, v in call.parameters.items() if k != "reasoning"}
            
            self.log_llm_communication(
                f"  {status} {call.name}({json.dumps(params_without_reasoning)})",
                "TOOL"
            )
            
            if reasoning:
                self.log_llm_communication(
                    f"     💭 Reasoning: {reasoning}",
                    "TOOL"
                )
            
            self.log_llm_communication(
                f"     Time: {call.execution_time*1000:.1f}ms | "
                f"Tokens: {call.input_tokens} in + {call.output_tokens} out = {call.input_tokens + call.output_tokens} total",
                "TOOL"
            )
            
            if call.success:
                # Log abbreviated result (without reasoning field)
                result = call.result.copy() if isinstance(call.result, dict) else call.result
                if isinstance(result, dict) and "llm_reasoning" in result:
                    result.pop("llm_reasoning")
                result_str = json.dumps(result, ensure_ascii=False)
                if len(result_str) > 200:
                    result_str = result_str[:200] + "..."
                self.log_llm_communication(f"     Result: {result_str}", "TOOL")
            else:
                self.log_llm_communication(f"     Error: {call.error}", "TOOL")
        
        # Summary
        self.log_llm_communication(
            f"  Total: {batch.success_count}/{batch.total_calls} successful | "
            f"{batch.total_tokens} tokens | {batch.total_time*1000:.1f}ms",
            "TOOL"
        )
        self.log_llm_communication("=" * 50, "TOOL")
        
        # Save detailed tool execution to separate file
        tool_log_file = self.session_dir / "tool_executions.json"
        
        # Load existing logs
        tool_logs = []
        if tool_log_file.exists():
            with open(tool_log_file, 'r', encoding='utf-8') as f:
                tool_logs = json.load(f)
        
        # Add new batch
        tool_logs.append(batch.to_dict())
        
        # Save updated logs
        with open(tool_log_file, 'w', encoding='utf-8') as f:
            json.dump(tool_logs, f, indent=2, ensure_ascii=False)
