#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Play Catan with AI Agents (Manual Mode)
---------------------------------------

This script starts a Catan game where AI agents generate prompts
but YOU enter their moves manually. This is useful for:
- Testing the AI prompt system
- Understanding what the AI "sees"
- Debugging AI decision making
- Training data collection

How it works:
1. AI agents are registered for each player
2. When it's an AI player's turn, a prompt is generated and saved
3. You see the prompt info and enter what action the AI should take
4. The game executes that action

All prompts and interactions are logged for later analysis.

Usage:
    python examples/ai_testing/play_with_ai.py
    
    # Or with options:
    python examples/ai_testing/play_with_ai.py --players 3 --auto-llm
"""

import sys
import os
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import List, Optional
import webbrowser
import threading
import time
from pycatan.management.game_manager import GameManager
from pycatan.players.human_user import HumanUser
from pycatan.ai import AIManager, AIUser, AIConfig
from pycatan.visualizations.web_visualization import WebVisualization
from pycatan.visualizations.visualization import VisualizationManager

# Configure stdout for UTF-8 on Windows
import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def print_banner():
    """Print the welcome banner."""
    print("=" * 70)
    print("[AI] PYCATAN WITH AI AGENTS")
    print("=" * 70)
    print()
    print("All players are AI - you enter their moves manually.")
    print()


def setup_game() -> tuple:
    """
    Simple setup - ask how many players and their names.
    All players are AI agents (manual input mode).
    
    Returns:
        Tuple of (num_players, player_configs)
    """
    print_banner()
    
    # Default player colors and names
    colors = ["Red", "Blue", "White", "Orange"]
    default_names = ["Alice", "Bob", "Charlie", "Diana"]
    
    # Get number of players
    while True:
        try:
            num_str = input("How many players? (2-4) [3]: ").strip()
            if not num_str:
                num_players = 3
            else:
                num_players = int(num_str)
            
            if 2 <= num_players <= 4:
                break
            else:
                print("Enter 2-4")
        except ValueError:
            print("Enter a number")
    
    # Get player names
    print(f"\nEnter names (or press Enter for default):")
    player_configs = []
    for i in range(num_players):
        name = input(f"  Player {i+1} ({colors[i]}) [{default_names[i]}]: ").strip()
        if not name:
            name = default_names[i]
        player_configs.append({
            "name": name,
            "is_ai": True,
            "color": colors[i]
        })
    
    # Brief summary
    names = [p["name"] for p in player_configs]
    print(f"\nPlayers: {', '.join(names)}")
    print()
    
    return num_players, player_configs


def create_game(player_configs: List[dict], send_to_llm: bool = True, manual_actions: bool = True) -> tuple:
    """
    Create the game with configured players.
    
    Args:
        player_configs: List of player configuration dicts
        send_to_llm: If True, sends prompts to LLM (shows suggestions)
        manual_actions: If True, user enters actions manually
        
    Returns:
        Tuple of (game_manager, ai_manager, web_viz)
    """
    # Create AIManager (shared between all AI players)
    ai_manager = AIManager(
        config=AIConfig(),
        send_to_llm=send_to_llm,
        manual_actions=manual_actions
    )
    
    # Create user objects
    users = []
    for i, cfg in enumerate(player_configs):
        if cfg["is_ai"]:
            # Create AI user
            user = AIUser(
                name=cfg["name"],
                user_id=i,
                ai_manager=ai_manager,
                color=cfg["color"]
            )
        else:
            # Create human user
            user = HumanUser(cfg["name"], i)
        
        users.append(user)
    
    # Create game manager
    game_manager = GameManager(users)
    
    # Setup web visualization
    web_viz = WebVisualization(port=5000, auto_open=False, debug=False)
    viz_manager = VisualizationManager()
    viz_manager.add_visualization(web_viz)
    game_manager.visualization_manager = viz_manager
    
    print(f"\n[OK] Game created!")
    print(f"[LOG] Session: {ai_manager.get_session_path()}")
    print()
    
    return game_manager, ai_manager, web_viz


def run_game(game_manager: GameManager, ai_manager: AIManager, web_viz: WebVisualization):
    """
    Run the main game loop.
    
    Args:
        game_manager: The GameManager instance
        ai_manager: The AIManager instance
        web_viz: The WebVisualization instance
    """
    # Start web server in background
    web_viz.start_server()
    
    # Open browser
    webbrowser.open("http://localhost:5000")
    
    print("=" * 70)
    print("[GAME] GAME STARTING!")
    print("[WEB] Board: http://localhost:5000")
    print("=" * 70)
    print()
    print("Commands:")
    print("  s <node>     - Place settlement (e.g., s 14)")
    print("  rd <n1> <n2> - Place road (e.g., rd 14 15)")
    print("  r            - Roll dice")
    print("  e            - End turn")
    print("  help         - Show all commands")
    print()
    print("=" * 70)
    print()
    
    try:
        # Initialize the game
        game_manager.start_game()
        
        # Run the main game loop
        game_manager.game_loop()
        
        print("\n" + "=" * 70)
        print("[WIN] GAME OVER!")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n[!] Game interrupted by user")
    except Exception as e:
        print(f"\n\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Save session
        print("\n[SAVE] Saving session...")
        ai_manager.save_session()
        print(f"[LOG] Session saved to: {ai_manager.get_session_path()}")
        
        # Show stats
        print("\n[STATS] AI Agent Statistics:")
        stats = ai_manager.get_stats()
        for name, agent_stats in stats.items():
            print(f"   {name}: {agent_stats['total_requests']} requests, "
                  f"{agent_stats['total_tokens_used']} tokens")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Play Catan with AI agents")
    parser.add_argument("--no-llm", action="store_true",
                       help="Don't send prompts to LLM (offline mode)")
    parser.add_argument("--auto", action="store_true",
                       help="Let AI play automatically (no manual input)")
    parser.add_argument("--players", type=int, choices=[2, 3, 4],
                       help="Number of players (skip setup)")
    parser.add_argument("--all-ai", action="store_true",
                       help="Make all players AI (skip setup)")
    args = parser.parse_args()
    
    # Quick setup mode
    if args.players and args.all_ai:
        colors = ["Red", "Blue", "White", "Orange"]
        player_configs = [
            {"name": f"AI_{i+1}", "is_ai": True, "color": colors[i]}
            for i in range(args.players)
        ]
        print_banner()
        print(f"Quick setup: {args.players} AI players")
    else:
        # Interactive setup
        num_players, player_configs = setup_game()
    
    # Determine mode
    send_to_llm = not args.no_llm  # Default: send to LLM
    manual_actions = not args.auto  # Default: manual input
    
    print(f"[MODE] LLM: {'ON' if send_to_llm else 'OFF'} | Actions: {'Manual' if manual_actions else 'Auto'}")
    
    # Create game
    game_manager, ai_manager, web_viz = create_game(
        player_configs,
        send_to_llm=send_to_llm,
        manual_actions=manual_actions
    )
    
    # Run game
    run_game(game_manager, ai_manager, web_viz)


if __name__ == "__main__":
    main()
