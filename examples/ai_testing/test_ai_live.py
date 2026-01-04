"""
AI Agent Live Testing - Watch AI Think and Respond!
---------------------------------------------------

This script:
1. Monitors for new prompts generated during gameplay
2. Sends prompts to Gemini AI for each player
3. Displays the AI's thinking and decisions in real-time
4. Saves chat messages and memories
5. Waits for you to execute moves manually

Setup:
- Run play_with_prompts.py to start a game
- This script will automatically process AI responses
"""

import sys
import json
import time
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import our AI components
from pycatan.ai.llm_client import GeminiClient, LLMResponse
from pycatan.ai.response_parser import ResponseParser, ParseResult
from pycatan.ai.schemas import ResponseType

# Import request tracker
from examples.ai_testing.request_tracker import RequestTracker


# ============================================================================
# Configuration
# ============================================================================

GEMINI_API_KEY = "AIzaSyAAdbl5LtljM8PGy5iqChAP70cn9Ua35p0"
GEMINI_MODEL = "models/gemini-2.5-flash"  # As requested by user

LOGS_DIR = Path("examples/ai_testing/my_games/ai_logs")

# Make sure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Data Management
# ============================================================================

class ChatManager:
    """Manages chat history between players."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.messages: List[Dict[str, Any]] = []
        self.load()
    
    def load(self):
        """Load chat history from file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.messages = data.get("messages", [])
                print(f"✅ Loaded {len(self.messages)} chat messages")
            except Exception as e:
                print(f"⚠️  Could not load chat history: {e}")
                self.messages = []
    
    def add_message(self, player: str, message: str):
        """Add a new chat message."""
        # Use simple incrementing message number instead of timestamp
        msg_num = len(self.messages) + 1
        self.messages.append({
            "msg": msg_num,
            "player": player,
            "message": message
        })
        self.save()
        print(f"💬 {player}: {message}")
    
    def save(self):
        """Save chat history to file."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump({"messages": self.messages}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Failed to save chat history: {e}")
    
    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages."""
        return self.messages[-limit:] if self.messages else []


class MemoryManager:
    """Manages agent memories (note_to_self)."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.memories: Dict[str, str] = {}
        self.load()
    
    def load(self):
        """Load memories from file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.memories = json.load(f)
                print(f"✅ Loaded memories for {len(self.memories)} agents")
            except Exception as e:
                print(f"⚠️  Could not load memories: {e}")
                self.memories = {}
    
    def update_memory(self, player: str, note: str):
        """Update agent's memory."""
        self.memories[player] = note
        self.save()
        print(f"📝 {player} updated memory: {note[:50]}...")
    
    def get_memory(self, player: str) -> Optional[str]:
        """Get agent's current memory."""
        return self.memories.get(player)
    
    def save(self):
        """Save memories to file."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.memories, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Failed to save memories: {e}")


# ============================================================================
# AI Response Handler
# ============================================================================

class AITester:
    """Handles AI testing - sends prompts and displays responses."""
    
    def __init__(self, session_dir: Path):
        self.llm_client = GeminiClient(
            model=GEMINI_MODEL,
            api_key=GEMINI_API_KEY,
            temperature=0.8,
            response_format="json"
        )
        self.parser = ResponseParser(enable_fallbacks=True, strict_mode=False)
        
        # Create chat and memory files INSIDE the session directory
        session_chat_file = session_dir / "chat_history.json"
        session_memory_file = session_dir / "agent_memories.json"
        
        self.chat_manager = ChatManager(session_chat_file)
        self.memory_manager = MemoryManager(session_memory_file)
        self.request_tracker = RequestTracker(session_dir)
        self.session_dir = session_dir
        self.player_logs = {}  # Will store file handles per player
        self.consecutive_failures = 0  # Track consecutive failures
        self.max_consecutive_failures = 5  # Stop after 5 failures in a row
        
        # NEW: Track active requests and previous game state
        self.active_requests: Set[str] = set()  # Player names with active requests
        self.active_requests_lock = threading.Lock()
        self.previous_game_state: Optional[Dict[str, Any]] = None
        self.previous_chat_count: int = 0
        
        print(f"🤖 AI Tester initialized with model: {GEMINI_MODEL}")
        print(f"📁 Session logs: {session_dir}")
        print(f"💬 Chat history: {session_chat_file}")
        print(f"📝 Agent memories: {session_memory_file}")
    
    def _get_player_log_file(self, player_name: str) -> Path:
        """Get or create log file for specific player."""
        if player_name not in self.player_logs:
            log_file = self.session_dir / f"player_{player_name}.md"
            self.player_logs[player_name] = log_file
            
            # Write Markdown header
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"# 🤖 AI Agent Log - Player {player_name.upper()}\n\n")
                f.write(f"---\n\n")
                f.write(f"**Session:** `{self.session_dir.name}`\n\n")
                f.write(f"**Model:** `{GEMINI_MODEL}`\n\n")
                f.write(f"**Started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"---\n\n")
        
        return self.player_logs[player_name]
    
    def _log_to_player_file(self, player_name: str, text: str):
        """Write text to player's log file."""
        try:
            log_file = self._get_player_log_file(player_name)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(text + '\n')
        except Exception as e:
            pass
    
    def _log_structured_response(self, player_name: str, data: Dict[str, Any]):
        """Format and log AI response in a beautiful structured way."""
        self._log_to_player_file(player_name, "\n### 🎯 AI Response\n")
        
        # Internal Thinking
        if "internal_thinking" in data and data["internal_thinking"]:
            self._log_to_player_file(player_name, "#### 💭 Internal Thinking\n")
            self._log_to_player_file(player_name, f"> {data['internal_thinking']}\n")
        
        # Note to Self
        if "note_to_self" in data and data["note_to_self"]:
            self._log_to_player_file(player_name, "#### 📝 Note to Self\n")
            self._log_to_player_file(player_name, f"*\"{data['note_to_self']}\"*\n")
        
        # Say Out Loud (Chat)
        if "say_outloud" in data and data["say_outloud"]:
            self._log_to_player_file(player_name, "#### 💬 Says Out Loud\n")
            self._log_to_player_file(player_name, f"**\"{data['say_outloud']}\"**\n")
        
        # Action
        if "action" in data and data["action"]:
            self._log_to_player_file(player_name, "#### 🎮 Action\n")
            action = data["action"]
            self._log_to_player_file(player_name, f"- **Type:** `{action.get('type', 'N/A')}`\n")
            if action.get("parameters"):
                self._log_to_player_file(player_name, f"- **Parameters:** `{action['parameters']}`\n")
        
        # Raw JSON in collapsible section for debugging
        self._log_to_player_file(player_name, "\n<details>")
        self._log_to_player_file(player_name, "<summary><strong>🔍 Raw JSON (Debug)</strong></summary>\n")
        self._log_to_player_file(player_name, "```json")
        self._log_to_player_file(player_name, json.dumps(data, indent=2, ensure_ascii=False))
        self._log_to_player_file(player_name, "```")
        self._log_to_player_file(player_name, "</details>\n")
    
    def _check_for_changes(self, response_data: Dict[str, Any]):
        """
        Check if the response caused changes in game state or chat.
        If yes, trigger prompt regeneration with updated context.
        """
        try:
            # Load current game state
            state_file = Path('examples/ai_testing/my_games/current_state.json')
            if not state_file.exists():
                return
            
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                current_state = data.get('state', {})
            
            # Check for game state changes
            game_changed = False
            chat_changed = False
            
            if self.previous_game_state:
                # Compare relevant fields that indicate game changes
                prev_phase = self.previous_game_state.get('current_phase', '')
                curr_phase = current_state.get('current_phase', '')
                
                prev_player = self.previous_game_state.get('current_player', '')
                curr_player = current_state.get('current_player', '')
                
                prev_settlements = len(self.previous_game_state.get('settlements', []))
                curr_settlements = len(current_state.get('settlements', []))
                
                prev_roads = len(self.previous_game_state.get('roads', []))
                curr_roads = len(current_state.get('roads', []))
                
                prev_dice = self.previous_game_state.get('dice_result', '')
                curr_dice = current_state.get('dice_result', '')
                
                # Detect game changes
                if (prev_phase != curr_phase or prev_player != curr_player or 
                    prev_settlements != curr_settlements or prev_roads != curr_roads or
                    prev_dice != curr_dice):
                    game_changed = True
                    print("🎲 Game state changed detected!")
            
            # Check for chat changes
            current_chat_count = len(self.chat_manager.messages)
            if current_chat_count > self.previous_chat_count:
                chat_changed = True
                print("💬 New chat message detected!")
            
            # Update tracking variables
            self.previous_game_state = current_state.copy() if current_state else None
            self.previous_chat_count = current_chat_count
            
            # If changes detected, trigger regeneration of prompts
            if game_changed or chat_changed:
                change_type = "game state" if game_changed else "chat"
                print(f"🔄 Detected {change_type} change - regenerating prompts...")
                print(f"   Note: Only players without active requests will be sent new prompts")
                self._trigger_prompt_regeneration()
                
        except Exception as e:
            print(f"⚠️  Error checking for changes: {e}")
    
    def _trigger_prompt_regeneration(self):
        """Trigger regeneration of prompts by calling generate_prompts script."""
        try:
            from examples.ai_testing.generate_prompts_from_state import main as generate_prompts
            generate_prompts()
        except Exception as e:
            print(f"⚠️  Could not trigger prompt regeneration: {e}")
    
    def process_prompt(self, prompt_file: Path, executor: Optional[ThreadPoolExecutor] = None) -> Optional[Dict[str, Any]]:
        """
        Process a single prompt file.
        
        Args:
            prompt_file: Path to prompt file
            executor: Optional thread pool executor for parallel processing
            
        Returns:
            Processed response data or None if failed
        """
        # Extract player name from filename (e.g., "prompt_player_a.txt" -> "a")
        player_name = prompt_file.stem.replace("prompt_player_", "")
        
        # Check if player already has an active request
        with self.active_requests_lock:
            if player_name in self.active_requests:
                print(f"🚫 Skipping {player_name} - already has active request")
                return None
            self.active_requests.add(player_name)
        
        separator = "="*80
        header = f"🤖 PROCESSING AI AGENT - Player {player_name.upper()}"
        
        print(separator)
        print(header)
        print(separator)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        request_num = len([k for k in self.player_logs.keys() if player_name in str(k)]) + 1
        
        # Use JSON file instead of TXT for actual prompt
        json_file = prompt_file.with_suffix('.json')
        if not json_file.exists():
            print(f"❌ JSON prompt file not found: {json_file}")
            return None
        
        # Read prompt JSON file directly
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                prompt_json = json.load(f)
        except Exception as e:
            print(f"❌ Failed to read JSON prompt file: {e}")
            return None
        
        # Extract the actual prompt (the nested 'prompt' field)
        actual_prompt = prompt_json.get("prompt", prompt_json)
        
        # Extract game context for tracking
        task_context = actual_prompt.get("task_context", {})
        meta_data = actual_prompt.get("meta_data", {})
        trigger = task_context.get("what_just_happened", "Unknown trigger")
        
        # Try to extract game phase from game_state
        game_state_str = actual_prompt.get("game_state", "")
        game_phase = "Unknown"
        current_player_in_game = "Unknown"
        
        # Parse meta from game_state if it contains JSON
        if '"meta"' in game_state_str or '"Meta"' in game_state_str:
            try:
                # Try to find and parse the game state JSON
                import re
                json_match = re.search(r'\{.*"meta".*\}', game_state_str, re.DOTALL)
                if json_match:
                    state_data = json.loads(json_match.group())
                    meta = state_data.get("meta", {})
                    game_phase = meta.get("phase", "Unknown")
                    current_player_in_game = meta.get("curr", "Unknown")
            except:
                pass
        
        # Create request in tracker
        request_id = self.request_tracker.add_request(
            player_name=player_name,
            trigger=trigger,
            game_phase=game_phase,
            current_player=current_player_in_game,
            prompt_data=actual_prompt,
            response_data=None,
            metadata={
                "request_num": request_num,
                "timestamp": timestamp,
                "model": GEMINI_MODEL
            }
        )
        
        print(f"📋 Request tracked: {request_id}")
        
        # Display prompt info
        print(f"📤 Sending prompt to Gemini...")
        print(f"   Model: {GEMINI_MODEL}")
        print(f"   Player: {player_name}")
        print(f"   Trigger: {trigger[:60]}{'...' if len(trigger) > 60 else ''}")
        
        # Write Markdown formatted log
        self._log_to_player_file(player_name, f"\n## 🔄 Request #{request_num}\n")
        self._log_to_player_file(player_name, f"**Timestamp:** {timestamp}\n\n")
        
        # Add schema section
        response_schema = prompt_json.get("response_schema", {})
        self._log_to_player_file(player_name, "<details>")
        self._log_to_player_file(player_name, "<summary><strong>📋 Expected Response Schema</strong></summary>\n")
        self._log_to_player_file(player_name, "```json")
        self._log_to_player_file(player_name, json.dumps(response_schema, indent=2, ensure_ascii=False))
        self._log_to_player_file(player_name, "```")
        self._log_to_player_file(player_name, "</details>\n")
        
        # Add prompt sent section
        self._log_to_player_file(player_name, "<details>")
        self._log_to_player_file(player_name, "<summary><strong>📤 Prompt Sent to Gemini</strong></summary>\n")
        self._log_to_player_file(player_name, "```json")
        self._log_to_player_file(player_name, json.dumps(actual_prompt, indent=2, ensure_ascii=False))
        self._log_to_player_file(player_name, "```")
        self._log_to_player_file(player_name, "</details>\n")
        
        # Send to LLM (schema is already in correct format from prompt_templates.py)
        start_time = time.time()
        llm_response = self.llm_client.generate_with_retry(
            prompt=json.dumps(actual_prompt),
            max_retries=3,
            response_schema=response_schema
        )
        
        if not llm_response.success:
            error_msg = f"❌ LLM request failed: {llm_response.error}"
            print(error_msg)
            self._log_to_player_file(player_name, f"\n{error_msg}")
            
            # Track consecutive failures
            self.consecutive_failures += 1
            
            # If it's a schema error, stop immediately to prevent repeated failures
            if "Unknown field for Schema" in str(llm_response.error):
                print("\n" + "="*80)
                print("🛑 CRITICAL ERROR: Schema validation failed!")
                print(f"Error: {llm_response.error}")
                print("The response schema contains fields that Gemini doesn't support.")
                print("Gemini only supports: type, properties, required, description, items, enum")
                print("Stopping to prevent repeated failures.")
                print("="*80 + "\n")
                raise RuntimeError("Schema validation error - stopping")
            
            return None
        
        # Reset failure counter on success
        self.consecutive_failures = 0
        
        print(f"✅ Response received ({llm_response.latency_seconds:.2f}s)")
        print(f"   Tokens: {llm_response.total_tokens} (prompt: {llm_response.prompt_tokens}, completion: {llm_response.completion_tokens})")
        
        # Log response metadata
        self._log_to_player_file(player_name, "\n### ✅ Response Received\n")
        self._log_to_player_file(player_name, f"- **Latency:** {llm_response.latency_seconds:.2f}s")
        self._log_to_player_file(player_name, f"- **Tokens:** {llm_response.total_tokens} (prompt: {llm_response.prompt_tokens}, completion: {llm_response.completion_tokens})\n")
        
        # Log raw response
        self._log_to_player_file(player_name, "<details>")
        self._log_to_player_file(player_name, "<summary><strong>📥 Raw Response from Gemini</strong></summary>\n")
        self._log_to_player_file(player_name, "```json")
        self._log_to_player_file(player_name, llm_response.content)
        self._log_to_player_file(player_name, "```")
        self._log_to_player_file(player_name, "</details>\n")
        
        # Determine response type based on whether action is expected
        constraints = actual_prompt.get("constraints", {})
        allowed_actions = constraints.get("allowed_actions", [])
        
        # If there are allowed actions, expect ACTIVE_TURN response (with action field)
        # Otherwise, expect OBSERVING response (just thinking)
        response_type = ResponseType.ACTIVE_TURN if allowed_actions else ResponseType.OBSERVING
        
        print(f"📋 Expected response type: {response_type.value}")
        
        # Parse response
        parse_result = self.parser.parse(llm_response.content, response_type)
        
        if not parse_result.success:
            error_msg = f"❌ Failed to parse response: {parse_result.error_message}"
            print(error_msg)
            print(f"Raw response: {llm_response.content[:500]}...")
            self._log_to_player_file(player_name, f"\n### ❌ Parse Error\n")
            self._log_to_player_file(player_name, f"**Error:** {parse_result.error_message}\n")
            self._log_to_player_file(player_name, f"**Raw response preview:** `{llm_response.content[:500]}...`\n")
            return None
        
        print("✅ Response parsed successfully")
        self._log_to_player_file(player_name, "\n### ✅ Parse Success\n")
        
        # Update request tracker with response (including raw response)
        self.request_tracker.update_response(
            request_id=request_id,
            response_data=parse_result.data,
            raw_response=llm_response.content,  # Save raw response from LLM
            metadata={
                "latency_seconds": llm_response.latency_seconds,
                "total_tokens": llm_response.total_tokens,
                "prompt_tokens": llm_response.prompt_tokens,
                "completion_tokens": llm_response.completion_tokens,
                "parse_success": True
            }
        )
        
        # Display structured response
        self._log_structured_response(player_name, parse_result.data)
        
        # Display the response
        self._display_response(player_name, parse_result.data, llm_response)
        
        # Handle chat and memory
        if "say_outloud" in parse_result.data and parse_result.data["say_outloud"]:
            self.chat_manager.add_message(player_name, parse_result.data["say_outloud"])
        
        if "note_to_self" in parse_result.data and parse_result.data["note_to_self"]:
            self.memory_manager.update_memory(player_name, parse_result.data["note_to_self"])
        
        # Remove from active requests when done
        with self.active_requests_lock:
            self.active_requests.discard(player_name)
        
        # Check for changes and trigger regeneration if needed
        self._check_for_changes(parse_result.data)
        
        return parse_result.data
    
    def _display_response(self, player: str, data: Dict[str, Any], llm_response: LLMResponse):
        """Display the parsed response in a nice format."""
        print("\n" + "="*80)
        print(f"🎯 AI RESPONSE - Player {player.upper()}")
        print("="*80)
        
        # Display thinking
        if "internal_thinking" in data:
            print(f"\n💭 Internal Thinking:")
            print(f"   {data['internal_thinking'][:200]}...")
        
        # Display note to self
        if "note_to_self" in data and data["note_to_self"]:
            print(f"\n📝 Note to Self:")
            print(f"   {data['note_to_self']}")
        
        # Display say outloud
        if "say_outloud" in data and data["say_outloud"]:
            print(f"\n💬 Says Out Loud:")
            print(f"   \"{data['say_outloud']}\"")
        
        # Display action
        if "action" in data:
            print(f"\n🎮 Action:")
            print(f"   Type: {data['action'].get('type', 'N/A')}")
            if data['action'].get('parameters'):
                print(f"   Parameters: {data['action']['parameters']}")
        
        print("\n" + "="*80 + "\n")
    
    def get_stats(self):
        """Display statistics."""
        stats = self.llm_client.get_stats()
        print("\n" + "="*80)
        print("📊 AI TESTER STATISTICS")
        print("="*80)
        for key, value in stats.items():
            print(f"   {key}: {value}")
        print("="*80 + "\n")


# ============================================================================
# Main Monitoring Loop
# ============================================================================

def get_or_create_session():
    """Always create a new session for each run."""
    # Use same path as generate_prompts_from_state.py
    current_session_file = Path("examples/ai_testing/my_games/current_session.txt")
    
    # Always create NEW session - don't reuse old ones
    # This prevents picking up old prompts as "new"
    session_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = LOGS_DIR / f"session_{session_time}"
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # Save current session path for other scripts to find
    # Write with flush to ensure it's immediately visible
    with open(current_session_file, 'w') as f:
        f.write(str(session_dir.absolute()))
        f.flush()
    
    print(f"📂 Created new session: {session_dir.name}")
    print(f"📄 Session file: {current_session_file.absolute()}")
    return session_dir


def monitor_prompts():
    """Monitor for new prompts and process them in parallel."""
    session_dir = get_or_create_session()
    
    # Create prompts directory inside session
    prompts_dir = session_dir / 'prompts'
    prompts_dir.mkdir(exist_ok=True)
    
    tester = AITester(session_dir)
    processed_files = {}  # Dictionary: filename -> content hash when processed
    retry_counts = {}  # Dictionary: filename -> number of retry attempts
    MAX_RETRIES = 3
    
    # Thread pool for parallel processing
    executor = ThreadPoolExecutor(max_workers=4)
    
    print("="*80)
    print("🎮 AI AGENT LIVE TESTER (PARALLEL MODE)")
    print("="*80)
    print(f"📁 Watching: {prompts_dir}")
    print(f"🤖 Model: {GEMINI_MODEL}")
    print(f"📝 Session logs: {session_dir}")
    print(f"⚡ Parallel processing enabled")
    print(f"⏳ Waiting for NEW prompts to be generated...")
    print("="*80 + "\n")
    
    try:
        while True:
            # Check for prompt files in SESSION prompts directory
            if prompts_dir.exists():
                prompt_files = sorted(prompts_dir.glob("prompt_player_*.txt"))
                
                # Collect new prompts to process
                new_prompts = []
                
                for prompt_file in prompt_files:
                    filename = prompt_file.name
                    
                    # Read JSON file to get content hash
                    json_file = prompt_file.with_suffix('.json')
                    if not json_file.exists():
                        continue
                    
                    try:
                        with open(json_file, 'rb') as f:
                            content = f.read()
                            content_hash = hashlib.md5(content).hexdigest()
                    except Exception as e:
                        print(f"⚠️  Could not read {json_file}: {e}")
                        continue
                    
                    # Check if this is a new prompt based on content hash
                    if filename not in processed_files or processed_files[filename] != content_hash:
                        new_prompts.append((prompt_file, filename, content_hash))
                
                # Process all new prompts in parallel
                if new_prompts:
                    print(f"\n🆕 Detected {len(new_prompts)} new prompt(s)")
                    
                    # Small delay to ensure files are fully written
                    time.sleep(0.2)
                    
                    # Check how many can actually be sent
                    players_with_active_requests = []
                    players_to_process = []
                    
                    for prompt_file, filename, content_hash in new_prompts:
                        player_name = prompt_file.stem.replace("prompt_player_", "")
                        
                        # Check if player already has active request
                        with tester.active_requests_lock:
                            if player_name in tester.active_requests:
                                players_with_active_requests.append(player_name)
                            else:
                                players_to_process.append((prompt_file, filename, content_hash, player_name))
                    
                    # Report skipped players
                    if players_with_active_requests:
                        print(f"🚫 Skipping players with active requests: {', '.join(players_with_active_requests)}")
                    
                    # Report players being processed
                    if players_to_process:
                        player_names = [p[3] for p in players_to_process]
                        print(f"📤 Submitting to queue: {', '.join(player_names)}")
                    
                    # Submit all prompts to thread pool
                    futures = []
                    for prompt_file, filename, content_hash, player_name in players_to_process:
                        future = executor.submit(tester.process_prompt, prompt_file, executor)
                        futures.append((future, filename, content_hash))
                    
                    # Wait for all to complete
                    for future, filename, content_hash in futures:
                        player_name = None
                        try:
                            # Extract player name from filename for error handling
                            player_name = filename.replace("prompt_player_", "").replace(".txt", "")
                            result = future.result(timeout=120)  # 2 minute timeout
                            if result:
                                processed_files[filename] = content_hash
                                # Reset retry count on success
                                if filename in retry_counts:
                                    del retry_counts[filename]
                        except TimeoutError:
                            print(f"❌ Error processing prompt: TimeoutError")
                            print(f"   Request for player '{player_name}' timed out after 120 seconds")
                            
                            # Track retry attempts
                            retry_counts[filename] = retry_counts.get(filename, 0) + 1
                            attempts = retry_counts[filename]
                            print(f"   ⚠️  Retry attempt {attempts}/{MAX_RETRIES}")
                            
                            # Check if max retries reached
                            if attempts >= MAX_RETRIES:
                                print(f"\n{'='*80}")
                                print(f"🛑 CRITICAL: Player '{player_name}' failed after {MAX_RETRIES} timeout attempts")
                                print(f"{'='*80}")
                                print(f"Stopping execution to prevent infinite retry loop.")
                                print(f"Check the prompt or API connection issues.")
                                print(f"{'='*80}\n")
                                raise RuntimeError(f"Max retries ({MAX_RETRIES}) exceeded for player '{player_name}'")
                            
                            # Remove from active requests so new prompts can be sent
                            if player_name:
                                with tester.active_requests_lock:
                                    tester.active_requests.discard(player_name)
                                print(f"   🔄 Removed '{player_name}' from active requests - will retry")
                        except Exception as e:
                            print(f"❌ Error processing prompt: {e}")
                            import traceback
                            traceback.print_exc()
                            # Also remove from active requests on any other error
                            if player_name:
                                with tester.active_requests_lock:
                                    tester.active_requests.discard(player_name)
                    
                    # Show stats periodically
                    if len(processed_files) % 5 == 0 and len(processed_files) > 0:
                        tester.get_stats()
            
            # Sleep before next check
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        print("\n\n✅ AI Tester stopped")
        executor.shutdown(wait=True)
        tester.get_stats()
        print(f"\n📝 Session logs saved to: {session_dir}")
        print(f"   Files: {', '.join([f.name for f in session_dir.glob('*.md')])}")


if __name__ == '__main__':
    monitor_prompts()
