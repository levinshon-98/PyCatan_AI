"""
Real-Time AI Game Viewer
-------------------------
Web interface to monitor AI agents, chat, and game state in real-time.
"""

import json
from pathlib import Path
from datetime import datetime
from collections import OrderedDict
from flask import Flask, render_template, jsonify, Response
import html

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# Ensure Flask preserves JSON key order
app.config['JSON_SORT_KEYS'] = False

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
    
    # Get structured requests data (new format)
    requests_file = session_dir / "requests.json"
    requests_data = []
    if requests_file.exists():
        try:
            with open(requests_file, 'r', encoding='utf-8') as f:
                # Use object_pairs_hook to preserve key order
                data = json.load(f, object_pairs_hook=OrderedDict)
                requests_data = data.get("requests", [])
                print(f"  ✓ Loaded {len(requests_data)} requests")
        except Exception as e:
            print(f"  ✗ Error loading requests: {e}")
    else:
        print(f"  ℹ No requests file found")
    
    # Get player logs (old format - keep for backwards compatibility)
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
    
    # Calculate statistics
    new_requests_count = sum(1 for req in requests_data if req.get("is_new", False))
    players_with_requests = {}
    for req in requests_data:
        player = req["player_name"]
        if player not in players_with_requests:
            players_with_requests[player] = {"total": 0, "new": 0}
        players_with_requests[player]["total"] += 1
        if req.get("is_new", False):
            players_with_requests[player]["new"] += 1
    
    return {
        "session_name": session_dir.name,
        "session_path": str(session_dir),
        "requests": requests_data,
        "new_requests_count": new_requests_count,
        "players_stats": players_with_requests,
        "players": players,
        "chat": chat_messages,
        "memories": memories
    }


@app.route('/')
def index():
    """Main page - use dynamic viewer."""
    sessions = get_all_sessions()
    current_session = get_current_session()
    
    return render_template('viewer_dynamic.html', 
                         sessions=sessions,
                         current_session=str(current_session) if current_session else None)


@app.route('/enhanced')
def enhanced_viewer():
    """Enhanced viewer (old version)."""
    sessions = get_all_sessions()
    current_session = get_current_session()
    
    return render_template('viewer_enhanced.html', 
                         sessions=sessions,
                         current_session=str(current_session) if current_session else None)


@app.route('/old')
def old_viewer():
    """Old viewer for backwards compatibility."""
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


@app.route('/api/mark_viewed/<path:session_path>/<request_id>')
def api_mark_viewed(session_path, request_id):
    """Mark a specific request as viewed."""
    session_dir = Path(session_path)
    requests_file = session_dir / "requests.json"
    
    if not requests_file.exists():
        return jsonify({"error": "Requests file not found"}), 404
    
    try:
        with open(requests_file, 'r', encoding='utf-8') as f:
            data = json.load(f, object_pairs_hook=OrderedDict)
        
        # Mark request as viewed
        found = False
        for req in data.get("requests", []):
            if req["request_id"] == request_id:
                req["is_new"] = False
                found = True
                break
        
        if not found:
            return jsonify({"error": "Request not found"}), 404
        
        # Save back (preserving order)
        with open(requests_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/mark_all_viewed/<path:session_path>')
def api_mark_all_viewed(session_path):
    """Mark all requests as viewed."""
    session_dir = Path(session_path)
    requests_file = session_dir / "requests.json"
    
    if not requests_file.exists():
        return jsonify({"error": "Requests file not found"}), 404
    
    try:
        with open(requests_file, 'r', encoding='utf-8') as f:
            data = json.load(f, object_pairs_hook=OrderedDict)
        
        # Mark all as viewed
        for req in data.get("requests", []):
            req["is_new"] = False
        
        # Save back (preserving order)
        with open(requests_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return jsonify({"success": True, "marked_count": len(data.get("requests", []))})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("="*80)
    print("🌐 AI Game Viewer Starting...")
    print("="*80)
    print(f"\n📁 Watching: {LOGS_DIR.absolute()}")
    print(f"📄 Session file: {SESSION_FILE.absolute()}")
    print(f"\n🔗 Open in browser: http://localhost:5001")
    print("\n⚠️  Note: Game board is on http://localhost:5000")
    print("   This viewer (5001) shows AI requests/responses")
    print("   Game board (5000) shows the actual Catan board")
    print("\n" + "="*80 + "\n")
    
    # Check current session on startup
    get_current_session()
    
    app.run(debug=False, host='0.0.0.0', port=5001)
