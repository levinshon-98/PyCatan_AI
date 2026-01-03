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
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import our AI components
from pycatan.ai.llm_client import GeminiClient, LLMResponse
from pycatan.ai.response_parser import ResponseParser, ParseResult
from pycatan.ai.schemas import ResponseType

# Configure logging - will be set up in main with file output
logger = logging.getLogger(__name__)


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
                logger.info(f"Loaded {len(self.messages)} chat messages")
            except Exception as e:
                logger.warning(f"Could not load chat history: {e}")
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
        logger.info(f"💬 {player}: {message}")
    
    def save(self):
        """Save chat history to file."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump({"messages": self.messages}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")
    
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
                logger.info(f"Loaded memories for {len(self.memories)} agents")
            except Exception as e:
                logger.warning(f"Could not load memories: {e}")
                self.memories = {}
    
    def update_memory(self, player: str, note: str):
        """Update agent's memory."""
        self.memories[player] = note
        self.save()
        logger.info(f"📝 {player} updated memory: {note[:50]}...")
    
    def get_memory(self, player: str) -> Optional[str]:
        """Get agent's current memory."""
        return self.memories.get(player)
    
    def save(self):
        """Save memories to file."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.memories, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")


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
        self.session_dir = session_dir
        self.player_logs = {}  # Will store file handles per player
        self.consecutive_failures = 0  # Track consecutive failures
        self.max_consecutive_failures = 5  # Stop after 5 failures in a row
        
        logger.info(f"🤖 AI Tester initialized with model: {GEMINI_MODEL}")
        logger.info(f"📁 Session logs: {session_dir}")
        logger.info(f"💬 Chat history: {session_chat_file}")
        logger.info(f"📝 Agent memories: {session_memory_file}")
    
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
    
    def process_prompt(self, prompt_file: Path) -> Optional[Dict[str, Any]]:
        """
        Process a single prompt file.
        
        Args:
            prompt_file: Path to prompt file
            
        Returns:
            Processed response data or None if failed
        """
        # Extract player name from filename (e.g., "prompt_player_a.txt" -> "a")
        player_name = prompt_file.stem.replace("prompt_player_", "")
        
        separator = "="*80
        header = f"🤖 PROCESSING AI AGENT - Player {player_name.upper()}"
        
        logger.info(separator)
        logger.info(header)
        logger.info(separator)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        request_num = len([k for k in self.player_logs.keys() if player_name in str(k)]) + 1
        
        # Use JSON file instead of TXT for actual prompt
        json_file = prompt_file.with_suffix('.json')
        if not json_file.exists():
            logger.error(f"JSON prompt file not found: {json_file}")
            return None
        
        # Read prompt JSON file directly
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                prompt_json = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read JSON prompt file: {e}")
            return None
        
        # Extract the actual prompt (the nested 'prompt' field)
        actual_prompt = prompt_json.get("prompt", prompt_json)
        
        # Display prompt info
        logger.info(f"📤 Sending prompt to Gemini...")
        logger.info(f"   Model: {GEMINI_MODEL}")
        logger.info(f"   Player: {player_name}")
        
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
            logger.error(error_msg)
            self._log_to_player_file(player_name, f"\n{error_msg}")
            
            # Track consecutive failures
            self.consecutive_failures += 1
            
            # If it's a schema error, stop immediately to prevent repeated failures
            if "Unknown field for Schema" in str(llm_response.error):
                logger.critical("\n" + "="*80)
                logger.critical("🛑 CRITICAL ERROR: Schema validation failed!")
                logger.critical(f"Error: {llm_response.error}")
                logger.critical("The response schema contains fields that Gemini doesn't support.")
                logger.critical("Gemini only supports: type, properties, required, description, items, enum")
                logger.critical("Stopping to prevent repeated failures.")
                logger.critical("="*80 + "\n")
                raise RuntimeError("Schema validation error - stopping")
            
            return None
        
        # Reset failure counter on success
        self.consecutive_failures = 0
        
        logger.info(f"✅ Response received ({llm_response.latency_seconds:.2f}s)")
        logger.info(f"   Tokens: {llm_response.total_tokens} (prompt: {llm_response.prompt_tokens}, completion: {llm_response.completion_tokens})")
        
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
        
        # Parse response
        parse_result = self.parser.parse(llm_response.content, ResponseType.OBSERVING)
        
        if not parse_result.success:
            error_msg = f"❌ Failed to parse response: {parse_result.error_message}"
            logger.error(error_msg)
            logger.error(f"Raw response: {llm_response.content[:500]}...")
            self._log_to_player_file(player_name, f"\n### ❌ Parse Error\n")
            self._log_to_player_file(player_name, f"**Error:** {parse_result.error_message}\n")
            self._log_to_player_file(player_name, f"**Raw response preview:** `{llm_response.content[:500]}...`\n")
            return None
        
        logger.info("✅ Response parsed successfully")
        self._log_to_player_file(player_name, "\n### ✅ Parse Success\n")
        
        # Display structured response
        self._log_structured_response(player_name, parse_result.data)
        
        # Display the response
        self._display_response(player_name, parse_result.data, llm_response)
        
        # Handle chat and memory
        if "say_outloud" in parse_result.data and parse_result.data["say_outloud"]:
            self.chat_manager.add_message(player_name, parse_result.data["say_outloud"])
        
        if "note_to_self" in parse_result.data and parse_result.data["note_to_self"]:
            self.memory_manager.update_memory(player_name, parse_result.data["note_to_self"])
        
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
    """Get existing session or create new one."""
    # Use same path as generate_prompts_from_state.py
    current_session_file = Path("examples/ai_testing/my_games/current_session.txt")
    
    # Try to use existing session first
    if current_session_file.exists():
        try:
            with open(current_session_file, 'r') as f:
                session_path = f.read().strip()
                session_dir = Path(session_path)
                if session_dir.exists():
                    logger.info(f"📂 Using existing session: {session_dir.name}")
                    return session_dir
        except Exception as e:
            logger.warning(f"Could not read existing session: {e}")
    
    # Create new session if none exists
    session_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = LOGS_DIR / f"session_{session_time}"
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # Save current session path for other scripts to find
    # Write with flush to ensure it's immediately visible
    with open(current_session_file, 'w') as f:
        f.write(str(session_dir.absolute()))
        f.flush()
    
    logger.info(f"📂 Created new session: {session_dir.name}")
    logger.info(f"📄 Session file: {current_session_file.absolute()}")
    return session_dir


def monitor_prompts():
    """Monitor for new prompts and process them."""
    session_dir = get_or_create_session()
    
    # Create prompts directory inside session
    prompts_dir = session_dir / 'prompts'
    prompts_dir.mkdir(exist_ok=True)
    
    tester = AITester(session_dir)
    processed_files = {}  # Dictionary: filename -> mtime when processed
    
    print("="*80)
    print("🎮 AI AGENT LIVE TESTER")
    print("="*80)
    print(f"📁 Watching: {prompts_dir}")
    print(f"🤖 Model: {GEMINI_MODEL}")
    print(f"📝 Session logs: {session_dir}")
    print(f"⏳ Waiting for NEW prompts to be generated...")
    print("="*80 + "\n")
    
    try:
        while True:
            # Check for prompt files in SESSION prompts directory
            if prompts_dir.exists():
                prompt_files = sorted(prompts_dir.glob("prompt_player_*.txt"))
                
                for prompt_file in prompt_files:
                    # Get current modification time
                    file_mtime = prompt_file.stat().st_mtime
                    
                    # Check if file has been updated or is new
                    filename = prompt_file.name
                    is_new_or_updated = (
                        filename not in processed_files or 
                        file_mtime > processed_files.get(filename, 0)
                    )
                    
                    if is_new_or_updated:
                        # New or updated prompt file
                        logger.info(f"🆕 Detected new prompt: {prompt_file.name}")
                        
                        # Small delay to ensure file is fully written
                        time.sleep(0.2)
                        
                        # Process it (will raise RuntimeError on critical schema errors)
                        try:
                            result = tester.process_prompt(prompt_file)
                        except RuntimeError as e:
                            # Critical error - stop immediately
                            print("\n" + "="*80)
                            print("🛑 CRITICAL ERROR DETECTED")
                            print("="*80)
                            print(f"Error: {e}")
                            print("\nStopping AI Tester to prevent repeated failures.")
                            print("Please fix the schema issue and restart.")
                            print("="*80 + "\n")
                            tester.get_stats()
                            print(f"\n📝 Session logs saved to: {session_dir}")
                            print(f"   Files: {', '.join([f.name for f in session_dir.glob('*.md')])}")
                            return  # Exit the function
                        
                        if result:
                            processed_files[filename] = file_mtime
                        
                        # Show stats periodically
                        if len(processed_files) % 5 == 0 and len(processed_files) > 0:
                            tester.get_stats()
            
            # Sleep before next check
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        print("\n\n✅ AI Tester stopped")
        tester.get_stats()
        print(f"\n📝 Session logs saved to: {session_dir}")
        print(f"   Files: {', '.join([f.name for f in session_dir.glob('*.md')])}")


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    monitor_prompts()
