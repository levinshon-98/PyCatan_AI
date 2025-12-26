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


def save_current_state(state):
    """Save the current state to a file (updated in real-time)."""
    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        cleaned = clean_state_for_llm(state)
        with open(CURRENT_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'state_number': len(captured_states),
                'state': cleaned
            }, f, indent=2, ensure_ascii=False)
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
    
    # Also save to standard location (cleaned)
    sample_file = Path('examples/ai_testing/sample_states/captured_game.json')
    sample_file.parent.mkdir(exist_ok=True)
    with open(sample_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_states[-1], f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*80)
    print("✅ GAME SAVED SUCCESSFULLY!")
    print("="*80)
    print(f"\nTotal states captured: {len(captured_states)}")
    print(f"\nSaved to:")
    print(f"  📁 Full history: {history_file}")
    print(f"  📄 Final state:  {final_file}")
    print(f"  📌 Quick access: {sample_file}")
    print(f"  🔄 Real-time:    {CURRENT_STATE_FILE} (updated during game)")
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
