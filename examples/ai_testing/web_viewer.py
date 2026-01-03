"""
Real-Time AI Game Viewer
-------------------------
Web interface to monitor AI agents, chat, and game state in real-time.
"""

import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify
import html

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

LOGS_DIR = Path("examples/ai_testing/my_games/ai_logs")
SESSION_FILE = Path("examples/ai_testing/my_games/current_session.txt")


def get_current_session():
    """Get current session directory."""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                session_path = f.read().strip()
                session_dir = Path(session_path)
                if session_dir.exists():
                    print(f"✓ Found current session: {session_dir.name}")
                    return session_dir
        except Exception as e:
            print(f"Error reading session file: {e}")
    
    # Fallback: get most recent session
    if LOGS_DIR.exists():
        sessions = sorted(LOGS_DIR.glob("session_*"), reverse=True)
        if sessions:
            print(f"✓ Using most recent session: {sessions[0].name}")
            return sessions[0]
    
    print("⚠ No session found")
    return None


def get_all_sessions():
    """Get list of all session directories."""
    if not LOGS_DIR.exists():
        return []
    
    sessions = []
    current_session_path = get_current_session()
    
    for session_dir in sorted(LOGS_DIR.glob("session_*"), reverse=True):
        sessions.append({
            "name": session_dir.name,
            "path": str(session_dir.absolute()),
            "is_current": current_session_path and str(session_dir.absolute()) == str(current_session_path.absolute())
        })
    return sessions


def get_session_data(session_path):
    """Get all data for a specific session."""
    session_dir = Path(session_path)
    
    if not session_dir.exists():
        return None
    
    print(f"Loading session data from: {session_dir}")
    
    # Get player logs
    players = {}
    for player_file in session_dir.glob("player_*.md"):
        player_name = player_file.stem.replace("player_", "").upper()
        try:
            with open(player_file, 'r', encoding='utf-8') as f:
                content = f.read()
                players[player_name] = {
                    "name": player_name,
                    "content": content,
                    "html": html.escape(content)
                }
                print(f"  ✓ Loaded player: {player_name}")
        except Exception as e:
            print(f"  ✗ Error loading {player_name}: {e}")
            players[player_name] = {
                "name": player_name,
                "content": f"Error loading: {e}",
                "html": html.escape(f"Error loading: {e}")
            }
    
    # Get chat history
    chat_file = session_dir / "chat_history.json"
    chat_messages = []
    if chat_file.exists():
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                chat_messages = data.get("messages", [])
                print(f"  ✓ Loaded {len(chat_messages)} chat messages")
        except Exception as e:
            print(f"  ✗ Error loading chat: {e}")
            chat_messages = [{"error": str(e)}]
    else:
        print(f"  ℹ No chat history file")
    
    # Get agent memories
    memory_file = session_dir / "agent_memories.json"
    memories = {}
    if memory_file.exists():
        try:
            with open(memory_file, 'r', encoding='utf-8') as f:
                memories = json.load(f)
                print(f"  ✓ Loaded memories for {len(memories)} players")
        except Exception as e:
            print(f"  ✗ Error loading memories: {e}")
            memories = {}
    else:
        print(f"  ℹ No memories file")
    
    return {
        "session_name": session_dir.name,
        "session_path": str(session_dir),
        "players": players,
        "chat": chat_messages,
        "memories": memories
    }


@app.route('/')
def index():
    """Main page."""
    sessions = get_all_sessions()
    current_session = get_current_session()
    
    return render_template('viewer.html', 
                         sessions=sessions,
                         current_session=str(current_session) if current_session else None)


@app.route('/api/sessions')
def api_sessions():
    """Get list of all sessions."""
    return jsonify(get_all_sessions())


@app.route('/api/session/<path:session_path>')
def api_session(session_path):
    """Get data for specific session."""
    data = get_session_data(session_path)
    if data is None:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(data)


@app.route('/api/current')
def api_current():
    """Get current session data."""
    current = get_current_session()
    if current is None:
        return jsonify({"error": "No active session"}), 404
    
    data = get_session_data(str(current))
    if data is None:
        return jsonify({"error": "Session not found"}), 404
    
    return jsonify(data)


if __name__ == '__main__':
    print("="*80)
    print("🌐 AI Game Viewer Starting...")
    print("="*80)
    print(f"\n📁 Watching: {LOGS_DIR.absolute()}")
    print(f"📄 Session file: {SESSION_FILE.absolute()}")
    print(f"\n🔗 Open in browser: http://localhost:5000")
    print("\n" + "="*80 + "\n")
    
    # Check current session on startup
    get_current_session()
    
    app.run(debug=False, host='0.0.0.0', port=5000)
