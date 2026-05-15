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
import ssl
import json
from pathlib import Path

# Fix SSL certificate verification on Windows (must be before any other imports)
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH'] = certifi.where()
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import List, Optional, Dict, Any
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


LOGS_DIR = Path("examples") / "ai_testing" / "my_games"


def resolve_session_path(session_ref: str) -> Path:
    """Resolve a replay session name/path."""
    path = Path(session_ref)
    if path.is_absolute() and path.exists():
        return path
    if path.exists():
        return path

    session_path = LOGS_DIR / session_ref
    if session_path.exists():
        return session_path

    raise FileNotFoundError(f"Replay session not found: {session_ref}")


def _parse_replay_marker(value: Optional[str]) -> Optional[tuple[str, int]]:
    """Parse a replay marker in the form Player:request_number."""
    if not value:
        return None
    if ":" not in value:
        raise ValueError("Replay marker must be in the form Player:request_number")
    player, request_number = value.split(":", 1)
    return player.strip(), int(request_number.strip())


def _marker_matches(decision: Dict[str, Any], marker: tuple[str, int]) -> bool:
    player_name, request_number = marker
    return (
        decision["player_name"].lower() == player_name.lower()
        and decision["request_number"] == request_number
    )


def _first_response_timestamp(player_dir: Path) -> str:
    responses_dir = player_dir / "responses"
    if not responses_dir.exists():
        return ""

    timestamps = []
    for response_file in responses_dir.glob("response_*.json"):
        try:
            data = json.loads(response_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("timestamp"):
            timestamps.append(str(data["timestamp"]))

    return min(timestamps) if timestamps else ""


def infer_players_from_session(session_dir: Path) -> List[str]:
    """Infer player names from session folders, preserving original turn order when possible."""
    ignored = {"prompts", "responses", "intermediate"}
    players = []
    for child in sorted(session_dir.iterdir(), key=lambda p: p.name.lower()):
        if child.is_dir() and child.name not in ignored:
            if (child / "responses").exists() or (child / "prompts").exists():
                players.append((child.name, _first_response_timestamp(child)))

    # In setup, first response order is the player order. Fall back to name order for
    # empty/incomplete folders.
    players.sort(key=lambda item: (item[1] == "", item[1], item[0].lower()))
    return [name for name, _timestamp in players]


def load_replay_decisions(
    session_dir: Path,
    max_decisions: Optional[int] = None,
    replay_through: Optional[str] = None,
    replay_stop_before: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Load parsed final responses from a previous session in chronological order."""
    through_marker = _parse_replay_marker(replay_through)
    stop_before_marker = _parse_replay_marker(replay_stop_before)
    decisions = []

    for player_dir in session_dir.iterdir():
        responses_dir = player_dir / "responses"
        if not responses_dir.exists():
            continue

        for response_file in responses_dir.glob("response_*.json"):
            if response_file.parent.name == "intermediate":
                continue
            try:
                data = json.loads(response_file.read_text(encoding="utf-8"))
            except Exception:
                continue

            parsed = data.get("parsed")
            if not parsed or not parsed.get("action_type"):
                continue

            decisions.append({
                "player_name": data.get("player_name") or player_dir.name,
                "request_number": int(data.get("request_number", 0)),
                "timestamp": data.get("timestamp", ""),
                "parsed": parsed,
                "source_file": str(response_file),
            })

    decisions.sort(key=lambda item: (item.get("timestamp", ""), item.get("player_name", ""), item.get("request_number", 0)))

    for marker_name, marker in [("replay-through", through_marker), ("replay-stop-before", stop_before_marker)]:
        if marker and not any(_marker_matches(decision, marker) for decision in decisions):
            raise ValueError(
                f"{marker_name} marker not found in session: {marker[0]}:{marker[1]}"
            )

    selected = []
    for decision in decisions:
        if stop_before_marker and _marker_matches(decision, stop_before_marker):
            break

        selected.append(decision)

        if through_marker and _marker_matches(decision, through_marker):
            break
        if max_decisions and len(selected) >= max_decisions:
            break

    return selected


def group_replay_decisions(decisions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group replay decisions by player, preserving chronological order per player."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for decision in decisions:
        grouped.setdefault(decision["player_name"], []).append(decision)
    return grouped


def annotate_replay_session(
    ai_manager: AIManager,
    source_session: Path,
    decisions: List[Dict[str, Any]],
    replay_through: Optional[str],
    replay_stop_before: Optional[str]
) -> None:
    """Write lineage metadata into the newly created session."""
    metadata_file = ai_manager.get_session_path() / "session_metadata.json"
    metadata = {}
    if metadata_file.exists():
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

    metadata["derived_from"] = str(source_session)
    metadata["replay"] = {
        "source_session": source_session.name,
        "decisions_loaded": len(decisions),
        "replay_through": replay_through,
        "replay_stop_before": replay_stop_before,
        "mode": "fast_action_replay_then_live_ai",
    }

    metadata_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


class ReplayAIUser(AIUser):
    """AI user that first replays recorded parsed decisions, then falls back to live AI."""

    def __init__(
        self,
        name: str,
        user_id: int,
        ai_manager: AIManager,
        color: str = "",
        replay_decisions: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(name=name, user_id=user_id, ai_manager=ai_manager, color=color)
        self.replay_decisions = list(replay_decisions or [])

    def get_input(self, game_state, prompt_message: str, allowed_actions: Optional[List[str]] = None):
        if self.replay_decisions:
            replay_item = self.replay_decisions[0]
            decision = dict(replay_item["parsed"])
            action = self._decision_to_action(decision, allowed_actions)

            if allowed_actions and action.action_type.name not in allowed_actions:
                print(
                    f"[REPLAY] {self.name} #{replay_item['request_number']} no longer matches "
                    f"allowed actions {allowed_actions}; switching {self.name} to live AI."
                )
                self.replay_decisions.clear()
                return super().get_input(game_state, prompt_message, allowed_actions)

            self.replay_decisions.pop(0)
            self._apply_replay_memory_and_chat(decision)
            print(
                f"[REPLAY] {self.name} #{replay_item['request_number']}: "
                f"{decision.get('action_type')} {decision.get('parameters', {})}"
            )
            return action

        return super().get_input(game_state, prompt_message, allowed_actions)

    def _apply_replay_memory_and_chat(self, decision: Dict[str, Any]) -> None:
        agent = self.ai_manager.agents.get(self.name)
        note_to_self = decision.get("note_to_self")
        if agent and note_to_self:
            agent.update_memory(note_to_self)
            self.ai_manager.logger.save_agent_memories(self.ai_manager.agents)

        say_outloud = decision.get("say_outloud")
        if say_outloud:
            self.ai_manager._broadcast_chat(self.name, say_outloud)


def load_env_file(env_path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE entries from .env without requiring python-dotenv."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_ai_config(config_path: Optional[str] = None) -> AIConfig:
    """Load explicit config, then config_dev.yaml, then defaults."""
    if config_path:
        return AIConfig.from_file(config_path)

    default_config = Path("pycatan") / "ai" / "config_dev.yaml"
    if default_config.exists():
        return AIConfig.from_file(str(default_config))

    return AIConfig()


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


def create_game(
    player_configs: List[dict],
    send_to_llm: bool = True,
    manual_actions: bool = True,
    config: Optional[AIConfig] = None,
    replay_decisions: Optional[Dict[str, List[Dict[str, Any]]]] = None
) -> tuple:
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
        config=config or AIConfig(),
        send_to_llm=send_to_llm,
        manual_actions=manual_actions
    )
    
    # Create user objects
    users = []
    replay_decisions = replay_decisions or {}
    for i, cfg in enumerate(player_configs):
        if cfg["is_ai"]:
            if cfg["name"] in replay_decisions:
                user = ReplayAIUser(
                    name=cfg["name"],
                    user_id=i,
                    ai_manager=ai_manager,
                    color=cfg["color"],
                    replay_decisions=replay_decisions[cfg["name"]]
                )
            else:
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
    
    # Create game manager with optional random seed for reproducibility
    # Use random_seed=0 for deterministic games, or None for random
    game_manager = GameManager(users, random_seed=0)
    
    # Setup web visualization
    web_viz = WebVisualization(port=5000, auto_open=False, debug=False)
    viz_manager = VisualizationManager()
    viz_manager.add_visualization(web_viz)
    game_manager.visualization_manager = viz_manager
    
    # Connect AI chat to web visualization
    ai_manager.set_chat_callback(lambda player, msg: web_viz.display_chat(player, msg))
    
    # Connect AI status updates to web visualization
    ai_manager.set_status_callback(lambda player, status, details: web_viz.display_ai_status(player, status, details))
    
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
    
    # Don't open browser here - batch file already opens unified view
    # webbrowser.open("http://localhost:5000")
    
    print("=" * 70)
    print("[GAME] GAME STARTING!")
    print("[WEB] Board: http://localhost:5000/unified")
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
    parser.add_argument("--names", type=str, nargs="+",
                       help="Custom names for AI players (e.g., --names Alice Bob Charlie). Also sets player count.")
    parser.add_argument("--config", type=str,
                       help="Path to AI config YAML. Defaults to pycatan/ai/config_dev.yaml when present.")
    parser.add_argument("--replay-session", type=str,
                       help="Fast-replay parsed actions from an existing session, then continue live.")
    parser.add_argument("--resume-session", type=str,
                       help="Alias for --replay-session.")
    parser.add_argument("--replay-max-decisions", type=int,
                       help="Maximum number of parsed decisions to replay.")
    parser.add_argument("--replay-through", type=str,
                       help="Replay through a marker like Alice:5, inclusive.")
    parser.add_argument("--replay-stop-before", type=str,
                       help="Stop replay before a marker like Alice:6.")
    args = parser.parse_args()

    load_env_file()
    ai_config = load_ai_config(args.config)
    replay_session_ref = args.replay_session or args.resume_session
    replay_session_path = resolve_session_path(replay_session_ref) if replay_session_ref else None
    replay_decision_list: List[Dict[str, Any]] = []
    replay_decisions_by_player: Dict[str, List[Dict[str, Any]]] = {}
    replay_player_names: List[str] = []
    if replay_session_path:
        replay_decision_list = load_replay_decisions(
            replay_session_path,
            max_decisions=args.replay_max_decisions,
            replay_through=args.replay_through,
            replay_stop_before=args.replay_stop_before
        )
        replay_decisions_by_player = group_replay_decisions(replay_decision_list)
        replay_player_names = infer_players_from_session(replay_session_path)
        print(f"[REPLAY] Source: {replay_session_path}")
        print(f"[REPLAY] Loaded {len(replay_decision_list)} parsed decisions")
    
    # Quick setup mode - either explicit --players or inferred from --names
    num_players = args.players
    
    # If names provided, infer player count from names (unless explicitly set)
    if args.names:
        if not num_players:
            num_players = min(len(args.names), 4)  # Max 4 players
            if num_players < 2:
                num_players = 2  # Min 2 players
        args.all_ai = True  # Names implies all-ai mode
    elif replay_session_path and replay_player_names:
        num_players = min(len(replay_player_names), 4)
        args.names = replay_player_names[:num_players]
        args.all_ai = True
    
    if num_players and args.all_ai:
        colors = ["Red", "Blue", "White", "Orange"]
        default_names = ["Alice", "Bob", "Charlie", "Diana"]
        
        # Use custom names if provided, otherwise use defaults
        if args.names:
            names = args.names[:num_players]
            # Pad with defaults if not enough names provided
            while len(names) < num_players:
                names.append(default_names[len(names)])
        else:
            names = default_names[:num_players]
        
        player_configs = [
            {"name": names[i], "is_ai": True, "color": colors[i]}
            for i in range(num_players)
        ]
        print_banner()
        print(f"Quick setup: {num_players} AI players - {', '.join(names)}")
    else:
        # Interactive setup
        num_players, player_configs = setup_game()
    
    # Determine mode
    send_to_llm = not args.no_llm  # Default: send to LLM
    manual_actions = not args.auto  # Default: manual input
    
    print(f"[MODE] LLM: {'ON' if send_to_llm else 'OFF'} | Actions: {'Manual' if manual_actions else 'Auto'}")
    print(f"[CONFIG] {ai_config.llm.provider}/{ai_config.llm.model_name}")
    
    # Create game
    game_manager, ai_manager, web_viz = create_game(
        player_configs,
        send_to_llm=send_to_llm,
        manual_actions=manual_actions,
        config=ai_config,
        replay_decisions=replay_decisions_by_player
    )
    if replay_session_path:
        annotate_replay_session(
            ai_manager,
            replay_session_path,
            replay_decision_list,
            args.replay_through,
            args.replay_stop_before
        )
        print(f"[REPLAY] New derived session: {ai_manager.get_session_path()}")
    
    # Run game
    run_game(game_manager, ai_manager, web_viz)


if __name__ == "__main__":
    main()
