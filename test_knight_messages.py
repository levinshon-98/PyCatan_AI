"""
Test Knight card messages with tile IDs
"""
from pycatan import Game
from pycatan.card import DevCard
from pycatan.board_definition import board_definition
from pycatan.actions import GamePhase

def test_knight_messages():
    """Test that Knight card shows proper tile IDs in messages."""
    print("\n" + "="*60)
    print("Testing Knight Card Message Formatting")
    print("="*60)
    
    # Create simple game
    game = Game(num_of_players=3)
    game.game_phase = GamePhase.NORMAL_PLAY
    
    # Give player 0 a Knight card
    game.players[0].add_dev_card(DevCard.Knight)
    
    print("\n✓ Game setup complete")
    print(f"  - Player 0 has {len(game.players[0].dev_cards)} Knight card")
    
    # Test using Knight card on tile 5
    print("\n🧪 Testing Knight card with tile ID 5...")
    
    tile_coords = board_definition.hex_id_to_game_coords(5)
    
    if tile_coords:
        row, index = tile_coords
        print(f"  - Tile 5 maps to game coordinates {tile_coords}")
        
        # Prepare args
        args = {
            'robber_pos': [row, index],
            'victim': None
        }
        
        print(f"\n📢 Using Knight card to move robber to tile 5 (coords {tile_coords})")
        
        # Execute
        from pycatan.statuses import Statuses
        status = game.use_dev_card(0, DevCard.Knight, args)
        
        if status == Statuses.ALL_GOOD:
            print("✅ Knight card used successfully!")
            print(f"  - Robber position: {game.board.robber}")
            print(f"  - Player 0 knights: {game.players[0].knight_cards}")
            
            # Verify the message format
            hex_id = board_definition.game_coords_to_hex_id(row, index)
            print(f"\n✨ Message should say: '⚔️ Alice used a Knight card! Robber moved to tile {hex_id}.'")
            print(f"   (Converted {tile_coords} → tile {hex_id})")
        else:
            print(f"❌ Failed with status: {status}")
    else:
        print("  ❌ Could not find tile 5 coordinates")
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)

if __name__ == "__main__":
    test_knight_messages()
