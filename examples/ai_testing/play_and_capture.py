"""
Play Interactive Game with Guaranteed State Capture
----------------------------------------------------
This version captures EVERY game state update reliably.
"""

import sys
from pathlib import Path
import json
import signal
import atexit
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pycatan import RealGame
from pycatan.management import game_manager as gm_module

# Global list to capture states
captured_states = []
original_update_state = None

# Output directory for states
OUTPUT_DIR = Path('examples/ai_testing/my_games')
CURRENT_STATE_FILE = OUTPUT_DIR / 'current_state.json'
OPTIMIZED_STATE_FILE = OUTPUT_DIR / 'current_state_optimized.txt'


def optimize_state_for_ai(input_data):
    """
    ממיר את מצב המשחק למבנה אופטימלי עבור AI.
    מדחס את המידע ומסיר דופליקציות.
    """
    # טיפול בעטיפה אם קיימת
    data = input_data['state'] if 'state' in input_data else input_data
    
    # מילוני קיצור
    RES_MAP = {"wood": "W", "brick": "B", "sheep": "S", "wheat": "Wh", "ore": "O", "desert": "D"}
    TYPE_MAP = {"settlement": "S", "city": "C"}
    
    # 1. יצירת מערך הקסים (H)
    max_hex_id = max([h['id'] for h in data.get('hexes', [])], default=0)
    hex_array = [""] * (max_hex_id + 1)
    
    robber_hex = None
    for h in data.get('hexes', []):
        if h.get('has_robber'): 
            robber_hex = h['id']
        t = RES_MAP.get(h['type'], "?")
        # אם יש מספר מוסיפים אותו, אחרת (מדבר) רק את הסוג
        val = f"{t}{h['number']}" if h['number'] else t
        hex_array[h['id']] = val

    # 2. מיפוי נמלים
    port_map = {}
    for p in data.get('harbors', []):
        t = RES_MAP.get(p['type'], "Any") if p['type'] != "any" else "?"
        code = f"{t}{p['ratio']}"
        port_map[p['point_one']] = code
        port_map[p['point_two']] = code

    # 3. יצירת מערך צמתים (N)
    max_point_id = max([p['point_id'] for p in data.get('points', [])], default=0)
    nodes_array = [None] * (max_point_id + 1)
    
    for p in data.get('points', []):
        # המבנה: [ [שכנים], [הקסים], נמל? ]
        val = [p['adjacent_points'], p['adjacent_hexes']]
        if p['point_id'] in port_map:
            val.append(port_map[p['point_id']])
        nodes_array[p['point_id']] = val

    # 4. עיבוד שחקנים
    players = {}
    pid_to_name = {}
    for pl in data.get('players', []):
        name = pl['name']
        pid_to_name[pl['id']] = name
        
        # ספירת משאבים
        res_list = pl.get('cards_list', [])
        res_compact = {}
        if res_list:
            for r in set(res_list):
                r_key = RES_MAP.get(r.lower(), r)
                res_compact[r_key] = res_list.count(r)
        
        p_obj = {"vp": pl['victory_points'], "res": res_compact}
        
        # קלפי פיתוח
        knights = pl.get('knights_played', 0)
        hidden = pl.get('dev_cards_list', [])
        if knights > 0 or hidden:
            p_obj["dev"] = {}
            if hidden: 
                p_obj["dev"]["h"] = hidden
            if knights: 
                p_obj["dev"]["r"] = ["K"] * knights
        
        # דגלים מיוחדים (LR / LA)
        flags = []
        if pl.get('has_longest_road'):
            flags.append("LR")  # Longest Road
        if pl.get('has_largest_army'):
            flags.append("LA")  # Largest Army
        
        if flags:
            p_obj["stat"] = flags
            
        players[name] = p_obj

    # 5. מצב הלוח (בניינים ודרכים)
    bld = []
    for b in data.get('settlements', []):
        owner_id = b.get('player', 1) - 1  # המרה מ-1-based ל-0-based
        owner = pid_to_name.get(owner_id, "?")
        bld.append([b['vertex'], owner, "S"])
    
    for b in data.get('cities', []):
        owner_id = b.get('player', 1) - 1  # המרה מ-1-based ל-0-based
        owner = pid_to_name.get(owner_id, "?")
        bld.append([b['vertex'], owner, "C"])

    rds = []
    for r in data.get('roads', []):
        owner_id = r.get('player', 1) - 1  # המרה מ-1-based ל-0-based
        owner = pid_to_name.get(owner_id, "?")
        rds.append([[r['from'], r['to']], owner])
    
    # המרת ID של השחקן הנוכחי לשם
    curr_id = data.get('current_player')
    curr_name = pid_to_name.get(curr_id, str(curr_id))

    # החזרת המילון המעובד
    return {
        "meta": {
            "curr": curr_name, 
            "phase": data.get('current_phase'), 
            "robber": robber_hex,
            "dice": data.get('dice_result')
        },
        "H": hex_array,
        "N": nodes_array,
        "state": {"bld": bld, "rds": rds},
        "players": players
    }


def format_hybrid_json(data):
    """יצירת מחרוזת JSON היברידית עם מקרא למעלה"""
    
    # המקרא
    legend = """1. LOOKUP TABLES:
   • "H" (Hexes): Array where Index = HexID. Value = Resource+Num.
     Example: H[1]="W12" -> Hex 1 is Wood 12.
   • "N" (Nodes): Array where Index = NodeID.
     Format: [ [Neighbors], [HexIDs], Port? ]
     Logic: To find yield of Node 10, check N[10]. Get HexIDs (e.g. [1,5]). Look up H[1] and H[5].

2. CODES: W=Wood, B=Brick, S=Sheep, Wh=Wheat, O=Ore, D=Desert.
          ?3=Any 3:1 port, X2=Specific Resource 2:1 port.

3. STATE: "bld"=[NodeID, Owner, Type], "rds"=[[From,To], Owner].

4. PLAYERS: "res"={Resource:Count}, "dev"={"h":[Hidden Cards], "r":[Revealed] (K=Knight)}, 
            "stat"=["LR" (Longest Road), "LA" (Largest Army)].

5. ROBBER: Located at HexID specified in "meta.robber". H[id] is blocked.

JSON:
"""
    
    sections = [
        f'"meta":{json.dumps(data["meta"], separators=(",", ":"))}',
        f'"H":{json.dumps(data["H"], separators=(",", ":"))}',
        f'"N":{json.dumps(data["N"], separators=(",", ":"))}',
        f'"state":{json.dumps(data["state"], separators=(",", ":"))}',
        f'"players":{json.dumps(data["players"], separators=(",", ":"))}'
    ]
    json_content = "{\n  " + ",\n  ".join(sections) + "\n}"
    
    return legend + json_content


def save_current_state(state):
    """Save the current state to a file (updated in real-time)."""
    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        cleaned = clean_state_for_llm(state)
        
        # שמירת הגרסה המקורית
        with open(CURRENT_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'state_number': len(captured_states),
                'state': cleaned
            }, f, indent=2, ensure_ascii=False)
        
        # שמירת הגרסה האופטימלית
        try:
            optimized = optimize_state_for_ai(cleaned)
            optimized_output = format_hybrid_json(optimized)
            with open(OPTIMIZED_STATE_FILE, 'w', encoding='utf-8') as f:
                f.write(optimized_output)
        except Exception as opt_err:
            print(f"[⚠️ Failed to save optimized state: {opt_err}]", flush=True)
            
    except Exception as e:
        print(f"[⚠️ Failed to save current state: {e}]", flush=True)


def capturing_wrapper(original_method):
    """Wrap the display_game_state method to capture all calls."""
    def wrapper(self, game_state):
        # Call original (this will update visualizations with converted state)
        result = original_method(self, game_state)
        
        # Now capture from web visualization's converted state
        for viz in self.visualizations:
            if hasattr(viz, 'current_game_state') and viz.current_game_state:
                try:
                    # current_game_state is already a dict (JSON-serializable)
                    state_copy = json.loads(json.dumps(viz.current_game_state))
                    captured_states.append(state_copy)
                    print(f"[✅ Captured state #{len(captured_states)}]", flush=True)
                    
                    # Save current state to file (real-time update)
                    save_current_state(state_copy)
                    
                    break  # Only capture once per update
                except (TypeError, AttributeError) as e:
                    # Skip if not serializable
                    pass
        
        return result
    return wrapper


def clean_state_for_llm(state):
    """Remove unnecessary fields that are noise for LLM."""
    cleaned = json.loads(json.dumps(state))  # Deep copy
    
    # Clean hexes: remove pixel_coords, position, axial_coords, q, r
    if 'hexes' in cleaned:
        for hex in cleaned['hexes']:
            hex.pop('pixel_coords', None)
            hex.pop('position', None)
            hex.pop('axial_coords', None)
            hex.pop('q', None)
            hex.pop('r', None)
    
    # Clean points: remove pixel_coords, game_coords
    if 'points' in cleaned:
        for point in cleaned['points']:
            point.pop('pixel_coords', None)
            point.pop('game_coords', None)
    
    # Remove board_graph entirely (redundant with points data)
    cleaned.pop('board_graph', None)
    
    return cleaned


def save_all_states():
    """Save all captured states to files."""
    if not captured_states:
        print("\n⚠️  No states were captured during this game.")
        return
    
    # Clean all states for LLM
    cleaned_states = [clean_state_for_llm(state) for state in captured_states]
    
    # Create output directory
    output_dir = Path('examples/ai_testing/my_games')
    output_dir.mkdir(exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save full history (cleaned)
    history_file = output_dir / f'game_{timestamp}_full.json'
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_states': len(cleaned_states),
            'timestamp': timestamp,
            'states': cleaned_states
        }, f, indent=2, ensure_ascii=False)
    
    # Save final state (cleaned)
    final_file = output_dir / f'game_{timestamp}_final.json'
    with open(final_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_states[-1], f, indent=2, ensure_ascii=False)
    
    # Save optimized final state
    optimized_final_file = output_dir / f'game_{timestamp}_final_optimized.txt'
    try:
        optimized_final = optimize_state_for_ai(cleaned_states[-1])
        with open(optimized_final_file, 'w', encoding='utf-8') as f:
            f.write(format_hybrid_json(optimized_final))
    except Exception as e:
        print(f"[⚠️ Failed to save optimized final state: {e}]")
    
    # Save optimized full history
    optimized_history_file = output_dir / f'game_{timestamp}_full_optimized.txt'
    try:
        optimized_states = [optimize_state_for_ai(state) for state in cleaned_states]
        with open(optimized_history_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total_states': len(optimized_states),
                'timestamp': timestamp,
                'states': optimized_states
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[⚠️ Failed to save optimized history: {e}]")
    
    # Also save to standard location (cleaned)
    sample_file = Path('examples/ai_testing/sample_states/captured_game.json')
    sample_file.parent.mkdir(exist_ok=True)
    with open(sample_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_states[-1], f, indent=2, ensure_ascii=False)
    
    # Save optimized to standard location
    sample_optimized_file = Path('examples/ai_testing/sample_states/captured_game_optimized.txt')
    try:
        optimized_sample = optimize_state_for_ai(cleaned_states[-1])
        with open(sample_optimized_file, 'w', encoding='utf-8') as f:
            f.write(format_hybrid_json(optimized_sample))
    except Exception as e:
        print(f"[⚠️ Failed to save optimized sample: {e}]")
    
    print("\n" + "="*80)
    print("✅ GAME SAVED SUCCESSFULLY!")
    print("="*80)
    print(f"\nTotal states captured: {len(captured_states)}")
    print(f"\nSaved to:")
    print(f"  📁 Full history:          {history_file}")
    print(f"  📁 Full history (opt):    {optimized_history_file}")
    print(f"  📄 Final state:           {final_file}")
    print(f"  📄 Final state (opt):     {optimized_final_file}")
    print(f"  📌 Quick access:          {sample_file}")
    print(f"  📌 Quick access (opt):    {sample_optimized_file}")
    print(f"  🔄 Real-time:             {CURRENT_STATE_FILE}")
    print(f"  🔄 Real-time (opt):       {OPTIMIZED_STATE_FILE}")
    print("\n" + "="*80)
    
    # Print summary
    if captured_states:
        final = captured_states[-1]
        print("\n📊 FINAL GAME STATE:")
        print(f"  Phase: {final.get('current_phase', 'UNKNOWN')}")
        print(f"  Settlements: {len(final.get('settlements', []))}")
        print(f"  Cities: {len(final.get('cities', []))}")
        print(f"  Roads: {len(final.get('roads', []))}")
        
        for player in final.get('players', []):
            print(f"\n  Player {player['id']} ({player['name']}):")
            print(f"    Victory Points: {player['victory_points']}")
            print(f"    Resources: {len(player.get('cards_list', []))}")
            print(f"    Settlements: {player['settlements']}")
            print(f"    Roads: {player['roads']}")
        
        print("="*80)


# Register save function
atexit.register(save_all_states)


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\n🛑 Game interrupted...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def main():
    print("="*80)
    print("🎮 CATAN WITH GUARANTEED STATE CAPTURE")
    print("="*80)
    print("\n📝 Every game action will be automatically saved!")
    print(f"🔄 Real-time state: {CURRENT_STATE_FILE}")
    print("💾 Full history saved at end of game")
    print("⌨️  Press Ctrl+C anytime to stop and save.")
    print("="*80 + "\n")
    
    # Patch the VisualizationManager's display_game_state
    from pycatan.visualizations.visualization import VisualizationManager
    VisualizationManager.display_game_state = capturing_wrapper(
        VisualizationManager.display_game_state
    )
    
    # Also patch WebVisualization.update_full_state (called directly by RealGame)
    from pycatan.visualizations.web_visualization import WebVisualization
    original_web_update = WebVisualization.update_full_state
    
    def web_update_wrapper(self, game_state):
        """Wrap WebVisualization.update_full_state to capture states."""
        # Call original FIRST (this updates self.current_game_state)
        result = original_web_update(self, game_state)
        
        # NOW capture from the updated current_game_state
        if hasattr(self, 'current_game_state') and self.current_game_state:
            state_copy = json.loads(json.dumps(self.current_game_state))
            captured_states.append(state_copy)
            print(f"[✅ Captured state #{len(captured_states)}]", flush=True)
            
            # Save current state to file (real-time update)
            save_current_state(state_copy)
        
        return result
    
    WebVisualization.update_full_state = web_update_wrapper
    
    try:
        # Start game
        game = RealGame()
        
        # 🎯 CRITICAL: Install turn start callback BEFORE running game
        # This ensures state is saved at the BEGINNING of each turn
        def on_turn_start(game_state):
            """Called at the start of each turn, before showing to user."""
            # Convert GameState object to dict
            from pycatan.visualizations.web_visualization import WebVisualization
            web_viz = WebVisualization()
            web_viz.update_full_state(game_state)
            
            if hasattr(web_viz, 'current_game_state') and web_viz.current_game_state:
                state_copy = json.loads(json.dumps(web_viz.current_game_state))
                captured_states.append(state_copy)
                print(f"[🎯 Turn Start - Captured state #{len(captured_states)}]", flush=True)
                save_current_state(state_copy)
        
        # Install the callback
        if hasattr(game, 'game_manager'):
            game.game_manager._on_turn_start_callback = on_turn_start
        
        game.run()
        
    except KeyboardInterrupt:
        print("\n\n✅ Game stopped")
    except EOFError:
        print("\n\n✅ Game completed")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
