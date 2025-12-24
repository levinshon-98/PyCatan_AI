"""
Show Complete Game State
-------------------------
Runs a game to a specific point and shows the COMPLETE JSON.
"""

import sys
from pathlib import Path
import os
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pycatan.visualizations.web_visualization import WebVisualization

# Capture states
captured_states = []
update_counter = 0

original_update = WebVisualization.update_full_state
original_start_server = WebVisualization.start_server

def capturing_update(self, game_state):
    """Capture and save all states."""
    global update_counter
    original_update(self, game_state)
    
    if hasattr(self, 'current_game_state') and self.current_game_state:
        update_counter += 1
        state_copy = json.loads(json.dumps(self.current_game_state))
        captured_states.append(state_copy)
        
        # Print just a notification
        print(f"\r[Captured state #{update_counter}]", end='', flush=True)

def no_server(self):
    """Disable web server."""
    self.running = True

# Apply patches
WebVisualization.update_full_state = capturing_update
WebVisualization.start_server = no_server


def print_complete_state(state, title="COMPLETE GAME STATE"):
    """Print the complete state in a readable format."""
    print("\n" + "="*80)
    print(f"🎮 {title}")
    print("="*80)
    
    # Print complete JSON
    print(json.dumps(state, indent=2, ensure_ascii=False))
    
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    
    # Summary
    print(f"\n🎲 Game Info:")
    print(f"   Current Player: {state.get('current_player', '?')}")
    print(f"   Game Phase: {state.get('current_phase', '?')}")
    
    if state.get('dice_result'):
        print(f"   Last Dice: {state['dice_result']}")
    
    print(f"\n🗺️  Board:")
    print(f"   Hexes: {len(state.get('hexes', []))}")
    hexes_by_type = {}
    for hex in state.get('hexes', []):
        htype = hex.get('type', 'unknown')
        hexes_by_type[htype] = hexes_by_type.get(htype, 0) + 1
    for htype, count in sorted(hexes_by_type.items()):
        print(f"      - {htype}: {count}")
    
    robber = state.get('robber_position')
    if robber:
        print(f"   Robber: {robber}")
    
    print(f"\n🏘️  Buildings:")
    settlements = state.get('settlements', [])
    cities = state.get('cities', [])
    roads = state.get('roads', [])
    print(f"   Settlements: {len(settlements)}")
    for s in settlements[:5]:  # Show first 5
        print(f"      - Point {s.get('point_id')}: Player {s.get('owner')}")
    if len(settlements) > 5:
        print(f"      ... and {len(settlements)-5} more")
    
    print(f"   Cities: {len(cities)}")
    for c in cities[:5]:
        print(f"      - Point {c.get('point_id')}: Player {c.get('owner')}")
    if len(cities) > 5:
        print(f"      ... and {len(cities)-5} more")
    
    print(f"   Roads: {len(roads)}")
    for r in roads[:5]:
        print(f"      - {r.get('start_point')} -> {r.get('end_point')}: Player {r.get('owner')}")
    if len(roads) > 5:
        print(f"      ... and {len(roads)-5} more")
    
    print(f"\n👥 Players: {len(state.get('players', []))}")
    for player in state.get('players', []):
        print(f"\n   Player {player.get('id')}: {player.get('name', 'Unknown')}")
        print(f"      Victory Points: {player.get('victory_points', 0)}")
        print(f"      Resources: {len(player.get('cards', []))} cards")
        if player.get('cards'):
            card_counts = {}
            for card in player['cards']:
                card_counts[card] = card_counts.get(card, 0) + 1
            print(f"         {dict(card_counts)}")
        print(f"      Dev Cards: {len(player.get('dev_cards', []))}")
        if player.get('dev_cards'):
            print(f"         {player['dev_cards']}")
        print(f"      Knights Played: {player.get('knights_played', 0)}")
        if player.get('has_longest_road'):
            print(f"      🛣️  Has LONGEST ROAD")
        if player.get('has_largest_army'):
            print(f"      ⚔️  Has LARGEST ARMY")
    
    print("\n" + "="*80)


def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = 'examples/data/game_moves_3Players.txt'
    
    print(f"\nRunning game with: {input_file}")
    print("(Web server disabled, capturing states...)\n")
    
    # Read inputs
    with open(input_file, 'r', encoding='utf-8') as f:
        inputs = f.read()
    
    from io import StringIO
    sys.stdin = StringIO(inputs)
    
    try:
        from pycatan import RealGame
        game = RealGame()
        game.run()
        
    except (EOFError, KeyboardInterrupt):
        print("\n\nGame stopped")
    except Exception as e:
        print(f"\n\nError: {e}")
    
    # Show results
    print(f"\n\n{'='*80}")
    print(f"✅ Captured {len(captured_states)} states total")
    print("="*80)
    
    if captured_states:
        # Save all states
        output_dir = Path('examples/ai_testing/captured_states')
        output_dir.mkdir(exist_ok=True)
        
        # Save first state
        first_state = captured_states[0]
        first_file = output_dir / 'state_001_initial.json'
        with open(first_file, 'w', encoding='utf-8') as f:
            json.dump(first_state, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved first state to: {first_file}")
        
        # Save last state
        last_state = captured_states[-1]
        last_file = output_dir / f'state_{len(captured_states):03d}_final.json'
        with open(last_file, 'w', encoding='utf-8') as f:
            json.dump(last_state, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved last state to: {last_file}")
        
        # Also save to sample_states for compatibility
        sample_file = Path('examples/ai_testing/sample_states/captured_game.json')
        sample_file.parent.mkdir(exist_ok=True)
        with open(sample_file, 'w', encoding='utf-8') as f:
            json.dump(last_state, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved to: {sample_file}")
        
        # Print complete final state
        print_complete_state(last_state, "FINAL GAME STATE - THIS IS WHAT AI SEES")
        
        print("\n" + "="*80)
        print("📝 To see full JSON of any state, check the files above")
        print("🌐 To view in browser, run:")
        print(f"   py examples/ai_testing/visualize_game_state.py --state-file {sample_file}")
        print("="*80)
    else:
        print("❌ No states were captured!")


if __name__ == '__main__':
    main()
