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


def capturing_wrapper(original_method):
    """Wrap the update_full_state method to capture all calls."""
    def wrapper(self, game_state=None):
        # Call original
        result = original_method(self, game_state)
        
        # Capture from web visualization
        for viz in self.visualizations:
            if hasattr(viz, 'current_game_state') and viz.current_game_state:
                state_copy = json.loads(json.dumps(viz.current_game_state))
                captured_states.append(state_copy)
                print(f"[Captured state #{len(captured_states)}]", flush=True)
                break  # Only capture once per update
        
        return result
    return wrapper


def save_all_states():
    """Save all captured states to files."""
    if not captured_states:
        print("\n⚠️  No states were captured during this game.")
        return
    
    # Create output directory
    output_dir = Path('examples/ai_testing/my_games')
    output_dir.mkdir(exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save full history
    history_file = output_dir / f'game_{timestamp}_full.json'
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_states': len(captured_states),
            'timestamp': timestamp,
            'states': captured_states
        }, f, indent=2, ensure_ascii=False)
    
    # Save final state
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
    print(f"  📁 Full history: {history_file}")
    print(f"  📄 Final state:  {final_file}")
    print(f"  📌 Quick access: {sample_file}")
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
    print("\nEvery game action will be automatically saved!")
    print("Press Ctrl+C anytime to stop and save.")
    print("="*80 + "\n")
    
    # Patch the VisualizationManager's update_full_state
    from pycatan.visualizations.visualization import VisualizationManager
    VisualizationManager.update_full_state = capturing_wrapper(
        VisualizationManager.update_full_state
    )
    
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
