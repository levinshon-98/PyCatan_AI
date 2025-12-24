"""
Play Interactive Game and Auto-Save States
-------------------------------------------
Play Catan interactively in your browser, and all states
are automatically captured and saved to JSON files.

Usage:
    python examples/ai_testing/play_and_save.py
"""

import sys
from pathlib import Path
import json
import signal
import atexit

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pycatan import RealGame
from pycatan.visualizations.web_visualization import WebVisualization

# Global list to capture states
captured_states = []
game_active = False

# Store original functions
original_web_update = WebVisualization.update_full_state
original_display_action = None

try:
    from pycatan.management.game_manager import GameManager
    original_display_action = GameManager.display_action
except:
    pass


def capturing_update(self, game_state):
    """Capture all state updates automatically."""
    global captured_states
    
    # Call original function
    original_web_update(self, game_state)
    
    # Capture the state
    if hasattr(self, 'current_game_state') and self.current_game_state:
        state_copy = json.loads(json.dumps(self.current_game_state))
        captured_states.append(state_copy)
        
        # Print notification (less verbose)
        if len(captured_states) % 5 == 0 or len(captured_states) == 1:
            print(f"[Captured {len(captured_states)} states so far...]", flush=True)


def capturing_display_action(self, action, result=None):
    """Hook into display_action to capture after each action."""
    # Call original
    if original_display_action:
        original_display_action(self, action, result)
    
    # Force a state capture by updating all visualizations
    if hasattr(self, 'visualization_manager'):
        try:
            self.visualization_manager.update_full_state(self.game.get_state())
        except:
            pass


def save_all_states():
    """Save all captured states to files."""
    if not captured_states:
        print("\n⚠️  No states were captured during this game.")
        return
    
    # Create output directory
    output_dir = Path('examples/ai_testing/my_games')
    output_dir.mkdir(exist_ok=True)
    
    # Generate timestamp for unique filename
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save full game history
    history_file = output_dir / f'game_{timestamp}_full.json'
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_states': len(captured_states),
            'timestamp': timestamp,
            'states': captured_states
        }, f, indent=2, ensure_ascii=False)
    
    # Save just the final state
    final_file = output_dir / f'game_{timestamp}_final.json'
    with open(final_file, 'w', encoding='utf-8') as f:
        json.dump(captured_states[-1], f, indent=2, ensure_ascii=False)
    
    # Also save to standard location
    sample_file = Path('examples/ai_testing/sample_states/captured_game.json')
    sample_file.parent.mkdir(exist_ok=True)
    with open(sample_file, 'w', encoding='utf-8') as f:
        json.dump(captured_states[-1], f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*80)
    print("✅ GAME SAVED SUCCESSFULLY!")
    print("="*80)
    print(f"\nTotal states captured: {len(captured_states)}")
    print(f"\nSaved to:")
    print(f"  📁 Full game history: {history_file}")
    print(f"  📄 Final state:       {final_file}")
    print(f"  📌 Standard location: {sample_file}")
    print("\n" + "="*80)
    
    # Print summary
    if captured_states:
        final_state = captured_states[-1]
        print("\n📊 FINAL GAME STATE:")
        print(f"  Current Phase: {final_state.get('current_phase', 'UNKNOWN')}")
        print(f"  Settlements: {len(final_state.get('settlements', []))}")
        print(f"  Cities: {len(final_state.get('cities', []))}")
        print(f"  Roads: {len(final_state.get('roads', []))}")
        print(f"  Players: {len(final_state.get('players', []))}")
        print("="*80)


# Register save function to run on exit
atexit.register(save_all_states)


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\n🛑 Game interrupted by user...")
    save_all_states()
    sys.exit(0)


# Register signal handler
signal.signal(signal.SIGINT, signal_handler)


def main():
    global game_active
    
    print("="*80)
    print("🎮 INTERACTIVE CATAN WITH AUTO-SAVE")
    print("="*80)
    print("\nPlay the game normally in your browser.")
    print("All states will be automatically captured and saved!")
    print("\nPress Ctrl+C at any time to stop and save.")
    print("="*80 + "\n")
    
    # Apply the patches
    WebVisualization.update_full_state = capturing_update
    
    # Also patch GameManager if available
    if original_display_action:
        from pycatan.management.game_manager import GameManager
        GameManager.display_action = capturing_display_action
    
    try:
        # Start the game
        game_active = True
        game = RealGame()
        game.run()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Game stopped by user")
    except EOFError:
        print("\n\n✅ Game completed")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        game_active = False
        # save_all_states() will be called by atexit


if __name__ == '__main__':
    main()
