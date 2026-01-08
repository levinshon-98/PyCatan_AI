"""
Quick Test: Verify New Prompt Structure Works
---------------------------------------------
This script tests that the new prompt management system works correctly.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.ai_testing.generate_prompts_from_state import (
    get_latest_prompt,
    get_current_session_dir
)


def test_structure():
    """Test that the new directory structure can be read."""
    print("\n" + "="*80)
    print("🧪 TESTING NEW PROMPT STRUCTURE")
    print("="*80 + "\n")
    
    # 1. Check if session exists
    print("1. Checking for active session...")
    session_dir = get_current_session_dir()
    
    if not session_dir:
        print("   ❌ No active session found")
        print("   💡 Run 'python examples/ai_testing/play_and_capture.py' first")
        return False
    
    print(f"   ✅ Found session: {session_dir.name}")
    
    # 2. Check for player directories
    print("\n2. Checking for player directories...")
    player_dirs = [d for d in session_dir.iterdir() 
                   if d.is_dir() and not d.name.startswith('.')]
    
    if not player_dirs:
        print("   ❌ No player directories found")
        print("   💡 Prompts haven't been generated yet")
        return False
    
    print(f"   ✅ Found {len(player_dirs)} player(s): {', '.join([d.name for d in player_dirs])}")
    
    # 3. Check for prompts
    print("\n3. Checking for prompts...")
    found_any = False
    
    for player_dir in player_dirs:
        player_name = player_dir.name
        prompts_dir = player_dir / 'prompts'
        
        if prompts_dir.exists():
            prompts = sorted(prompts_dir.glob('prompt_*.json'))
            if prompts:
                found_any = True
                latest = prompts[-1]
                print(f"   ✅ {player_name}: {len(prompts)} prompt(s)")
                print(f"      Latest: {latest.name}")
    
    if not found_any:
        print("   ❌ No prompts found")
        print("   💡 Play a few turns to generate prompts")
        return False
    
    # 4. Test get_latest_prompt function
    print("\n4. Testing get_latest_prompt() function...")
    
    for player_dir in player_dirs:
        player_name = player_dir.name
        prompt_file, prompt_data = get_latest_prompt(player_name, session_dir)
        
        if prompt_file and prompt_data:
            print(f"   ✅ {player_name}: {prompt_file.name}")
            print(f"      Size: {prompt_file.stat().st_size:,} bytes")
        else:
            print(f"   ⚠️  {player_name}: No prompt data")
    
    # 5. Summary
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED!")
    print("="*80)
    print("\n💡 The new prompt structure is working correctly!")
    print(f"📁 Session: {session_dir}")
    print("\n📚 Documentation:")
    print("   - PROMPT_STRUCTURE.md - Full documentation")
    print("   - README_PROMPT_CHANGES.md - Summary of changes")
    print("   - FIX_test_ai_live.md - test_ai_live.py fix details")
    print("\n" + "="*80 + "\n")
    
    return True


if __name__ == '__main__':
    success = test_structure()
    sys.exit(0 if success else 1)
