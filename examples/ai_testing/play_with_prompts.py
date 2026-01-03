"""
Play Catan with Auto-Generated Prompts
---------------------------------------
This version generates AI prompts for each player at the START of every turn.

During the game, you'll see:
- Game proceeds normally
- At each turn start, prompts are automatically generated for all players
- Prompts are saved to: examples/ai_testing/my_games/prompts/

This lets you see exactly what each AI agent would receive as input.
"""

import sys
from pathlib import Path
import subprocess
import time
import threading

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import the original capture script's functionality
from examples.ai_testing import play_and_capture

# Import prompt generator
from examples.ai_testing.generate_prompts_from_state import main as generate_prompts


def prompt_generator_thread():
    """
    Background thread that watches for state changes and generates prompts.
    """
    state_file = Path('examples/ai_testing/my_games/current_state_optimized.txt')
    full_state_file = Path('examples/ai_testing/my_games/current_state.json')
    last_modified = 0
    
    print("\n[🤖 Prompt Generator Active - will generate prompts on state changes]")
    
    while True:
        try:
            # Check both files - use the most recent modification time
            current_modified = 0
            
            if state_file.exists():
                current_modified = max(current_modified, state_file.stat().st_mtime)
            
            if full_state_file.exists():
                current_modified = max(current_modified, full_state_file.stat().st_mtime)
            
            if current_modified > 0:
                # If file was modified, generate prompts
                if current_modified > last_modified:
                    last_modified = current_modified
                    
                    # Wait a bit to ensure BOTH files are fully written (optimized + full state)
                    time.sleep(0.3)
                    
                    print("\n" + "🔄 " + "-"*70)
                    print("🔄 State changed - generating AI prompts for all players...")
                    print("🔄 " + "-"*70)
                    
                    try:
                        # Generate prompts
                        generate_prompts()
                        print("🔄 " + "-"*70)
                        print("✅ Prompts generated! Check examples/ai_testing/my_games/prompts/")
                        print("🔄 " + "-"*70 + "\n")
                    except Exception as e:
                        print(f"⚠️ Error generating prompts: {e}\n")
            
            # Check every 0.5 seconds
            time.sleep(0.5)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            # Ignore errors silently
            time.sleep(1)


def main():
    """Main entry point."""
    print("="*80)
    print("🎮 CATAN WITH AUTO-GENERATED AI PROMPTS")
    print("="*80)
    print("\n📝 This version automatically generates AI prompts for each player!")
    print("📁 Prompts saved to: examples/ai_testing/my_games/prompts/")
    print("⏱️  Prompts generated at the START of each turn")
    print("\n" + "="*80 + "\n")
    
    # Start prompt generator thread
    generator = threading.Thread(target=prompt_generator_thread, daemon=True)
    generator.start()
    
    # Give thread time to start
    time.sleep(0.5)
    
    # Run the game (this will block)
    try:
        play_and_capture.main()
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
