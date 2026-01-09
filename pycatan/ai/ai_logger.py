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
    
    def log_llm_communication(self, message: str, msg_type: str = "INFO") -> None:
        """
        Log a message to the LLM communication log file.
        
        Args:
            message: The message to log
            msg_type: Type of message (SEND, RECV, ERROR, INFO)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{msg_type}] {message}\n"
        
        with open(self.llm_log_file, 'a', encoding='utf-8') as f:
            f.write(line)
            f.flush()  # Ensure immediate write
    
    def _ensure_player_dirs(self, player_name: str) -> Dict[str, Path]:
        """
        Ensure directories exist for a player.
        
        Returns:
            Dict with 'root', 'prompts', 'responses' paths
        """
        player_dir = self.session_dir / player_name
        prompts_dir = player_dir / "prompts"
        responses_dir = player_dir / "responses"
        
        player_dir.mkdir(parents=True, exist_ok=True)
        prompts_dir.mkdir(exist_ok=True)
        responses_dir.mkdir(exist_ok=True)
        
        return {
            "root": player_dir,
            "prompts": prompts_dir,
            "responses": responses_dir
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
        allowed_actions: Optional[List[Dict]] = None
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
        
        # Save JSON file
        json_path = dirs["prompts"] / f"prompt_{num}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(prompt_doc, f, indent=2, ensure_ascii=False)
        
        # Save TXT file (just the prompt content as string)
        txt_path = dirs["prompts"] / f"prompt_{num}.txt"
        prompt_str = json.dumps(prompt, indent=2, ensure_ascii=False)
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False) if schema else "N/A"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"=== Prompt #{num} for {player_name} ===\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Active Turn: {is_active}\n")
            f.write(f"\n--- What Happened ---\n{what_happened}\n")
            f.write(f"\n--- Response Schema ---\n{schema_str}\n")
            f.write(f"\n--- Prompt Content ---\n{prompt_str}\n")
        
        # Update MD log
        self._append_prompt_to_md(player_name, num, prompt, is_active, what_happened)
        
        return {
            "number": num,
            "json_path": json_path,
            "txt_path": txt_path
        }
    
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
            "success": response.success,
            "raw_content": response.content,
            "parsed": parsed,
            "model": response.model,
            "tokens": {
                "prompt": response.prompt_tokens,
                "completion": response.completion_tokens,
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
        what_happened: str
    ) -> None:
        """Append prompt section to MD file."""
        dirs = self._ensure_player_dirs(player_name)
        md_path = dirs["root"] / f"{player_name}.md"
        
        # Initialize if needed
        if not md_path.exists():
            self._init_player_md(player_name)
        
        turn_type = "🎯 ACTIVE TURN" if is_active else "👀 OBSERVING"
        
        section = f"""
## Request #{num} - {turn_type}

**Time:** {datetime.now().strftime('%H:%M:%S')}

### What Happened
{what_happened if what_happened else "(No events)"}

### Prompt Sent
See: [prompt_{num}.json](prompts/prompt_{num}.json)

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
            action = parsed.get("action", {})
            
            action_str = ""
            if action:
                action_str = f"**{action.get('type', 'unknown')}**"
                params = action.get("parameters", {})
                if params:
                    action_str += f" - {json.dumps(params)}"
            
            section = f"""### Response Received ✅

**Latency:** {response.latency_seconds:.2f}s | **Tokens:** {response.total_tokens}

**Thinking:** {thinking[:200]}{'...' if len(thinking) > 200 else ''}

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
