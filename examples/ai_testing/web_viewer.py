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

# Session directories - use absolute path from script location
SCRIPT_DIR = Path(__file__).parent.absolute()
LOGS_DIR = SCRIPT_DIR / "my_games"
SESSION_FILE = LOGS_DIR / "current_session.txt"


def get_current_session():
    """Get current session directory."""
    print(f"[DEBUG] LOGS_DIR: {LOGS_DIR}")
    print(f"[DEBUG] LOGS_DIR exists: {LOGS_DIR.exists()}")
    print(f"[DEBUG] SESSION_FILE: {SESSION_FILE}")
    print(f"[DEBUG] SESSION_FILE exists: {SESSION_FILE.exists()}")
    
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                session_name = f.read().strip()
                print(f"[DEBUG] Session name from file: {session_name}")
                # Handle both full path and just session name
                if Path(session_name).is_absolute():
                    session_dir = Path(session_name)
                else:
                    session_dir = LOGS_DIR / session_name
                print(f"[DEBUG] Session dir: {session_dir}")
                print(f"[DEBUG] Session dir exists: {session_dir.exists()}")
                if session_dir.exists():
                    print(f"[OK] Found current session: {session_dir.name}")
                    return session_dir
        except Exception as e:
            print(f"Error reading session file: {e}")
    
    # Fallback: get most recent session
    if LOGS_DIR.exists():
        sessions = sorted(LOGS_DIR.glob("session_*"), reverse=True)
        print(f"[DEBUG] Found sessions: {[s.name for s in sessions]}")
        if sessions:
            print(f"[OK] Using most recent session: {sessions[0].name}")
            return sessions[0]
    
    print("[!] No session found")
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
    
    # Get structured requests data
    requests_data = []
    
    # Try new format: player folders with prompts/responses
    for player_dir in session_dir.iterdir():
        if player_dir.is_dir() and (player_dir / "prompts").exists():
            player_name = player_dir.name
            prompts_dir = player_dir / "prompts"
            responses_dir = player_dir / "responses"
            
            # Load all prompts for this player
            for prompt_file in sorted(prompts_dir.glob("prompt_*.json")):
                # Skip iteration files - they're in iterations subfolder
                if "iter" in prompt_file.name:
                    continue
                    
                try:
                    with open(prompt_file, 'r', encoding='utf-8') as f:
                        prompt_data = json.load(f)
                    
                    req_num = prompt_data.get("request_number", 0)
                    
                    # Try to load corresponding response
                    response_data = None
                    response_file = responses_dir / f"response_{req_num}.json"
                    if response_file.exists():
                        with open(response_file, 'r', encoding='utf-8') as f:
                            response_data = json.load(f)
                    
                    # Load tool iterations for this prompt
                    tool_iterations = []
                    iterations_dir = prompts_dir / "iterations"
                    if iterations_dir.exists():
                        for iter_file in sorted(iterations_dir.glob(f"prompt_{req_num}_iter*.json")):
                            try:
                                with open(iter_file, 'r', encoding='utf-8') as f:
                                    iter_data = json.load(f)
                                    tool_iterations.append({
                                        "iteration": iter_data.get("iteration", 0),
                                        "tool_results": iter_data.get("tool_results", ""),
                                        "timestamp": iter_data.get("timestamp", "")
                                    })
                            except Exception as e:
                                print(f"    [!] Error loading iteration {iter_file.name}: {e}")
                    
                    requests_data.append({
                        "player_name": player_name,
                        "request_number": req_num,
                        "timestamp": prompt_data.get("timestamp", ""),
                        "prompt": prompt_data.get("prompt", {}),
                        "response": response_data.get("parsed", {}) if response_data else None,
                        "raw_response": response_data.get("raw_content", "") if response_data else None,
                        "tokens": response_data.get("tokens", {}) if response_data else {},
                        "success": response_data.get("success", False) if response_data else False,
                        "tool_iterations": tool_iterations
                    })
                    
                except Exception as e:
                    print(f"  [!] Error loading {prompt_file.name}: {e}")
            
            print(f"  [OK] Loaded {player_name}: {len([p for p in requests_data if p['player_name'] == player_name])} requests")
    
    # Fallback: try old format (requests.json)
    if not requests_data:
        requests_file = session_dir / "requests.json"
        if requests_file.exists():
            try:
                with open(requests_file, 'r', encoding='utf-8') as f:
                    data = json.load(f, object_pairs_hook=OrderedDict)
                    requests_data = data.get("requests", [])
                    print(f"  [OK] Loaded {len(requests_data)} requests (old format)")
            except Exception as e:
                print(f"  [!] Error loading requests: {e}")
    
    # Sort by timestamp
    requests_data.sort(key=lambda x: x.get("timestamp", ""))
    
    # Get player logs - check player folders
    players = {}
    for player_dir in session_dir.iterdir():
        if player_dir.is_dir():
            player_name = player_dir.name
            md_file = player_dir / f"{player_name}.md"
            if md_file.exists():
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        players[player_name] = {
                            "name": player_name,
                            "content": content,
                            "html": html.escape(content)
                        }
                except Exception as e:
                    print(f"  [!] Error loading {player_name}: {e}")
    
    # Get chat history
    chat_file = session_dir / "chat_history.json"
    chat_messages = []
    if chat_file.exists():
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                chat_messages = data.get("messages", [])
        except Exception as e:
            print(f"  [!] Error loading chat: {e}")
            chat_messages = []
    
    # Get agent memories
    memory_file = session_dir / "agent_memories.json"
    memories = {}
    if memory_file.exists():
        try:
            with open(memory_file, 'r', encoding='utf-8') as f:
                memories = json.load(f)
                print(f"  [OK] Loaded memories for {len(memories)} players")
        except Exception as e:
            print(f"  [!] Error loading memories: {e}")
            memories = {}
    
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
    print("[WEB] AI Game Viewer Starting...")
    print("="*80)
    print(f"\n[DIR] Watching: {LOGS_DIR.absolute()}")
    print(f"[FILE] Session file: {SESSION_FILE.absolute()}")
    print(f"\n[URL] Open in browser: http://localhost:5001")
    print("\n[NOTE] Game board is on http://localhost:5000")
    print("   This viewer (5001) shows AI requests/responses")
    print("   Game board (5000) shows the actual Catan board")
    print("\n" + "="*80 + "\n")
    
    # Check current session on startup
    get_current_session()
    
    app.run(debug=False, host='0.0.0.0', port=5001)
