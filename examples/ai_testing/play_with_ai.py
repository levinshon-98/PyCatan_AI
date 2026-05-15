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
import html as html_lib
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
from pycatan.management.game_manager import GameManager
from pycatan.players.human_user import HumanUser
from pycatan.ai import AIManager, AIUser, AIConfig
from pycatan.ai.config import normalize_chat_language
from pycatan.visualizations.web_visualization import WebVisualization
from pycatan.visualizations.visualization import VisualizationManager

# Configure stdout for UTF-8 on Windows
import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


LOGS_DIR = Path("examples") / "ai_testing" / "my_games"


GEMINI_TEXT_MODELS = [
    {
        "id": "gemini-3-flash-preview",
        "label": "Gemini 3 Flash Preview",
        "note": "Recommended for this game: fast, capable, supports tools and structured JSON.",
    },
    {
        "id": "gemini-3.1-pro-preview",
        "label": "Gemini 3.1 Pro Preview",
        "note": "Highest reasoning option; slower and usually more expensive.",
    },
    {
        "id": "gemini-3.1-flash-lite",
        "label": "Gemini 3.1 Flash-Lite",
        "note": "Stable low-latency option for cheaper runs.",
    },
    {
        "id": "gemini-3.1-flash-lite-preview",
        "label": "Gemini 3.1 Flash-Lite Preview",
        "note": "Preview low-latency option with structured output support.",
    },
    {
        "id": "gemini-2.5-flash",
        "label": "Gemini 2.5 Flash",
        "note": "Stable price-performance model with tools and structured output.",
    },
    {
        "id": "gemini-2.5-pro",
        "label": "Gemini 2.5 Pro",
        "note": "Stable stronger reasoning model.",
    },
    {
        "id": "gemini-2.5-flash-lite",
        "label": "Gemini 2.5 Flash-Lite",
        "note": "Stable budget model.",
    },
]

ELEVENLABS_TTS_MODELS = [
    {
        "id": "eleven_v3",
        "label": "Eleven v3",
        "note": "Best quality and Hebrew support; recommended for natural Hebrew table talk.",
    },
    {
        "id": "eleven_multilingual_v2",
        "label": "Eleven Multilingual v2",
        "note": "Good multilingual quality; useful fallback if v3 is too slow or inconsistent.",
    },
    {
        "id": "eleven_flash_v2_5",
        "label": "Eleven Flash v2.5",
        "note": "Fast and cheaper; best if you switch table talk back to English or another supported v2.5 language.",
    },
    {
        "id": "eleven_turbo_v2_5",
        "label": "Eleven Turbo v2.5",
        "note": "Low-latency quality/speed balance; useful fallback for supported languages.",
    },
]

DEFAULT_PLAYER_NAMES = ["Alice", "Bob", "Charlie", "Diana"]
PLAYER_COLORS = ["Red", "Blue", "White", "Orange"]


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


def load_replay_decision_chain(
    session_dir: Path,
    max_decisions: Optional[int] = None,
    replay_through: Optional[str] = None,
    replay_stop_before: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Load replay decisions needed to reconstruct a session.

    Derived sessions only contain the live decisions made after their own replay
    prefix. To replay from a derived session, first replay its lineage metadata,
    then append this session's local decisions.
    """
    prefix: List[Dict[str, Any]] = []
    metadata_file = session_dir / "session_metadata.json"
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        except Exception:
            metadata = {}

        derived_from = metadata.get("derived_from")
        replay_meta = metadata.get("replay") or {}
        if derived_from:
            parent_session = resolve_session_path(derived_from)
            prefix = load_replay_decision_chain(
                parent_session,
                replay_through=replay_meta.get("replay_through"),
                replay_stop_before=replay_meta.get("replay_stop_before")
            )

    local = load_replay_decisions(
        session_dir,
        replay_through=replay_through,
        replay_stop_before=replay_stop_before
    )
    decisions = prefix + local
    if max_decisions:
        decisions = decisions[:max_decisions]
    return decisions


def group_replay_decisions(decisions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group replay decisions by player, preserving chronological order per player."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for decision in decisions:
        grouped.setdefault(decision["player_name"], []).append(decision)
    return grouped


class ReplayExhausted(Exception):
    """Raised by watch-only replay when no recorded decision exists."""


def annotate_replay_session(
    ai_manager: AIManager,
    source_session: Path,
    decisions: List[Dict[str, Any]],
    replay_through: Optional[str],
    replay_stop_before: Optional[str],
    mode: str = "fast_action_replay_then_live_ai"
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
        "mode": mode,
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
        replay_decisions: Optional[List[Dict[str, Any]]] = None,
        replay_chat: bool = True,
        replay_speak: bool = False,
        replay_only: bool = False
    ):
        super().__init__(name=name, user_id=user_id, ai_manager=ai_manager, color=color)
        self.replay_decisions = list(replay_decisions or [])
        self.replay_chat = replay_chat
        self.replay_speak = replay_speak
        self.replay_only = replay_only
        self.last_replay_item: Optional[Dict[str, Any]] = None

    def get_input(self, game_state, prompt_message: str, allowed_actions: Optional[List[str]] = None):
        if self.replay_decisions:
            replay_item = self.replay_decisions[0]
            decision = dict(replay_item["parsed"])
            action = self._decision_to_action(decision, allowed_actions)

            if allowed_actions and action.action_type.name not in allowed_actions:
                if self.replay_only:
                    raise ReplayExhausted(
                        f"{self.name} #{replay_item['request_number']} no longer matches "
                        f"allowed actions {allowed_actions}"
                    )
                print(
                    f"[REPLAY] {self.name} #{replay_item['request_number']} no longer matches "
                    f"allowed actions {allowed_actions}; switching {self.name} to live AI."
                )
                self.replay_decisions.clear()
                return super().get_input(game_state, prompt_message, allowed_actions)

            self.last_replay_item = self.replay_decisions.pop(0)
            self._apply_replay_memory_and_chat(decision, game_state)
            print(
                f"[REPLAY] {self.name} #{replay_item['request_number']}: "
                f"{decision.get('action_type')} {decision.get('parameters', {})}"
            )
            return action

        if self.replay_only:
            raise ReplayExhausted(f"No more recorded replay decisions for {self.name}")

        return super().get_input(game_state, prompt_message, allowed_actions)

    def _apply_replay_memory_and_chat(
        self,
        decision: Dict[str, Any],
        game_state: Optional[Dict[str, Any]] = None
    ) -> None:
        agent = self.ai_manager.agents.get(self.name)
        note_to_self = decision.get("note_to_self")
        if agent and note_to_self:
            agent.update_memory(note_to_self)
            self.ai_manager._maybe_compact_agent_memory(agent, game_state)
            self.ai_manager.logger.save_agent_memories(self.ai_manager.agents)

        say_outloud = decision.get("say_outloud")
        if self.replay_chat and say_outloud:
            self.ai_manager._broadcast_chat(
                self.name,
                say_outloud,
                speak=self.replay_speak
            )


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


def _render_browser_settings_page(
    errors: Optional[List[str]] = None,
    selected_model: str = "gemini-3-flash-preview",
    selected_chat_language: str = "english",
    selected_tts_provider: str = "gemini",
    selected_tts_model: str = "eleven_v3",
    selected_gemini_tts_model: str = "gemini-2.5-flash-preview-tts",
    selected_gemini_tts_voice: str = "Kore",
    player_count: int = 3,
    player_names: Optional[List[str]] = None
) -> str:
    """Render the temporary browser setup form."""
    player_names = player_names or DEFAULT_PLAYER_NAMES
    errors_html = ""
    if errors:
        error_items = "".join(f"<li>{html_lib.escape(error)}</li>" for error in errors)
        errors_html = f"<div class=\"errors\"><ul>{error_items}</ul></div>"

    model_options = []
    for model in GEMINI_TEXT_MODELS:
        selected = " selected" if model["id"] == selected_model else ""
        model_options.append(
            f"<option value=\"{html_lib.escape(model['id'])}\"{selected}>"
            f"{html_lib.escape(model['label'])} - {html_lib.escape(model['id'])}"
            "</option>"
        )

    model_notes = "".join(
        "<li><strong>"
        + html_lib.escape(model["id"])
        + "</strong>: "
        + html_lib.escape(model["note"])
        + "</li>"
        for model in GEMINI_TEXT_MODELS
    )

    tts_model_options = []
    for model in ELEVENLABS_TTS_MODELS:
        selected = " selected" if model["id"] == selected_tts_model else ""
        tts_model_options.append(
            f"<option value=\"{html_lib.escape(model['id'])}\"{selected}>"
            f"{html_lib.escape(model['label'])} - {html_lib.escape(model['id'])}"
            "</option>"
        )

    tts_model_notes = "".join(
        "<li><strong>"
        + html_lib.escape(model["id"])
        + "</strong>: "
        + html_lib.escape(model["note"])
        + "</li>"
        for model in ELEVENLABS_TTS_MODELS
    )

    gemini_tts_models = [
        "gemini-2.5-flash-preview-tts",
        "gemini-2.5-pro-preview-tts",
        "gemini-3.1-flash-tts-preview",
        "gemini-3.1-pro-tts-preview",
    ]
    gemini_tts_model_options = []
    for model_id in gemini_tts_models:
        selected = " selected" if model_id == selected_gemini_tts_model else ""
        gemini_tts_model_options.append(
            f"<option value=\"{html_lib.escape(model_id)}\"{selected}>"
            f"{html_lib.escape(model_id)}</option>"
        )

    gemini_tts_voices = [
        "Kore", "Puck", "Zephyr", "Charon", "Fenrir", "Leda", "Orus",
        "Aoede", "Callirrhoe", "Autonoe", "Enceladus", "Iapetus",
        "Umbriel", "Algieba", "Despina", "Erinome", "Algenib",
        "Rasalgethi", "Laomedeia", "Achernar", "Alnilam", "Schedar",
        "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
        "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
    ]
    gemini_tts_voice_options = []
    for voice in gemini_tts_voices:
        selected = " selected" if voice == selected_gemini_tts_voice else ""
        gemini_tts_voice_options.append(
            f"<option value=\"{html_lib.escape(voice)}\"{selected}>"
            f"{html_lib.escape(voice)}</option>"
        )

    player_inputs = []
    for index in range(4):
        value = player_names[index] if index < len(player_names) and player_names[index] else DEFAULT_PLAYER_NAMES[index]
        player_inputs.append(
            f"""
            <label class="player-field" data-player-index="{index + 1}">
                <span>Player {index + 1} ({PLAYER_COLORS[index]})</span>
                <input name="player_{index + 1}" value="{html_lib.escape(value)}" maxlength="32">
            </label>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PyCatan AI Setup</title>
    <style>
        :root {{
            --bg: #edf1f5;
            --ink: #1f2933;
            --muted: #68717d;
            --line: #cbd5df;
            --panel: #ffffff;
            --accent: #246b5b;
            --accent-dark: #17483d;
            --danger: #b42318;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            font-family: "Segoe UI", Arial, sans-serif;
            background: var(--bg);
            color: var(--ink);
            display: grid;
            place-items: center;
            padding: 24px;
        }}
        main {{
            width: min(980px, 100%);
            display: grid;
            grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
            gap: 22px;
            align-items: start;
        }}
        section, aside {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            box-shadow: 0 18px 45px rgba(31, 41, 51, 0.12);
        }}
        section {{ padding: 28px; }}
        aside {{ padding: 22px; }}
        h1, h2 {{ margin: 0; }}
        h1 {{ font-size: 30px; line-height: 1.15; }}
        h2 {{ font-size: 17px; margin-bottom: 12px; }}
        p {{ color: var(--muted); line-height: 1.5; }}
        form {{ display: grid; gap: 18px; margin-top: 22px; }}
        fieldset {{
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 16px;
        }}
        legend {{ padding: 0 8px; font-weight: 700; }}
        label {{ display: grid; gap: 7px; font-weight: 650; }}
        input, select {{
            width: 100%;
            border: 1px solid #b9b09d;
            border-radius: 6px;
            padding: 11px 12px;
            font: inherit;
            background: #fbfcfd;
            color: var(--ink);
        }}
        input:focus, select:focus {{
            outline: 3px solid rgba(36, 107, 91, 0.18);
            border-color: var(--accent);
        }}
        .radio-row {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .radio-pill {{
            display: flex;
            align-items: center;
            gap: 8px;
            border: 1px solid var(--line);
            border-radius: 7px;
            padding: 8px 13px;
            background: #fbfcfd;
            cursor: pointer;
        }}
        .radio-pill input {{ width: auto; }}
        .players-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
        }}
        .errors {{
            color: var(--danger);
            background: #fff0ed;
            border: 1px solid #f4b4aa;
            border-radius: 8px;
            padding: 10px 14px;
        }}
        .errors ul {{ margin: 0; padding-left: 18px; }}
        button {{
            border: 0;
            border-radius: 7px;
            padding: 13px 18px;
            font: inherit;
            font-weight: 800;
            color: white;
            background: var(--accent);
            cursor: pointer;
        }}
        button:hover {{ background: var(--accent-dark); }}
        .model-list {{
            margin: 0;
            padding-left: 18px;
            color: var(--muted);
            display: grid;
            gap: 9px;
            font-size: 13px;
            line-height: 1.4;
        }}
        .hint {{ margin: 6px 0 0; font-size: 13px; }}
        @media (max-width: 820px) {{
            main {{ grid-template-columns: 1fr; }}
            .players-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <main>
        <section>
            <h1>PyCatan AI Setup</h1>
            <p>Choose the Gemini model, enter your API key, then set the AI players for this run.</p>
            {errors_html}
            <form method="post" action="/start">
                <fieldset>
                    <legend>Gemini</legend>
                    <label>
                        Model
                        <select name="model" required>
                            {''.join(model_options)}
                        </select>
                    </label>
                    <label style="margin-top: 12px;">
                        API key
                        <input name="api_key" type="password" autocomplete="off" required>
                    </label>
                    <p class="hint">The key is only placed in this game process environment as GEMINI_API_KEY.</p>
                </fieldset>

                <fieldset>
                    <legend>Table talk</legend>
                    <label>
                        Chat language
                        <select name="chat_language" required>
                            <option value="english" {'selected' if selected_chat_language == 'english' else ''}>English</option>
                            <option value="hebrew" {'selected' if selected_chat_language == 'hebrew' else ''}>Hebrew</option>
                        </select>
                    </label>
                    <p class="hint">Controls only public say_outloud chat. Private reasoning stays in English.</p>
                </fieldset>

                <fieldset>
                    <legend>Voice</legend>
                    <label>
                        Provider
                        <select name="tts_provider" required>
                            <option value="gemini" {'selected' if selected_tts_provider == 'gemini' else ''}>Gemini TTS</option>
                            <option value="elevenlabs" {'selected' if selected_tts_provider == 'elevenlabs' else ''}>ElevenLabs</option>
                            <option value="off" {'selected' if selected_tts_provider == 'off' else ''}>Off</option>
                        </select>
                    </label>
                    <div id="gemini-tts-fields">
                        <label style="margin-top: 12px;">
                            Gemini speech model
                            <select name="gemini_tts_model">
                                {''.join(gemini_tts_model_options)}
                            </select>
                        </label>
                        <label style="margin-top: 12px;">
                            Gemini voice
                            <select name="gemini_tts_voice">
                                {''.join(gemini_tts_voice_options)}
                            </select>
                        </label>
                        <p class="hint">Uses the Gemini API key above. Hebrew is auto-detected by the TTS model.</p>
                    </div>
                    <div id="elevenlabs-tts-fields">
                    <label>
                        Speech model
                        <select name="elevenlabs_tts_model" required>
                            {''.join(tts_model_options)}
                        </select>
                    </label>
                    <label style="margin-top: 12px;">
                        API key
                        <input name="elevenlabs_api_key" type="password" autocomplete="off" required>
                    </label>
                    <label style="margin-top: 12px;">
                        Default voice ID
                        <input name="elevenlabs_default_voice_id" autocomplete="off" required>
                    </label>
                    <p class="hint">Used only for this run as ELEVENLABS_API_KEY and ELEVENLABS_DEFAULT_VOICE_ID.</p>
                    </div>
                </fieldset>

                <fieldset>
                    <legend>Players</legend>
                    <div class="radio-row">
                        <label class="radio-pill"><input type="radio" name="player_count" value="2" {'checked' if player_count == 2 else ''}> 2 players</label>
                        <label class="radio-pill"><input type="radio" name="player_count" value="3" {'checked' if player_count == 3 else ''}> 3 players</label>
                        <label class="radio-pill"><input type="radio" name="player_count" value="4" {'checked' if player_count == 4 else ''}> 4 players</label>
                    </div>
                    <div class="players-grid" style="margin-top: 14px;">
                        {''.join(player_inputs)}
                    </div>
                </fieldset>
                <button type="submit">Start game</button>
            </form>
        </section>
        <aside>
            <h2>Text models in this setup</h2>
            <ul class="model-list">{model_notes}</ul>
            <h2 style="margin-top: 22px;">Speech models</h2>
            <ul class="model-list">{tts_model_notes}</ul>
        </aside>
    </main>
    <script>
        const radios = document.querySelectorAll('input[name="player_count"]');
        const playerFields = document.querySelectorAll('.player-field');
        const providerSelect = document.querySelector('select[name="tts_provider"]');
        const geminiTtsFields = document.getElementById('gemini-tts-fields');
        const elevenLabsFields = document.getElementById('elevenlabs-tts-fields');
        function refreshPlayers() {{
            const count = Number(document.querySelector('input[name="player_count"]:checked').value);
            playerFields.forEach((field) => {{
                const visible = Number(field.dataset.playerIndex) <= count;
                field.style.display = visible ? 'grid' : 'none';
                field.querySelector('input').required = visible;
            }});
        }}
        function refreshTtsProvider() {{
            const provider = providerSelect.value;
            geminiTtsFields.style.display = provider === 'gemini' ? 'block' : 'none';
            elevenLabsFields.style.display = provider === 'elevenlabs' ? 'block' : 'none';
            geminiTtsFields.querySelectorAll('select, input').forEach((field) => {{
                field.required = provider === 'gemini';
            }});
            elevenLabsFields.querySelectorAll('select, input').forEach((field) => {{
                field.required = provider === 'elevenlabs';
            }});
        }}
        radios.forEach((radio) => radio.addEventListener('change', refreshPlayers));
        providerSelect.addEventListener('change', refreshTtsProvider);
        refreshPlayers();
        refreshTtsProvider();
    </script>
</body>
</html>"""


def _render_game_starting_page(model: str, player_names: List[str]) -> bytes:
    """Render the post-submit page while the real game server starts."""
    safe_model = html_lib.escape(model)
    safe_players = html_lib.escape(", ".join(player_names))
    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Starting PyCatan</title>
    <style>
        body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            font-family: "Segoe UI", Arial, sans-serif;
            background: #edf1f5;
            color: #1f2933;
        }}
        main {{
            width: min(620px, calc(100% - 32px));
            padding: 30px;
            border: 1px solid #cbd5df;
            border-radius: 8px;
            background: #ffffff;
            box-shadow: 0 18px 45px rgba(31, 41, 51, 0.12);
        }}
        h1 {{ margin: 0 0 12px; }}
        p {{ line-height: 1.5; color: #68717d; }}
    </style>
</head>
<body>
    <main>
        <h1>Starting game...</h1>
        <p><strong>Model:</strong> {safe_model}</p>
        <p><strong>Players:</strong> {safe_players}</p>
        <p>The board will open here as soon as the game server is ready.</p>
    </main>
    <script>
        async function waitForGame() {{
            try {{
                const response = await fetch('/api/game-state', {{ cache: 'no-store' }});
                if (response.ok) {{
                    window.location.href = '/unified';
                    return;
                }}
            }} catch (error) {{}}
            setTimeout(waitForGame, 1000);
        }}
        setTimeout(waitForGame, 1000);
    </script>
</body>
</html>""".encode("utf-8")


def collect_browser_settings(port: int = 5000) -> Dict[str, Any]:
    """Open a temporary localhost setup page and wait for the selected run settings."""
    settings: Dict[str, Any] = {}
    settings_ready = threading.Event()
    valid_models = {model["id"] for model in GEMINI_TEXT_MODELS}
    valid_chat_languages = {"english", "hebrew"}
    valid_tts_models = {model["id"] for model in ELEVENLABS_TTS_MODELS}
    valid_tts_providers = {"off", "gemini", "elevenlabs"}
    valid_gemini_tts_models = {
        "gemini-2.5-flash-preview-tts",
        "gemini-2.5-pro-preview-tts",
        "gemini-3.1-flash-tts-preview",
        "gemini-3.1-pro-tts-preview",
    }

    class ReusableThreadingHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True

    class SettingsHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def _send_html(self, body: Any, status: int = 200) -> None:
            body_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)

        def do_GET(self):
            if self.path not in ("/", "/settings"):
                self.send_response(302)
                self.send_header("Location", "/settings")
                self.end_headers()
                return
            self._send_html(_render_browser_settings_page())

        def do_POST(self):
            if self.path != "/start":
                self.send_error(404)
                return

            length = int(self.headers.get("Content-Length", "0"))
            fields = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            selected_model = fields.get("model", [""])[0].strip()
            chat_language = normalize_chat_language(fields.get("chat_language", ["english"])[0])
            api_key = fields.get("api_key", [""])[0].strip()
            tts_provider = fields.get("tts_provider", ["gemini"])[0].strip()
            gemini_tts_model = fields.get("gemini_tts_model", ["gemini-2.5-flash-preview-tts"])[0].strip()
            gemini_tts_voice = fields.get("gemini_tts_voice", ["Kore"])[0].strip()
            elevenlabs_tts_model = fields.get("elevenlabs_tts_model", ["eleven_v3"])[0].strip()
            elevenlabs_api_key = fields.get("elevenlabs_api_key", [""])[0].strip()
            elevenlabs_default_voice_id = fields.get("elevenlabs_default_voice_id", [""])[0].strip()
            player_count_raw = fields.get("player_count", ["3"])[0].strip()
            names = [
                fields.get(f"player_{index + 1}", [DEFAULT_PLAYER_NAMES[index]])[0].strip()
                for index in range(4)
            ]

            errors = []
            if selected_model not in valid_models:
                errors.append("Choose one of the available Gemini text models.")
            if chat_language not in valid_chat_languages:
                errors.append("Choose English or Hebrew for table talk.")
            if not api_key:
                errors.append("Enter a Gemini API key.")
            if tts_provider not in valid_tts_providers:
                errors.append("Choose a valid voice provider.")
            if tts_provider == "gemini":
                if gemini_tts_model not in valid_gemini_tts_models:
                    errors.append("Choose one of the available Gemini speech models.")
                if not gemini_tts_voice:
                    errors.append("Choose a Gemini voice.")
            if tts_provider == "elevenlabs":
                if elevenlabs_tts_model not in valid_tts_models:
                    errors.append("Choose one of the available ElevenLabs speech models.")
                if not elevenlabs_api_key:
                    errors.append("Enter an ElevenLabs API key.")
                if not elevenlabs_default_voice_id:
                    errors.append("Enter an ElevenLabs default voice ID.")
            try:
                player_count = int(player_count_raw)
            except ValueError:
                player_count = 3
                errors.append("Choose 2, 3, or 4 players.")
            if player_count not in (2, 3, 4):
                errors.append("Choose 2, 3, or 4 players.")

            selected_names = names[:player_count]
            for index, name in enumerate(selected_names):
                if not name:
                    errors.append(f"Player {index + 1} needs a name.")

            lowered_names = [name.lower() for name in selected_names if name]
            if len(lowered_names) != len(set(lowered_names)):
                errors.append("Player names must be unique.")

            if errors:
                self._send_html(
                    _render_browser_settings_page(
                        errors=errors,
                        selected_model=selected_model if selected_model in valid_models else "gemini-3-flash-preview",
                        selected_chat_language=chat_language if chat_language in valid_chat_languages else "english",
                        selected_tts_provider=tts_provider if tts_provider in valid_tts_providers else "gemini",
                        selected_tts_model=elevenlabs_tts_model if elevenlabs_tts_model in valid_tts_models else "eleven_v3",
                        selected_gemini_tts_model=gemini_tts_model if gemini_tts_model in valid_gemini_tts_models else "gemini-2.5-flash-preview-tts",
                        selected_gemini_tts_voice=gemini_tts_voice or "Kore",
                        player_count=player_count if player_count in (2, 3, 4) else 3,
                        player_names=names
                    ),
                    status=400
                )
                return

            settings.update({
                "model": selected_model,
                "chat_language": chat_language,
                "api_key": api_key,
                "tts_provider": tts_provider,
                "gemini_tts_model": gemini_tts_model,
                "gemini_tts_voice": gemini_tts_voice,
                "elevenlabs_api_key": elevenlabs_api_key,
                "elevenlabs_default_voice_id": elevenlabs_default_voice_id,
                "elevenlabs_tts_model": elevenlabs_tts_model,
                "player_configs": [
                    {"name": selected_names[index], "is_ai": True, "color": PLAYER_COLORS[index]}
                    for index in range(player_count)
                ],
            })
            self._send_html(_render_game_starting_page(selected_model, selected_names))
            settings_ready.set()

    server = ReusableThreadingHTTPServer(("127.0.0.1", port), SettingsHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    setup_url = f"http://localhost:{port}/settings"
    print(f"[SETUP] Browser settings page: {setup_url}")
    try:
        webbrowser.open(setup_url)
    except Exception as exc:
        print(f"[SETUP] Could not open browser automatically: {exc}")
        print(f"[SETUP] Open this URL manually: {setup_url}")

    print("[SETUP] Waiting for browser settings...")
    try:
        while not settings_ready.wait(timeout=0.25):
            pass
    except KeyboardInterrupt:
        server.shutdown()
        server.server_close()
        raise

    server.shutdown()
    server.server_close()
    server_thread.join(timeout=2)
    return settings


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
    replay_decisions: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    replay_chat: bool = True,
    replay_speak: bool = False,
    replay_only: bool = False
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
                    replay_decisions=replay_decisions[cfg["name"]],
                    replay_chat=replay_chat,
                    replay_speak=replay_speak,
                    replay_only=replay_only
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


def _remaining_replay_decisions(game_manager: GameManager) -> int:
    """Count unplayed replay decisions across replay users."""
    total = 0
    for user in game_manager.users:
        total += len(getattr(user, "replay_decisions", []) or [])
    return total


def run_replay_viewer(
    game_manager: GameManager,
    ai_manager: AIManager,
    web_viz: WebVisualization,
    delay_seconds: float = 2.5,
    source_session: Optional[Path] = None
) -> None:
    """
    Build a recorded-session timeline and serve it to the browser.

    The browser controls playback by seeking captured snapshots, so users can
    move backward and forward without re-running game logic.
    """
    print("=" * 70)
    print("[REPLAY] WATCH MODE")
    print("[REPLAY] Building seekable timeline...")
    print("=" * 70)
    print()

    try:
        speech_prepare_callback = (
            getattr(ai_manager.tts, "prepare_blocking", None)
            or getattr(ai_manager.tts, "speak_blocking", None)
            or getattr(ai_manager.tts, "speak", None)
        )
        speech_play_callback = getattr(ai_manager.tts, "speak", None)
        web_viz.enable_replay_mode(
            source_session=str(source_session or ai_manager.get_session_path()),
            delay_seconds=delay_seconds,
            speech_prepare_callback=speech_prepare_callback,
            speech_play_callback=speech_play_callback,
        )

        game_manager.start_game()
        web_viz.capture_replay_snapshot("Start")
        consumed_items = set()

        while game_manager.is_running and not game_manager._check_game_end_conditions():
            remaining_before = _remaining_replay_decisions(game_manager)
            if remaining_before <= 0:
                print("[REPLAY] All recorded decisions were played.")
                break

            try:
                turn_ended = game_manager._handle_single_turn()
            except ReplayExhausted as exc:
                print(f"[REPLAY] Stopping: {exc}")
                break

            remaining_after = _remaining_replay_decisions(game_manager)
            if remaining_after == remaining_before:
                print("[REPLAY] Stopping because no recorded decision was consumed.")
                break

            if turn_ended:
                game_manager._advance_to_next_player()

            consumed = None
            for user in game_manager.users:
                replay_item = getattr(user, "last_replay_item", None)
                if replay_item is not None and id(replay_item) not in consumed_items:
                    consumed = replay_item
                    consumed_items.add(id(replay_item))
                    break

            label = "Recorded decision"
            if consumed:
                parsed = consumed.get("parsed") or {}
                label = (
                    f"{consumed.get('player_name')} #{consumed.get('request_number')}: "
                    f"{parsed.get('action_type')}"
                )
            web_viz.capture_replay_snapshot(label, consumed)

        print("\n" + "=" * 70)
        print(f"[REPLAY] Timeline ready: {len(web_viz.replay_timeline)} snapshots")
        print("[WEB] Board: http://localhost:5000/unified")
        print(f"[REPLAY] Browser playback delay: {delay_seconds:.1f}s")
        print("=" * 70)

        web_viz.seek_replay(0, speak=False)
        web_viz.start_server()
        try:
            webbrowser.open("http://localhost:5000/unified")
        except Exception:
            pass

        print("[REPLAY] Use the browser controls to play, pause, seek, step backward, or step forward.")
        print("[REPLAY] Press Ctrl+C here when you are done watching.")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n[!] Replay interrupted by user")
    except Exception as e:
        print(f"\n\n[ERROR] Replay error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n[SAVE] Saving replay viewer session...")
        ai_manager.save_session()
        if hasattr(ai_manager.tts, "close"):
            ai_manager.tts.close()
        print(f"[LOG] Replay viewer session saved to: {ai_manager.get_session_path()}")


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
    parser.add_argument("--browser-settings", action="store_true",
                       help="Open a browser setup screen for Gemini model/API key and player names before starting.")
    parser.add_argument("--chat-language", choices=["english", "hebrew"], default=None,
                       help="Language for public say_outloud table talk.")
    parser.add_argument("--hebrew-chat", action="store_true",
                       help="Shortcut for --chat-language hebrew.")
    parser.add_argument("--english-chat", action="store_true",
                       help="Shortcut for --chat-language english.")
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
    parser.add_argument("--replay-skip-chat", action="store_true",
                       help="Do not rebroadcast recorded say_outloud chat while fast-replaying.")
    parser.add_argument("--watch-replay", action="store_true",
                       help="Play a recorded session visually and stop when the recording ends. No LLM calls are made.")
    parser.add_argument("--replay-delay", type=float, default=2.5,
                       help="Seconds to wait between recorded decisions in --watch-replay mode.")
    parser.add_argument("--replay-speak", action="store_true",
                       help="Speak recorded say_outloud chat during replay using the configured cached TTS provider.")
    args = parser.parse_args()

    load_env_file()
    ai_config = load_ai_config(args.config)
    if args.hebrew_chat:
        args.chat_language = "hebrew"
    if args.english_chat:
        args.chat_language = "english"
    ai_config.agent.chat_language = normalize_chat_language(
        args.chat_language
        or os.environ.get("PYCATAN_CHAT_LANGUAGE")
        or ai_config.agent.chat_language
    )
    browser_player_configs: Optional[List[dict]] = None

    if args.browser_settings:
        browser_settings = collect_browser_settings(port=5000)
        ai_config.agent.chat_language = browser_settings["chat_language"]
        os.environ["GEMINI_API_KEY"] = browser_settings["api_key"]
        os.environ["TTS_PROVIDER"] = browser_settings["tts_provider"]
        if browser_settings["tts_provider"] == "gemini":
            os.environ["GEMINI_TTS_ENABLED"] = "true"
            os.environ["GEMINI_TTS_MODEL_ID"] = browser_settings["gemini_tts_model"]
            os.environ["GEMINI_TTS_VOICE_NAME"] = browser_settings["gemini_tts_voice"]
            os.environ.setdefault("GEMINI_TTS_PLAY_AUDIO", "true")
        elif browser_settings["tts_provider"] == "elevenlabs":
            os.environ["ELEVENLABS_TTS_ENABLED"] = "true"
            os.environ["ELEVENLABS_API_KEY"] = browser_settings["elevenlabs_api_key"]
            os.environ["ELEVENLABS_DEFAULT_VOICE_ID"] = browser_settings["elevenlabs_default_voice_id"]
            os.environ["ELEVENLABS_TTS_MODEL_ID"] = browser_settings["elevenlabs_tts_model"]
            os.environ.setdefault("ELEVENLABS_TTS_OUTPUT_FORMAT", "pcm_16000")
            os.environ.setdefault("ELEVENLABS_TTS_PLAY_AUDIO", "true")
        ai_config.llm.provider = "gemini"
        ai_config.llm.api_key_env_var = "GEMINI_API_KEY"
        ai_config.llm.model_name = browser_settings["model"]
        browser_player_configs = browser_settings["player_configs"]
        args.all_ai = True
        print("[SETUP] Browser settings accepted")

    replay_session_ref = args.replay_session or args.resume_session
    if args.watch_replay and not replay_session_ref:
        parser.error("--watch-replay requires --replay-session or --resume-session")

    replay_session_path = resolve_session_path(replay_session_ref) if replay_session_ref else None
    if (
        args.watch_replay
        and replay_session_path
        and not os.environ.get("AI_TTS_CACHE_DIR")
        and not os.environ.get("PYCATAN_TTS_CACHE_DIR")
    ):
        os.environ["AI_TTS_CACHE_DIR"] = str(replay_session_path / "tts_cache")
        print(f"[REPLAY] TTS cache: {os.environ['AI_TTS_CACHE_DIR']}")
    elif not args.watch_replay and not os.environ.get("AI_TTS_CACHE_DIR") and not os.environ.get("PYCATAN_TTS_CACHE_DIR"):
        print("[TTS] Voice cache: per-session tts_cache/")

    replay_decision_list: List[Dict[str, Any]] = []
    replay_decisions_by_player: Dict[str, List[Dict[str, Any]]] = {}
    replay_player_names: List[str] = []
    if replay_session_path:
        replay_decision_list = load_replay_decision_chain(
            replay_session_path,
            max_decisions=args.replay_max_decisions,
            replay_through=args.replay_through,
            replay_stop_before=args.replay_stop_before
        )
        replay_decisions_by_player = group_replay_decisions(replay_decision_list)
        replay_player_names = infer_players_from_session(replay_session_path)
        print(f"[REPLAY] Source: {replay_session_path}")
        print(f"[REPLAY] Loaded {len(replay_decision_list)} parsed decisions")
        if (replay_session_path / "session_metadata.json").exists():
            print("[REPLAY] Derived-session lineage is included when present")
    
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
    
    if browser_player_configs:
        player_configs = browser_player_configs
        num_players = len(player_configs)
        print_banner()
        print(
            f"Browser setup: {num_players} AI players - "
            f"{', '.join(player['name'] for player in player_configs)}"
        )
    elif num_players and args.all_ai:
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

    if args.watch_replay:
        send_to_llm = False
        manual_actions = False
        print("[REPLAY] Watch mode enabled: using recorded decisions only")

    print(f"[MODE] LLM: {'ON' if send_to_llm else 'OFF'} | Actions: {'Manual' if manual_actions else 'Auto'}")
    print(f"[CONFIG] {ai_config.llm.provider}/{ai_config.llm.model_name}")
    
    # Create game
    game_manager, ai_manager, web_viz = create_game(
        player_configs,
        send_to_llm=send_to_llm,
        manual_actions=manual_actions,
        config=ai_config,
        replay_decisions=replay_decisions_by_player,
        replay_chat=not args.replay_skip_chat,
        replay_speak=(args.replay_speak and not args.watch_replay),
        replay_only=args.watch_replay
    )
    if replay_session_path:
        annotate_replay_session(
            ai_manager,
            replay_session_path,
            replay_decision_list,
            args.replay_through,
            args.replay_stop_before,
            mode="watch_replay_visual_playback" if args.watch_replay else "fast_action_replay_then_live_ai"
        )
        print(f"[REPLAY] New derived session: {ai_manager.get_session_path()}")
    
    # Run game
    if args.watch_replay:
        run_replay_viewer(
            game_manager,
            ai_manager,
            web_viz,
            delay_seconds=max(0.0, args.replay_delay),
            source_session=replay_session_path
        )
    else:
        run_game(game_manager, ai_manager, web_viz)


if __name__ == "__main__":
    main()
