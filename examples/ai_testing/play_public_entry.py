#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Public single-page entrypoint for PyCatan AI.

This entrypoint is meant for first-time/public users:
- choose between a new AI game and an analysed replay
- optionally hide API-key entry when keys are supplied through ENV/.env
- expose only replay sessions marked as public in a small manifest
- provide a lightweight client-side admin unlock for curating that manifest
"""

import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.ai_testing.play_with_ai import (
    DEFAULT_PLAYER_NAMES,
    LOGS_DIR,
    PLAYER_COLORS,
    annotate_replay_session,
    create_game,
    group_replay_decisions,
    infer_players_from_decisions,
    list_replay_marker_options,
    load_ai_config,
    load_env_file,
    load_replay_decision_chain,
    resolve_session_path,
    run_game,
    run_replay_viewer,
)
from examples.ai_testing.play_with_openrouter import (
    GEMINI_TTS_MODELS,
    GEMINI_TTS_VOICES,
    MIN_COMPLETION_TOKENS,
    MIN_CONTEXT_LENGTH,
    PLAYER_GENDERS,
    RELATIONSHIP_CONTEXT_MODES,
    _apply_reaction_settings,
    _infer_session_player_names,
    _minimum_recorded_actions_for_state,
    _load_session_final_state,
    _parse_float,
    _parse_optional_int,
    _player_configs_for_replay,
    fetch_openrouter_models,
    infer_session_run_settings,
    provider_from_model_id,
    render_starting_page,
    write_run_settings_metadata,
)
from pycatan.ai.config import normalize_chat_language


PUBLIC_SESSIONS_MANIFEST = Path("examples") / "ai_testing" / "public_sessions.json"
ADMIN_PASSWORD = "20209"


def _json_response(handler: BaseHTTPRequestHandler, payload: Dict[str, Any], status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, body: Any, status: int = 200) -> None:
    body_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body_bytes)))
    handler.end_headers()
    handler.wfile.write(body_bytes)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _session_sort_key(path: Path) -> str:
    return path.name.replace("session_", "")


def _load_manifest() -> Dict[str, Any]:
    manifest = _read_json(PUBLIC_SESSIONS_MANIFEST)
    sessions = manifest.get("sessions")
    if not isinstance(sessions, dict):
        sessions = {}
    return {"sessions": sessions}


def _session_dirs(limit: int = 200) -> List[Path]:
    if not LOGS_DIR.exists():
        return []
    dirs = [path for path in LOGS_DIR.iterdir() if path.is_dir() and path.name.startswith("session_")]
    dirs.sort(key=_session_sort_key, reverse=True)
    return dirs[:limit]


def _response_count(session_dir: Path) -> int:
    return len(list(session_dir.glob("*/responses/response_*.json")))


def _prompt_count(session_dir: Path) -> int:
    return len(list(session_dir.glob("*/prompts/prompt_*.json")))


def _session_players_and_models(session_dir: Path) -> tuple[List[str], List[str]]:
    settings = infer_session_run_settings(session_dir)
    players = settings.get("players") if isinstance(settings, dict) else []
    names: List[str] = []
    models: List[str] = []
    if isinstance(players, list):
        for player in players:
            if not isinstance(player, dict):
                continue
            name = str(player.get("name") or "").strip()
            model = str((player.get("llm") or {}).get("model_name") or "").strip()
            if name:
                names.append(name)
            if model and model not in models:
                models.append(model)
    if not names:
        names = _infer_session_player_names(session_dir)
    return names[:4], models[:4]


def _generated_description(session_dir: Path, summary: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    players, models = _session_players_and_models(session_dir)
    run_settings = metadata.get("run_settings") if isinstance(metadata.get("run_settings"), dict) else {}
    vp = run_settings.get("victory_points") or (summary.get("final_game_state") or {}).get("meta", {}).get("vp_to_win")
    response_count = _response_count(session_dir)
    player_label = ", ".join(players) if players else "unknown players"
    model_label = ", ".join(models) if models else "recorded AI models"
    if metadata.get("replay"):
        source = (metadata.get("replay") or {}).get("source_session") or metadata.get("derived_from") or "another session"
        return f"Analysed replay derived from {source}. Players: {player_label}. {response_count} recorded AI responses."
    details = [f"{len(players) or '?'}-player AI Catan match", f"players: {player_label}"]
    if vp:
        details.append(f"target: {vp} VP")
    if response_count:
        details.append(f"{response_count} responses")
    if model_label:
        details.append(f"models: {model_label}")
    return ". ".join(details) + "."


def _session_summary(session_dir: Path, manifest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    manifest = manifest or _load_manifest()
    manifest_entry = (manifest.get("sessions") or {}).get(session_dir.name) or {}
    metadata = _read_json(session_dir / "session_metadata.json")
    summary = _read_json(session_dir / "session_summary.json")
    players, models = _session_players_and_models(session_dir)
    response_count = _response_count(session_dir)
    prompt_count = _prompt_count(session_dir)
    replay = metadata.get("replay") if isinstance(metadata.get("replay"), dict) else {}
    mode = replay.get("mode") or metadata.get("mode") or (metadata.get("run_settings") or {}).get("run_mode") or "recorded"
    generated = _generated_description(session_dir, summary, metadata)
    available = bool(manifest_entry.get("available", False))
    return {
        "name": session_dir.name,
        "path": str(session_dir),
        "available": available,
        "start_time": metadata.get("start_time", ""),
        "mode": mode,
        "derived_from": metadata.get("derived_from", ""),
        "source_session": replay.get("source_session", ""),
        "players": players,
        "models": models,
        "description": str(manifest_entry.get("description") or generated),
        "generated_description": generated,
        "response_count": response_count,
        "prompt_count": prompt_count,
        "has_summary": bool(summary),
        "has_tts": (session_dir / "tts_cache").exists(),
    }


def list_all_sessions(limit: int = 200) -> List[Dict[str, Any]]:
    manifest = _load_manifest()
    return [_session_summary(path, manifest) for path in _session_dirs(limit)]


def list_public_sessions(limit: int = 160) -> List[Dict[str, Any]]:
    sessions = list_all_sessions(limit)
    explicit_available = [session for session in sessions if session["available"]]
    if explicit_available:
        return explicit_available
    if (_load_manifest().get("sessions") or {}):
        return []
    # Fresh clones should not look empty before the owner curates the list.
    return [session for session in sessions if session["response_count"] > 0 or session["has_summary"]][:24]


def _session_preview(session_ref: str) -> Dict[str, Any]:
    session_dir = resolve_session_path(session_ref)
    summary = _session_summary(session_dir)
    markers = list_replay_marker_options(session_dir)
    final_state = _load_session_final_state(session_dir)
    minimum_actions = _minimum_recorded_actions_for_state(final_state)
    return {
        **summary,
        "markers": markers,
        "settings": infer_session_run_settings(session_dir),
        "minimum_actions_for_resume": minimum_actions,
        "can_replay": summary["response_count"] > 0,
    }


def _save_admin_manifest(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _admin_password_ok(payload.get("password")):
        raise PermissionError("Wrong admin password.")
    requested = payload.get("sessions") if isinstance(payload.get("sessions"), dict) else {}
    valid_names = {path.name for path in _session_dirs(500)}
    saved: Dict[str, Dict[str, Any]] = {}
    for name, config in requested.items():
        if name not in valid_names or not isinstance(config, dict):
            continue
        description = str(config.get("description") or "").strip()
        saved[name] = {
            "available": bool(config.get("available")),
            "description": description[:600],
        }
    manifest = {"sessions": saved}
    _write_json(PUBLIC_SESSIONS_MANIFEST, manifest)
    return manifest


def _admin_password_ok(password: Any) -> bool:
    return str(password or "") == ADMIN_PASSWORD


def _legacy_render_public_spa(models: List[Dict[str, Any]], key_mode: str) -> bytes:
    bootstrap = {
        "models": models,
        "sessions": list_public_sessions(),
        "allSessions": list_all_sessions(),
        "keyMode": key_mode,
        "env": {
            "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
            "gemini": bool(os.environ.get("GEMINI_API_KEY")),
        },
        "defaults": {
            "players": DEFAULT_PLAYER_NAMES,
            "colors": PLAYER_COLORS,
            "genders": PLAYER_GENDERS,
            "geminiTtsModels": GEMINI_TTS_MODELS,
            "geminiTtsVoices": GEMINI_TTS_VOICES,
            "relationshipModes": RELATIONSHIP_CONTEXT_MODES,
        },
    }
    safe_payload = json.dumps(bootstrap, ensure_ascii=False).replace("</", "<\\/")
    html = """<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>קטאן AI על השולחן</title>
<style>
:root {
  color-scheme: light;
  --ink: #20231f;
  --muted: #6a6f66;
  --line: #d9d3c3;
  --paper: #fffaf0;
  --surface: #ffffff;
  --wash: #f3efe3;
  --wood: #9a642d;
  --wood-dark: #53351d;
  --brick: #b85a42;
  --forest: #2d7050;
  --field: #d8a93d;
  --sea: #2e7282;
  --danger: #b42318;
  --shadow: 0 18px 46px rgba(44, 39, 30, .14);
  --soft-shadow: 0 10px 28px rgba(44, 39, 30, .10);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
  background:
    radial-gradient(circle at 12% 10%, rgba(216,169,61,.18), transparent 30%),
    linear-gradient(135deg, rgba(46,114,130,.13), transparent 34%),
    linear-gradient(315deg, rgba(184,90,66,.14), transparent 42%),
    var(--wash);
  font-family: Inter, ui-sans-serif, "Segoe UI", Arial, sans-serif;
}
button, input, select, textarea { font: inherit; }
button { cursor: pointer; }
.app { min-height: 100vh; }
.hero {
  min-height: 430px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 430px);
  gap: clamp(22px, 4vw, 54px);
  align-items: center;
  padding: 34px clamp(18px, 5vw, 72px) 76px;
  color: #fff;
  background:
    linear-gradient(90deg, rgba(29,35,29,.96), rgba(37,46,39,.78) 52%, rgba(31,44,48,.70)),
    url("/static/images/Fields.png");
  background-size: cover, 240px 210px;
  background-position: center, left bottom;
  position: relative;
  overflow: hidden;
}
.hero::after {
  content: "";
  position: absolute;
  inset-inline-start: 0;
  bottom: 0;
  width: 100%;
  height: 74px;
  background:
    linear-gradient(0deg, rgba(32,35,31,.28), transparent),
    repeating-linear-gradient(90deg, rgba(255,255,255,.07) 0 1px, transparent 1px 64px);
  pointer-events: none;
}
.eyebrow {
  color: rgba(255,255,255,.72);
  font-weight: 850;
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0;
}
.hero h1 {
  margin: 0;
  font-size: clamp(42px, 7vw, 86px);
  line-height: .95;
  letter-spacing: 0;
}
.hero p {
  max-width: 760px;
  margin: 20px 0 0;
  color: rgba(255,255,255,.84);
  font-size: clamp(17px, 2vw, 22px);
  line-height: 1.5;
}
.hero-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 26px; }
.status {
  width: min(100%, 420px);
  justify-self: end;
  border: 1px solid rgba(255,255,255,.22);
  border-radius: 8px;
  padding: 18px;
  background: rgba(255,255,255,.12);
  box-shadow: 0 20px 60px rgba(0,0,0,.22);
  backdrop-filter: blur(12px);
}
.status strong { display: block; margin-bottom: 8px; font-size: 18px; }
.status span { display: block; color: rgba(255,255,255,.76); line-height: 1.45; }
.table-preview {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.terrain {
  min-height: 74px;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,.22);
  background-size: cover;
  background-position: center;
}
.terrain.field { background-image: url("/static/images/Fields.png"); }
.terrain.forest { background-image: url("/static/images/Forest.png"); }
.terrain.hills { background-image: url("/static/images/Hills.png"); }
.terrain.pasture { background-image: url("/static/images/Pasture.png"); }
.terrain.mountain { background-image: url("/static/images/Mountains.png"); }
.terrain.sea { background: linear-gradient(135deg, #276d7c, #62a7b5); }
.workspace {
  width: min(1240px, calc(100% - 28px));
  margin: -58px auto 36px;
  display: grid;
  gap: 16px;
  position: relative;
  z-index: 2;
}
.choicebar {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.choice {
  min-height: 118px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 20px;
  text-align: left;
  color: var(--ink);
  background: var(--surface);
  box-shadow: var(--shadow);
  display: grid;
  gap: 8px;
  direction: rtl;
}
.choice.active { border-color: var(--wood); box-shadow: inset 0 0 0 2px var(--wood), var(--shadow); background: #fffdf8; }
.choice strong { display: block; font-size: 24px; }
.choice span { color: var(--muted); line-height: 1.45; }
.view { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; align-items: start; }
.section {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  box-shadow: var(--soft-shadow);
}
.section h2, .section h3 { margin: 0 0 12px; letter-spacing: 0; }
.section h2 { font-size: 23px; }
.section h3 { font-size: 18px; }
.section-title { display: flex; justify-content: space-between; gap: 14px; align-items: start; margin-bottom: 14px; }
.section-title p { margin: 4px 0 0; color: var(--muted); line-height: 1.45; }
.stack { display: grid; gap: 14px; }
.grid-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
label { display: grid; gap: 7px; font-weight: 750; }
input, select, textarea {
  width: 100%;
  min-height: 42px;
  border: 1px solid #bac8bf;
  border-radius: 6px;
  padding: 9px 11px;
  background: #fff;
  color: var(--ink);
}
input[type="password"], input[type="number"], #config-path, select[id^="model-"] { direction: ltr; text-align: left; }
textarea { min-height: 92px; resize: vertical; }
.players { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.player {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 13px;
  background: var(--surface);
  display: grid;
  gap: 10px;
}
.player.hidden, .hidden { display: none !important; }
.player-head { display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 13px; }
.player-head strong { color: var(--ink); }
.actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.primary, .secondary, .quiet {
  min-height: 43px;
  border-radius: 7px;
  padding: 0 15px;
  font-weight: 850;
}
.primary { border: 1px solid var(--forest); background: var(--forest); color: #fff; }
.primary:hover { background: #245c42; }
.secondary { border: 1px solid var(--line); background: #fff; color: var(--wood-dark); }
.quiet { border: 0; background: transparent; color: var(--sea); padding: 0 4px; }
.side { position: sticky; top: 14px; }
.note { color: var(--muted); line-height: 1.55; font-size: 14px; }
.model-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; max-height: 372px; overflow: auto; }
.model-list li { border: 1px solid var(--line); border-radius: 7px; padding: 9px; background: #fff; }
.model-list strong { display: block; font-size: 12px; overflow-wrap: anywhere; direction: ltr; text-align: left; }
.steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.steps li { display: grid; grid-template-columns: 28px 1fr; gap: 10px; align-items: start; color: var(--muted); line-height: 1.45; }
.steps b { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: #efe2c4; color: var(--wood-dark); }
.session-tools { display: flex; gap: 8px; margin-bottom: 12px; }
.session-list { display: grid; gap: 9px; max-height: 610px; overflow: auto; padding-right: 4px; }
.session-row {
  width: 100%;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 13px;
  display: grid;
  gap: 8px;
  direction: rtl;
}
.session-row.active { border-color: var(--forest); box-shadow: inset 0 0 0 1px var(--forest); background: #fbfff8; }
.session-name { font-family: Consolas, "SFMono-Regular", monospace; font-weight: 850; font-size: 13px; direction: ltr; text-align: left; }
.session-desc { color: var(--muted); line-height: 1.45; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; color: var(--muted); font-size: 12px; background: #f7f8f4; }
.errors { display: none; border: 1px solid #efb3aa; background: #fff5f2; color: var(--danger); border-radius: 8px; padding: 12px 14px; }
.errors.visible { display: block; }
.errors ul { margin: 0; padding-left: 20px; }
details { border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fff; }
summary { cursor: pointer; font-weight: 850; }
.compact-admin { opacity: .72; }
.compact-admin[open] { opacity: 1; }
.admin-list { display: grid; gap: 10px; max-height: 540px; overflow: auto; }
.admin-row { border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fff; display: grid; gap: 9px; }
.check { display: flex; gap: 8px; align-items: center; font-weight: 800; }
.check input { width: auto; min-height: auto; }
@media (max-width: 980px) {
  .hero { grid-template-columns: 1fr; }
  .status { justify-self: stretch; }
  .view { grid-template-columns: 1fr; }
  .side { position: static; }
}
@media (max-width: 720px) {
  .choicebar, .grid-2, .grid-3, .players { grid-template-columns: 1fr; }
  .hero { min-height: 520px; padding-bottom: 86px; }
  .workspace { width: min(100% - 20px, 1240px); }
  .session-tools { display: grid; }
}
</style>
</head>
<body>
<div class="app">
  <header class="hero">
    <div>
      <div class="eyebrow">שולחן ציבורי</div>
      <h1>קטאן AI על השולחן</h1>
      <p>פותחים משחק חדש בין סוכני AI, או נכנסים לשידור חוזר שכבר נותח. פחות מסך הגדרות, יותר תחושה של משחק שמתחיל עכשיו.</p>
      <div class="hero-actions">
        <button class="primary" type="button" onclick="setView('new')">להתחיל משחק</button>
        <button class="secondary" type="button" onclick="setView('replay')">לצפות בשידור חוזר</button>
      </div>
    </div>
    <div class="status">
      <strong>מצב השולחן</strong>
      <span id="runtime-status"></span>
      <div class="table-preview" aria-hidden="true">
        <div class="terrain field"></div>
        <div class="terrain forest"></div>
        <div class="terrain hills"></div>
        <div class="terrain pasture"></div>
        <div class="terrain mountain"></div>
        <div class="terrain sea"></div>
      </div>
    </div>
  </header>

  <main class="workspace">
    <div class="choicebar">
      <button class="choice active" id="choose-new" type="button">
        <strong>משחק חדש</strong>
        <span>בחרו שחקנים, יעד ניצחון ושפה. המודלים והקולות זמינים למי שרוצה לכוון.</span>
      </button>
      <button class="choice" id="choose-replay" type="button">
        <strong>שידורים חוזרים</strong>
        <span>פתחו משחק מוקלט עם ניתוח החלטות, ציר זמן ודיבור שולחן אם קיים במטמון.</span>
      </button>
    </div>
    <div id="errors" class="errors"></div>

    <section id="new-view" class="view">
      <div class="stack">
        <div class="section" id="keys-section">
          <div class="section-title">
            <div>
              <h2>כניסה לשולחן</h2>
              <p>רק כדי להריץ משחק חי. בשידורים חוזרים לא צריך מפתח.</p>
            </div>
          </div>
          <div class="grid-2">
            <label>מפתח OpenRouter למהלכים
              <input id="openrouter-key" type="password" autocomplete="off" placeholder="sk-or-...">
            </label>
            <label>מפתח Gemini לקול
              <input id="gemini-key" type="password" autocomplete="off" placeholder="AIza...">
            </label>
          </div>
          <p class="note">המפתחות נשארים בתהליך המקומי ולא נשמרים במטא־דאטה של המשחק.</p>
        </div>

        <div class="section">
          <div class="section-title">
            <div>
              <h2>אופי המשחק</h2>
              <p>הדברים שהכי משפיעים על החוויה נמצאים כאן. כל השאר מקופל למטה.</p>
            </div>
          </div>
          <div class="grid-3">
            <label>מספר שחקנים
              <select id="player-count">
                <option value="2">2 שחקנים</option>
                <option value="3">3 שחקנים</option>
                <option value="4" selected>4 שחקנים</option>
              </select>
            </label>
            <label>יעד ניצחון
              <input id="victory-points" type="number" min="1" step="1" value="5">
            </label>
            <label>שפת הדיבור
              <select id="chat-language">
                <option value="english" selected>English</option>
                <option value="hebrew">עברית</option>
              </select>
            </label>
            <label>תגובות מסביב לשולחן
              <select id="reaction-mode">
                <option value="async" selected>חי ומהיר</option>
                <option value="sync">מסודר לפי תור</option>
                <option value="off">כבוי</option>
                <option value="default">לפי קובץ הגדרות</option>
              </select>
            </label>
            <label>זיכרון יחסים
              <select id="relationship-mode"></select>
            </label>
            <label>Seed אקראי
              <input id="random-seed" type="number" step="1" placeholder="0">
            </label>
          </div>
          <label style="margin-top:12px">סיפור קטן לשולחן
            <textarea id="game-context" maxlength="4000" placeholder="לדוגמה: השחקנים משחקים כמו פרשני טורניר בטוחים בעצמם."></textarea>
          </label>
          <details style="margin-top:12px">
            <summary>כיוונון מתקדם</summary>
            <div class="grid-3" style="margin-top:12px">
              <label>קובץ הגדרות
                <input id="config-path" placeholder="pycatan/ai/config_dev.yaml">
              </label>
              <label>כמות תגובות
                <input id="reaction-batch-size" type="number" min="1" step="1" placeholder="5">
              </label>
              <label>מודל קול Gemini
                <select id="gemini-tts-model"></select>
              </label>
              <label>קול Gemini
                <select id="gemini-tts-voice"></select>
              </label>
              <label>דיבור
                <select id="tts-provider">
                  <option value="gemini" selected>Gemini</option>
                  <option value="off">כבוי</option>
                </select>
              </label>
            </div>
            <label class="check" style="margin-top:12px"><input id="no-llm" type="checkbox"> מצב מקומי ללא קריאות LLM חדשות</label>
          </details>
        </div>

        <div class="section">
          <div class="section-title">
            <div>
              <h2>מי יושב סביב השולחן</h2>
              <p>אפשר להשאיר את ברירת המחדל, או לתת לכל שחקן שם ומוח משחק אחר.</p>
            </div>
          </div>
          <div class="players" id="players"></div>
        </div>

        <div class="actions">
          <button class="primary" type="button" id="start-game">פתח שולחן משחק</button>
          <button class="secondary" type="button" id="reset-defaults">איפוס</button>
        </div>
      </div>

      <aside class="section side">
        <h3>מה יקרה עכשיו</h3>
        <ol class="steps">
          <li><b>1</b><span>נפתח לוח קטאן חי בדפדפן.</span></li>
          <li><b>2</b><span>כל שחקן AI יקבל תור, ידבר, יבדוק אפשרויות ויבצע מהלך.</span></li>
          <li><b>3</b><span>אפשר לעקוב אחרי הלוח, הצ'אט והניתוח בזמן אמת.</span></li>
        </ol>
        <details style="margin-top:14px">
          <summary>רשימת מודלים זמינים</summary>
          <p class="note">מוצגים רק מודלים שמתאימים לכלי המשחק ולפלט מובנה.</p>
          <ol id="model-list" class="model-list"></ol>
        </details>
      </aside>
    </section>

    <section id="replay-view" class="view hidden">
      <div class="section">
        <div class="section-title">
          <div>
            <h2>ספריית שידורים חוזרים</h2>
            <p>בחרו משחק מוקלט ופתחו אותו כצפייה מודרכת עם החלטות השחקנים.</p>
          </div>
        </div>
        <div class="session-tools">
          <input id="session-search" placeholder="חיפוש לפי שחקן, תיאור או מודל">
          <button class="secondary" id="refresh-sessions" type="button">רענון</button>
        </div>
        <div id="session-list" class="session-list"></div>
      </div>
      <aside class="section side">
        <h3>השידור שנבחר</h3>
        <div id="session-preview" class="note">בחרו משחק מהרשימה.</div>
        <div class="grid-2" style="margin-top:12px">
          <label>קצב צפייה
            <input id="replay-delay" type="number" min="0" step="0.1" value="2.5">
          </label>
          <label>הקדמת טקסט
            <input id="replay-text-lead" type="number" min="0" step="0.05" value="0.25">
          </label>
        </div>
        <label class="check" style="margin-top:12px"><input id="replay-speak" type="checkbox"> להשמיע דיבור שמור אם קיים</label>
        <div class="actions" style="margin-top:14px">
          <button class="primary" type="button" id="start-replay">פתח צפייה מנותחת</button>
        </div>
      </aside>
    </section>

    <details class="section compact-admin" id="admin-panel">
      <summary>ניהול ספריית שידורים</summary>
      <div class="grid-2" style="margin-top:12px">
        <label>סיסמה
          <input id="admin-password" type="password" placeholder="סיסמת ניהול">
        </label>
        <div class="actions" style="align-self:end">
          <button class="secondary" type="button" id="admin-unlock">פתיחה</button>
          <button class="primary hidden" type="button" id="admin-save">שמירה</button>
        </div>
      </div>
      <p class="note">כאן בוחרים אילו משחקים יופיעו לאורחים בספרייה הציבורית.</p>
      <div id="admin-list" class="admin-list hidden"></div>
    </details>
  </main>
</div>

<script>
const state = __BOOTSTRAP_JSON__;
const byId = (id) => document.getElementById(id);
let currentView = "new";
let selectedSession = "";
let adminUnlocked = false;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));
}

function showErrors(errors) {
  const box = byId("errors");
  if (!errors || !errors.length) {
    box.classList.remove("visible");
    box.innerHTML = "";
    return;
  }
  box.innerHTML = "<ul>" + errors.map((error) => `<li>${escapeHtml(error)}</li>`).join("") + "</ul>";
  box.classList.add("visible");
  box.scrollIntoView({behavior: "smooth", block: "center"});
}

function setView(view) {
  currentView = view;
  byId("choose-new").classList.toggle("active", view === "new");
  byId("choose-replay").classList.toggle("active", view === "replay");
  byId("new-view").classList.toggle("hidden", view !== "new");
  byId("replay-view").classList.toggle("hidden", view !== "replay");
  showErrors([]);
}

function optionHtml(value, label, selected = false) {
  return `<option value="${escapeHtml(value)}" ${selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
}

function renderStatus() {
  const hidden = state.keyMode === "env_hidden";
  byId("keys-section").classList.toggle("hidden", hidden);
  const llm = state.env.openrouter ? "OpenRouter מחובר" : "OpenRouter לא מחובר";
  const tts = state.env.gemini ? "Gemini מחובר" : "Gemini לא מחובר";
  byId("runtime-status").textContent = hidden
    ? `${llm}. ${tts}. אפשר להתחיל בלי להזין מפתחות במסך.`
    : "למשחק חי מזינים מפתחות פעם אחת, ואז השולחן נפתח בדפדפן.";
}

function renderModels() {
  const models = state.models || [];
  byId("model-list").innerHTML = models.map((model) =>
    `<li><strong>${escapeHtml(model.id)}</strong><span class="note">${escapeHtml(model.name || "")}</span></li>`
  ).join("") || "<li>רשימת מודלים לא נטענה עדיין. בדקו חיבור OpenRouter.</li>";
}

function renderStaticSelects() {
  byId("relationship-mode").innerHTML = (state.defaults.relationshipModes || [])
    .map(([value, label], index) => optionHtml(value, label, index === 0)).join("");
  byId("gemini-tts-model").innerHTML = (state.defaults.geminiTtsModels || [])
    .map((value, index) => optionHtml(value, value, index === 0)).join("");
  byId("gemini-tts-voice").innerHTML = (state.defaults.geminiTtsVoices || [])
    .map((value) => optionHtml(value, value, value === "Kore")).join("");
}

function renderPlayers() {
  const models = state.models || [];
  const defaults = state.defaults.players || ["Alice", "Bob", "Charlie", "Diana"];
  const modelOptions = models.map((model, index) =>
    optionHtml(model.id, `${model.name || model.id} - ${model.id}`, index === 0)
  ).join("");
  byId("players").innerHTML = [1, 2, 3, 4].map((slot) => {
    const color = (state.defaults.colors || [])[slot - 1] || "";
    const gender = (state.defaults.genders || {})[slot] || "";
    return `<div class="player" data-player-card="${slot}">
      <div class="player-head"><strong>שחקן ${slot}</strong><span>${escapeHtml(color)} ${gender ? " / " + escapeHtml(gender) : ""}</span></div>
      <label>שם <input id="player-${slot}" value="${escapeHtml(defaults[slot - 1] || `Player ${slot}`)}"></label>
      <label>מוח משחק <select id="model-${slot}">${modelOptions}</select></label>
    </div>`;
  }).join("");
  updatePlayerCount();
}

function updatePlayerCount() {
  const count = Number(byId("player-count").value || 4);
  document.querySelectorAll("[data-player-card]").forEach((card) => {
    card.classList.toggle("hidden", Number(card.dataset.playerCard) > count);
  });
}

function sessionMatches(session, term) {
  if (!term) return true;
  const haystack = [
    session.name,
    session.description,
    (session.players || []).join(" "),
    (session.models || []).join(" "),
    session.mode
  ].join(" ").toLowerCase();
  return haystack.includes(term.toLowerCase());
}

function sessionLine(session) {
  const players = (session.players || []).join(", ") || "שחקנים לא זוהו";
  const models = (session.models || []).join(", ") || "אין פירוט מודלים";
  return `<span class="session-name">${escapeHtml(session.name)}</span>
    <span class="session-desc">${escapeHtml(session.description || session.generated_description || "")}</span>
    <span class="note">${escapeHtml(players)}</span>
    <span class="note">${escapeHtml(models)}</span>
    <span class="chips">
      <span class="chip">${escapeHtml(session.mode || "recorded")}</span>
      <span class="chip">${session.response_count || 0} החלטות</span>
      ${session.has_summary ? '<span class="chip">סיכום</span>' : ""}
      ${session.has_tts ? '<span class="chip">קול שמור</span>' : ""}
    </span>`;
}

function renderSessions() {
  const term = byId("session-search").value || "";
  const sessions = (state.sessions || []).filter((session) => sessionMatches(session, term));
  byId("session-list").innerHTML = sessions.map((session) =>
    `<button class="session-row ${selectedSession === session.name ? "active" : ""}" type="button" data-session="${escapeHtml(session.name)}">${sessionLine(session)}</button>`
  ).join("") || '<div class="note">אין עדיין שידורים חוזרים זמינים לצפייה.</div>';
  document.querySelectorAll("[data-session]").forEach((row) => {
    row.addEventListener("click", () => selectSession(row.dataset.session));
  });
}

async function refreshSessions() {
  const response = await fetch("/api/sessions", {cache: "no-store"});
  const payload = await response.json();
  state.sessions = payload.sessions || [];
  if (!state.sessions.some((session) => session.name === selectedSession)) selectedSession = "";
  renderSessions();
  renderSessionPreview(null);
}

async function selectSession(name) {
  selectedSession = name;
  renderSessions();
  renderSessionPreview({loading: true});
  try {
    const response = await fetch(`/api/session?session=${encodeURIComponent(name)}`, {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not load session.");
    renderSessionPreview(payload);
  } catch (error) {
    renderSessionPreview({error: error.message});
  }
}

function renderSessionPreview(preview) {
  if (!preview) {
    byId("session-preview").innerHTML = selectedSession ? "טוען..." : "בחרו משחק מהרשימה.";
    return;
  }
  if (preview.loading) {
    byId("session-preview").textContent = "טוען פרטי משחק...";
    return;
  }
  if (preview.error) {
    byId("session-preview").innerHTML = `<span style="color:var(--danger)">${escapeHtml(preview.error)}</span>`;
    return;
  }
  byId("session-preview").innerHTML = `<div class="session-name">${escapeHtml(preview.name)}</div>
    <p>${escapeHtml(preview.description || "")}</p>
    <div class="chips">
      <span class="chip">${(preview.players || []).length || "?"} שחקנים</span>
      <span class="chip">${preview.response_count || 0} החלטות</span>
      <span class="chip">${(preview.markers || []).length} נקודות ציון</span>
    </div>`;
}

function renderAdminList() {
  const sessions = state.allSessions || [];
  byId("admin-list").innerHTML = sessions.map((session) => `
    <div class="admin-row" data-admin-session="${escapeHtml(session.name)}">
      <label class="check"><input type="checkbox" class="admin-available" ${session.available ? "checked" : ""}> ${escapeHtml(session.name)}</label>
      <div class="note">${escapeHtml((session.players || []).join(", ") || "לא זוהו שחקנים")} / ${session.response_count || 0} החלטות</div>
      <label>תיאור
        <textarea class="admin-description" maxlength="600">${escapeHtml(session.description || session.generated_description || "")}</textarea>
      </label>
    </div>
  `).join("") || '<div class="note">לא נמצאו משחקים.</div>';
}

async function unlockAdmin() {
  if (byId("admin-password").value !== "20209") {
    showErrors(["סיסמת הניהול שגויה."]);
    return;
  }
  adminUnlocked = true;
  const response = await fetch("/api/admin/sessions", {cache: "no-store"});
  const payload = await response.json();
  state.allSessions = payload.sessions || state.allSessions || [];
  byId("admin-list").classList.remove("hidden");
  byId("admin-save").classList.remove("hidden");
  renderAdminList();
  showErrors([]);
}

async function saveAdmin() {
  if (!adminUnlocked) return;
  const sessions = {};
  document.querySelectorAll("[data-admin-session]").forEach((row) => {
    sessions[row.dataset.adminSession] = {
      available: row.querySelector(".admin-available").checked,
      description: row.querySelector(".admin-description").value
    };
  });
  const response = await fetch("/api/admin/sessions", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({password: byId("admin-password").value, sessions})
  });
  const payload = await response.json();
  if (!response.ok) {
    showErrors([payload.error || "לא הצלחתי לשמור את הגדרות הספרייה."]);
    return;
  }
  state.allSessions = payload.sessions || [];
  await refreshSessions();
  showErrors([]);
}

function collectNewGameFields() {
  const fields = new URLSearchParams();
  fields.set("run_mode", "new_game");
  fields.set("player_count", byId("player-count").value);
  fields.set("openrouter_api_key", byId("openrouter-key").value);
  fields.set("gemini_api_key", byId("gemini-key").value);
  fields.set("chat_language", byId("chat-language").value);
  fields.set("relationship_context_mode", byId("relationship-mode").value);
  fields.set("reaction_mode", byId("reaction-mode").value);
  fields.set("victory_points", byId("victory-points").value);
  fields.set("random_seed", byId("random-seed").value);
  fields.set("game_context", byId("game-context").value);
  fields.set("config_path", byId("config-path").value);
  fields.set("reaction_batch_size", byId("reaction-batch-size").value);
  fields.set("tts_provider", byId("tts-provider").value);
  fields.set("gemini_tts_model", byId("gemini-tts-model").value);
  fields.set("gemini_tts_voice", byId("gemini-tts-voice").value);
  if (byId("no-llm").checked) fields.set("no_llm", "on");
  for (let slot = 1; slot <= 4; slot += 1) {
    fields.set(`player_${slot}`, byId(`player-${slot}`).value);
    fields.set(`model_${slot}`, byId(`model-${slot}`).value);
  }
  return fields;
}

function collectReplayFields() {
  const fields = new URLSearchParams();
  fields.set("run_mode", "analyse_game");
  fields.set("replay_session", selectedSession);
  fields.set("replay_delay", byId("replay-delay").value);
  fields.set("replay_text_lead", byId("replay-text-lead").value);
  if (byId("replay-speak").checked) fields.set("replay_speak", "on");
  return fields;
}

async function postStart(fields) {
  showErrors([]);
  const response = await fetch("/start", {
    method: "POST",
    headers: {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
    body: fields.toString()
  });
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok && contentType.includes("application/json")) {
    const payload = await response.json();
    showErrors(payload.errors || [payload.error || "Could not start."]);
    return;
  }
  document.open();
  document.write(await response.text());
  document.close();
}

function resetDefaults() {
  byId("player-count").value = "4";
  byId("victory-points").value = "5";
  byId("chat-language").value = "english";
  byId("reaction-mode").value = "async";
  byId("game-context").value = "";
  updatePlayerCount();
}

byId("choose-new").addEventListener("click", () => setView("new"));
byId("choose-replay").addEventListener("click", () => setView("replay"));
byId("player-count").addEventListener("change", updatePlayerCount);
byId("session-search").addEventListener("input", renderSessions);
byId("refresh-sessions").addEventListener("click", refreshSessions);
byId("start-game").addEventListener("click", () => postStart(collectNewGameFields()));
byId("start-replay").addEventListener("click", () => {
  if (!selectedSession) {
    showErrors(["בחרו שידור חוזר מהרשימה לפני הפתיחה."]);
    return;
  }
  postStart(collectReplayFields());
});
byId("reset-defaults").addEventListener("click", resetDefaults);
byId("admin-unlock").addEventListener("click", unlockAdmin);
byId("admin-save").addEventListener("click", saveAdmin);

renderStatus();
renderStaticSelects();
renderModels();
renderPlayers();
renderSessions();
</script>
</body>
</html>"""
    return html.replace("__BOOTSTRAP_JSON__", safe_payload).encode("utf-8")


def render_public_spa(models: List[Dict[str, Any]], key_mode: str) -> bytes:
    bootstrap = {
        "models": models,
        "sessions": list_public_sessions(),
        "allSessions": [],
        "keyMode": key_mode,
        "env": {
            "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
            "gemini": bool(os.environ.get("GEMINI_API_KEY")),
        },
        "defaults": {
            "players": DEFAULT_PLAYER_NAMES,
            "colors": PLAYER_COLORS,
            "genders": PLAYER_GENDERS,
            "geminiTtsModels": GEMINI_TTS_MODELS,
            "geminiTtsVoices": GEMINI_TTS_VOICES,
            "relationshipModes": RELATIONSHIP_CONTEXT_MODES,
        },
    }
    safe_payload = json.dumps(bootstrap, ensure_ascii=False).replace("</", "<\\/")
    html = """<!doctype html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PyCatan AI Table</title>
<style>
:root {
  color-scheme: light;
  --ink: #20231f;
  --muted: #687066;
  --line: #d8d1c0;
  --paper: #fffaf0;
  --surface: #ffffff;
  --wash: #f3efe3;
  --wood: #9a642d;
  --wood-dark: #53351d;
  --forest: #2d7050;
  --sea: #2e7282;
  --danger: #b42318;
  --shadow: 0 18px 46px rgba(44, 39, 30, .14);
  --soft-shadow: 0 10px 28px rgba(44, 39, 30, .10);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
  background:
    radial-gradient(circle at 12% 10%, rgba(216,169,61,.18), transparent 30%),
    linear-gradient(135deg, rgba(46,114,130,.13), transparent 34%),
    linear-gradient(315deg, rgba(184,90,66,.14), transparent 42%),
    var(--wash);
  font-family: Inter, ui-sans-serif, "Segoe UI", Arial, sans-serif;
}
button, input, select, textarea { font: inherit; }
button { cursor: pointer; }
.app { min-height: 100vh; }
.hero {
  min-height: 430px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 420px);
  gap: clamp(22px, 4vw, 54px);
  align-items: center;
  padding: 34px clamp(18px, 5vw, 72px) 76px;
  color: #fff;
  background:
    linear-gradient(90deg, rgba(29,35,29,.96), rgba(37,46,39,.78) 52%, rgba(31,44,48,.70)),
    url("/static/images/Fields.png");
  background-size: cover, 240px 210px;
  background-position: center, left bottom;
  position: relative;
  overflow: hidden;
}
.hero::after {
  content: "";
  position: absolute;
  inset-inline-start: 0;
  bottom: 0;
  width: 100%;
  height: 74px;
  background:
    linear-gradient(0deg, rgba(32,35,31,.28), transparent),
    repeating-linear-gradient(90deg, rgba(255,255,255,.07) 0 1px, transparent 1px 64px);
  pointer-events: none;
}
.eyebrow {
  color: rgba(255,255,255,.72);
  font-weight: 850;
  margin-bottom: 12px;
  text-transform: uppercase;
}
.hero h1 {
  margin: 0;
  font-size: clamp(42px, 7vw, 86px);
  line-height: .95;
  letter-spacing: 0;
}
.hero p {
  max-width: 760px;
  margin: 20px 0 0;
  color: rgba(255,255,255,.84);
  font-size: clamp(17px, 2vw, 22px);
  line-height: 1.5;
}
.hero-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 26px; }
.status {
  width: min(100%, 420px);
  justify-self: end;
  border: 1px solid rgba(255,255,255,.22);
  border-radius: 8px;
  padding: 18px;
  background: rgba(255,255,255,.12);
  box-shadow: 0 20px 60px rgba(0,0,0,.22);
  backdrop-filter: blur(12px);
}
.status strong { display: block; margin-bottom: 8px; font-size: 18px; }
.status span { display: block; color: rgba(255,255,255,.76); line-height: 1.45; }
.table-preview { margin-top: 18px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.terrain {
  min-height: 74px;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,.22);
  background-size: cover;
  background-position: center;
}
.terrain.field { background-image: url("/static/images/Fields.png"); }
.terrain.forest { background-image: url("/static/images/Forest.png"); }
.terrain.hills { background-image: url("/static/images/Hills.png"); }
.terrain.pasture { background-image: url("/static/images/Pasture.png"); }
.terrain.mountain { background-image: url("/static/images/Mountains.png"); }
.terrain.sea { background: linear-gradient(135deg, #276d7c, #62a7b5); }
.workspace {
  width: min(1240px, calc(100% - 28px));
  margin: -58px auto 36px;
  display: grid;
  gap: 16px;
  position: relative;
  z-index: 2;
}
.choicebar { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.choice {
  min-height: 118px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 20px;
  text-align: left;
  color: var(--ink);
  background: var(--surface);
  box-shadow: var(--shadow);
  display: grid;
  gap: 8px;
}
.choice.active { border-color: var(--wood); box-shadow: inset 0 0 0 2px var(--wood), var(--shadow); background: #fffdf8; }
.choice strong { display: block; font-size: 24px; }
.choice span { color: var(--muted); line-height: 1.45; }
.view { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; align-items: start; }
.section {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  box-shadow: var(--soft-shadow);
}
.section h2, .section h3 { margin: 0 0 12px; letter-spacing: 0; }
.section h2 { font-size: 23px; }
.section h3 { font-size: 18px; }
.section-title { display: flex; justify-content: space-between; gap: 14px; align-items: start; margin-bottom: 14px; }
.section-title p { margin: 4px 0 0; color: var(--muted); line-height: 1.45; }
.stack { display: grid; gap: 14px; }
.grid-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
label { display: grid; gap: 7px; font-weight: 750; }
input, select, textarea {
  width: 100%;
  min-height: 42px;
  border: 1px solid #bac8bf;
  border-radius: 6px;
  padding: 9px 11px;
  background: #fff;
  color: var(--ink);
}
textarea { min-height: 92px; resize: vertical; }
.players { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.player { border: 1px solid var(--line); border-radius: 8px; padding: 13px; background: var(--surface); display: grid; gap: 10px; }
.player.hidden, .hidden { display: none !important; }
.player-head { display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 13px; }
.player-head strong { color: var(--ink); }
.actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.primary, .secondary, .quiet {
  min-height: 43px;
  border-radius: 7px;
  padding: 0 15px;
  font-weight: 850;
}
.primary { border: 1px solid var(--forest); background: var(--forest); color: #fff; }
.primary:hover { background: #245c42; }
.secondary { border: 1px solid var(--line); background: #fff; color: var(--wood-dark); }
.quiet { border: 0; background: transparent; color: var(--sea); padding: 0 4px; }
.side { position: sticky; top: 14px; }
.note { color: var(--muted); line-height: 1.55; font-size: 14px; }
.model-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; max-height: 372px; overflow: auto; }
.model-list li { border: 1px solid var(--line); border-radius: 7px; padding: 9px; background: #fff; }
.model-list strong { display: block; font-size: 12px; overflow-wrap: anywhere; }
.steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.steps li { display: grid; grid-template-columns: 28px 1fr; gap: 10px; align-items: start; color: var(--muted); line-height: 1.45; }
.steps b { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: #efe2c4; color: var(--wood-dark); }
.session-tools { display: flex; gap: 8px; margin-bottom: 12px; }
.session-list { display: grid; gap: 9px; max-height: 610px; overflow: auto; padding-right: 4px; }
.session-row {
  width: 100%;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 13px;
  display: grid;
  gap: 8px;
}
.session-row.active { border-color: var(--forest); box-shadow: inset 0 0 0 1px var(--forest); background: #fbfff8; }
.session-name { font-family: Consolas, "SFMono-Regular", monospace; font-weight: 850; font-size: 13px; }
.session-desc { color: var(--muted); line-height: 1.45; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; color: var(--muted); font-size: 12px; background: #f7f8f4; }
.errors { display: none; border: 1px solid #efb3aa; background: #fff5f2; color: var(--danger); border-radius: 8px; padding: 12px 14px; }
.errors.visible { display: block; }
.errors ul { margin: 0; padding-left: 20px; }
details { border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fff; }
summary { cursor: pointer; font-weight: 850; }
.admin-entry { justify-content: flex-end; margin-top: 16px; }
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 20;
  background: rgba(23, 28, 24, .58);
  display: grid;
  place-items: center;
  padding: 18px;
}
.modal {
  width: min(980px, 100%);
  max-height: min(760px, calc(100vh - 36px));
  overflow: hidden;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 32px 90px rgba(0,0,0,.30);
  display: grid;
  grid-template-rows: auto auto 1fr auto;
}
.modal-head { display: flex; justify-content: space-between; align-items: start; gap: 16px; padding: 18px; border-bottom: 1px solid var(--line); }
.modal-head h2 { margin: 0 0 4px; }
.modal-body { padding: 16px 18px; overflow: auto; }
.admin-list { display: grid; gap: 10px; max-height: 480px; overflow: auto; }
.admin-row { border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fff; display: grid; gap: 9px; }
.check { display: flex; gap: 8px; align-items: center; font-weight: 800; }
.check input { width: auto; min-height: auto; }
.admin-status { color: var(--muted); min-height: 20px; }
.admin-status.error { color: var(--danger); }
.modal-actions { display: flex; justify-content: space-between; gap: 10px; align-items: center; padding: 14px 18px; border-top: 1px solid var(--line); }
@media (max-width: 980px) {
  .hero { grid-template-columns: 1fr; }
  .status { justify-self: stretch; }
  .view { grid-template-columns: 1fr; }
  .side { position: static; }
}
@media (max-width: 720px) {
  .choicebar, .grid-2, .grid-3, .players { grid-template-columns: 1fr; }
  .hero { min-height: 520px; padding-bottom: 86px; }
  .workspace { width: min(100% - 20px, 1240px); }
  .session-tools, .modal-actions { display: grid; }
}
</style>
</head>
<body>
<div class="app">
  <header class="hero">
    <div>
      <div class="eyebrow">Public table</div>
      <h1>PyCatan AI Table</h1>
      <p>Start a live AI match or open a curated replay with decision analysis. The page should feel like a table, not a developer settings dump.</p>
      <div class="hero-actions">
        <button class="primary" type="button" onclick="setView('new')">Start a game</button>
        <button class="secondary" type="button" onclick="setView('replay')">Watch a replay</button>
      </div>
    </div>
    <div class="status">
      <strong>Table status</strong>
      <span id="runtime-status"></span>
      <div class="table-preview" aria-hidden="true">
        <div class="terrain field"></div>
        <div class="terrain forest"></div>
        <div class="terrain hills"></div>
        <div class="terrain pasture"></div>
        <div class="terrain mountain"></div>
        <div class="terrain sea"></div>
      </div>
    </div>
  </header>

  <main class="workspace">
    <div class="choicebar">
      <button class="choice active" id="choose-new" type="button">
        <strong>New game</strong>
        <span>Choose the players, victory target, and table language. Model details stay available without taking over the screen.</span>
      </button>
      <button class="choice" id="choose-replay" type="button">
        <strong>Replay library</strong>
        <span>Open a recorded match with the timeline, table talk, and decision trace ready for viewing.</span>
      </button>
    </div>
    <div id="errors" class="errors"></div>

    <section id="new-view" class="view">
      <div class="stack">
        <div class="section" id="keys-section">
          <div class="section-title">
            <div>
              <h2>Table access</h2>
              <p>Only needed for live games. Replays can be watched without entering keys.</p>
            </div>
          </div>
          <div class="grid-2">
            <label>OpenRouter key
              <input id="openrouter-key" type="password" autocomplete="off" placeholder="sk-or-...">
            </label>
            <label>Gemini voice key
              <input id="gemini-key" type="password" autocomplete="off" placeholder="AIza...">
            </label>
          </div>
          <p class="note">Keys stay in this local process and are not written to session metadata.</p>
        </div>

        <div class="section">
          <div class="section-title">
            <div>
              <h2>Game feel</h2>
              <p>The settings that shape the experience are here. Specialist controls are tucked away.</p>
            </div>
          </div>
          <div class="grid-3">
            <label>Players
              <select id="player-count">
                <option value="2">2 players</option>
                <option value="3">3 players</option>
                <option value="4" selected>4 players</option>
              </select>
            </label>
            <label>Victory target
              <input id="victory-points" type="number" min="1" step="1" value="5">
            </label>
            <label>Table language
              <select id="chat-language">
                <option value="english" selected>English</option>
                <option value="hebrew">Hebrew</option>
              </select>
            </label>
            <label>Table reactions
              <select id="reaction-mode">
                <option value="async" selected>Live and quick</option>
                <option value="sync">Orderly turns</option>
                <option value="off">Off</option>
                <option value="default">From config</option>
              </select>
            </label>
            <label>Relationship memory
              <select id="relationship-mode"></select>
            </label>
            <label>Random seed
              <input id="random-seed" type="number" step="1" placeholder="0">
            </label>
          </div>
          <label style="margin-top:12px">Table premise
            <textarea id="game-context" maxlength="4000" placeholder="Example: make the agents play like confident tournament commentators."></textarea>
          </label>
          <details style="margin-top:12px">
            <summary>Advanced controls</summary>
            <div class="grid-3" style="margin-top:12px">
              <label>Config file
                <input id="config-path" placeholder="pycatan/ai/config_dev.yaml">
              </label>
              <label>Reaction batch size
                <input id="reaction-batch-size" type="number" min="1" step="1" placeholder="5">
              </label>
              <label>Gemini TTS model
                <select id="gemini-tts-model"></select>
              </label>
              <label>Gemini voice
                <select id="gemini-tts-voice"></select>
              </label>
              <label>Voice
                <select id="tts-provider">
                  <option value="gemini" selected>Gemini</option>
                  <option value="off">Off</option>
                </select>
              </label>
            </div>
            <label class="check" style="margin-top:12px"><input id="no-llm" type="checkbox"> Offline mode, no new LLM calls</label>
          </details>
        </div>

        <div class="section">
          <div class="section-title">
            <div>
              <h2>Seats at the table</h2>
              <p>Keep the defaults or give each player a name and a different AI model.</p>
            </div>
          </div>
          <div class="players" id="players"></div>
        </div>

        <div class="actions">
          <button class="primary" type="button" id="start-game">Open the table</button>
          <button class="secondary" type="button" id="reset-defaults">Reset</button>
        </div>
      </div>

      <aside class="section side">
        <h3>What happens next</h3>
        <ol class="steps">
          <li><b>1</b><span>A live Catan board opens in the browser.</span></li>
          <li><b>2</b><span>Each AI takes turns, talks, checks options, and commits a move.</span></li>
          <li><b>3</b><span>You can follow the board, chat, and analysis as the game unfolds.</span></li>
        </ol>
        <details style="margin-top:14px">
          <summary>Available model list</summary>
          <p class="note">Only models that fit the game's tool and structured-output needs are shown.</p>
          <ol id="model-list" class="model-list"></ol>
        </details>
      </aside>
    </section>

    <section id="replay-view" class="view hidden">
      <div class="section">
        <div class="section-title">
          <div>
            <h2>Replay library</h2>
            <p>Pick a recorded match and open it as a guided replay with player decisions.</p>
          </div>
        </div>
        <div class="session-tools">
          <input id="session-search" placeholder="Search sessions, players, models">
          <button class="secondary" id="refresh-sessions" type="button">Refresh</button>
        </div>
        <div id="session-list" class="session-list"></div>
      </div>
      <aside class="section side">
        <h3>Selected replay</h3>
        <div id="session-preview" class="note">Choose a match from the library.</div>
        <div class="grid-2" style="margin-top:12px">
          <label>Replay pace
            <input id="replay-delay" type="number" min="0" step="0.1" value="2.5">
          </label>
          <label>Text lead
            <input id="replay-text-lead" type="number" min="0" step="0.05" value="0.25">
          </label>
        </div>
        <label class="check" style="margin-top:12px"><input id="replay-speak" type="checkbox"> Play cached table talk when available</label>
        <div class="actions" style="margin-top:14px">
          <button class="primary" type="button" id="start-replay">Open analysed replay</button>
        </div>
        <div class="actions admin-entry">
          <button class="quiet" type="button" id="admin-open">Manage replay library</button>
        </div>
      </aside>
    </section>
  </main>
</div>

<div class="modal-backdrop hidden" id="admin-modal" role="dialog" aria-modal="true" aria-labelledby="admin-title">
  <div class="modal">
    <div class="modal-head">
      <div>
        <h2 id="admin-title">Replay library management</h2>
        <div class="note">Choose which sessions are visible to guests and edit their public descriptions.</div>
      </div>
      <button class="secondary" type="button" id="admin-close">Close</button>
    </div>
    <div class="modal-body">
      <div class="grid-2">
        <label>Admin password
          <input id="admin-password" type="password" placeholder="Password">
        </label>
        <div class="actions" style="align-self:end">
          <button class="secondary" type="button" id="admin-unlock">Load sessions</button>
        </div>
      </div>
      <div id="admin-status" class="admin-status" style="margin-top:12px"></div>
      <div id="admin-list" class="admin-list hidden" style="margin-top:12px"></div>
    </div>
    <div class="modal-actions">
      <span class="note">Saved changes update the public replay list immediately.</span>
      <button class="primary hidden" type="button" id="admin-save">Save library</button>
    </div>
  </div>
</div>

<script>
const state = __BOOTSTRAP_JSON__;
const byId = (id) => document.getElementById(id);
let currentView = "new";
let selectedSession = "";
let adminUnlocked = false;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));
}

function showErrors(errors) {
  const box = byId("errors");
  if (!errors || !errors.length) {
    box.classList.remove("visible");
    box.innerHTML = "";
    return;
  }
  box.innerHTML = "<ul>" + errors.map((error) => `<li>${escapeHtml(error)}</li>`).join("") + "</ul>";
  box.classList.add("visible");
  box.scrollIntoView({behavior: "smooth", block: "center"});
}

function setAdminStatus(message, isError = false) {
  const status = byId("admin-status");
  status.textContent = message || "";
  status.classList.toggle("error", Boolean(isError));
}

function setView(view) {
  currentView = view;
  byId("choose-new").classList.toggle("active", view === "new");
  byId("choose-replay").classList.toggle("active", view === "replay");
  byId("new-view").classList.toggle("hidden", view !== "new");
  byId("replay-view").classList.toggle("hidden", view !== "replay");
  showErrors([]);
}

function optionHtml(value, label, selected = false) {
  return `<option value="${escapeHtml(value)}" ${selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
}

function renderStatus() {
  const hidden = state.keyMode === "env_hidden";
  byId("keys-section").classList.toggle("hidden", hidden);
  const llm = state.env.openrouter ? "OpenRouter connected" : "OpenRouter key needed";
  const tts = state.env.gemini ? "Gemini connected" : "Gemini key needed for voice";
  byId("runtime-status").textContent = hidden
    ? `${llm}. ${tts}. The key step is hidden because environment keys are enabled.`
    : "Enter keys once for a live game, then the table opens in the browser.";
}

function renderModels() {
  const models = state.models || [];
  byId("model-list").innerHTML = models.map((model) =>
    `<li><strong>${escapeHtml(model.id)}</strong><span class="note">${escapeHtml(model.name || "")}</span></li>`
  ).join("") || "<li>No model list loaded. Check OpenRouter connectivity.</li>";
}

function renderStaticSelects() {
  byId("relationship-mode").innerHTML = (state.defaults.relationshipModes || [])
    .map(([value, label], index) => optionHtml(value, label, index === 0)).join("");
  byId("gemini-tts-model").innerHTML = (state.defaults.geminiTtsModels || [])
    .map((value, index) => optionHtml(value, value, index === 0)).join("");
  byId("gemini-tts-voice").innerHTML = (state.defaults.geminiTtsVoices || [])
    .map((value) => optionHtml(value, value, value === "Kore")).join("");
}

function renderPlayers() {
  const models = state.models || [];
  const defaults = state.defaults.players || ["Alice", "Bob", "Charlie", "Diana"];
  const modelOptions = models.map((model, index) =>
    optionHtml(model.id, `${model.name || model.id} - ${model.id}`, index === 0)
  ).join("");
  byId("players").innerHTML = [1, 2, 3, 4].map((slot) => {
    const color = (state.defaults.colors || [])[slot - 1] || "";
    const gender = (state.defaults.genders || {})[slot] || "";
    return `<div class="player" data-player-card="${slot}">
      <div class="player-head"><strong>Player ${slot}</strong><span>${escapeHtml(color)} ${gender ? " / " + escapeHtml(gender) : ""}</span></div>
      <label>Name <input id="player-${slot}" value="${escapeHtml(defaults[slot - 1] || `Player ${slot}`)}"></label>
      <label>AI model <select id="model-${slot}">${modelOptions}</select></label>
    </div>`;
  }).join("");
  updatePlayerCount();
}

function updatePlayerCount() {
  const count = Number(byId("player-count").value || 4);
  document.querySelectorAll("[data-player-card]").forEach((card) => {
    card.classList.toggle("hidden", Number(card.dataset.playerCard) > count);
  });
}

function sessionMatches(session, term) {
  if (!term) return true;
  const haystack = [
    session.name,
    session.description,
    (session.players || []).join(" "),
    (session.models || []).join(" "),
    session.mode
  ].join(" ").toLowerCase();
  return haystack.includes(term.toLowerCase());
}

function publicDescription(session) {
  const raw = String(session.description || session.generated_description || "");
  if (raw.includes("׳") || raw.includes("�")) {
    const players = (session.players || []).length || "?";
    const decisions = session.response_count || 0;
    return `${players}-player AI Catan match with ${decisions} recorded AI responses.`;
  }
  return raw;
}

function sessionLine(session) {
  const players = (session.players || []).join(", ") || "Players not detected";
  const models = (session.models || []).join(", ") || "Model metadata unavailable";
  return `<span class="session-name">${escapeHtml(session.name)}</span>
    <span class="session-desc">${escapeHtml(publicDescription(session))}</span>
    <span class="note">${escapeHtml(players)}</span>
    <span class="note">${escapeHtml(models)}</span>
    <span class="chips">
      <span class="chip">${escapeHtml(session.mode || "recorded")}</span>
      <span class="chip">${session.response_count || 0} decisions</span>
      ${session.has_summary ? '<span class="chip">summary</span>' : ""}
      ${session.has_tts ? '<span class="chip">voice cache</span>' : ""}
    </span>`;
}

function renderSessions() {
  const term = byId("session-search").value || "";
  const sessions = (state.sessions || []).filter((session) => sessionMatches(session, term));
  byId("session-list").innerHTML = sessions.map((session) =>
    `<button class="session-row ${selectedSession === session.name ? "active" : ""}" type="button" data-session="${escapeHtml(session.name)}">${sessionLine(session)}</button>`
  ).join("") || '<div class="note">No public replay sessions are available yet.</div>';
  document.querySelectorAll("[data-session]").forEach((row) => {
    row.addEventListener("click", () => selectSession(row.dataset.session));
  });
}

async function refreshSessions() {
  const response = await fetch("/api/sessions", {cache: "no-store"});
  const payload = await response.json();
  state.sessions = payload.sessions || [];
  if (!state.sessions.some((session) => session.name === selectedSession)) selectedSession = "";
  renderSessions();
  renderSessionPreview(null);
}

async function selectSession(name) {
  selectedSession = name;
  renderSessions();
  renderSessionPreview({loading: true});
  try {
    const response = await fetch(`/api/session?session=${encodeURIComponent(name)}`, {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not load session.");
    renderSessionPreview(payload);
  } catch (error) {
    renderSessionPreview({error: error.message});
  }
}

function renderSessionPreview(preview) {
  if (!preview) {
    byId("session-preview").innerHTML = selectedSession ? "Loading..." : "Choose a match from the library.";
    return;
  }
  if (preview.loading) {
    byId("session-preview").textContent = "Loading session details...";
    return;
  }
  if (preview.error) {
    byId("session-preview").innerHTML = `<span style="color:var(--danger)">${escapeHtml(preview.error)}</span>`;
    return;
  }
  byId("session-preview").innerHTML = `<div class="session-name">${escapeHtml(preview.name)}</div>
    <p>${escapeHtml(publicDescription(preview))}</p>
    <div class="chips">
      <span class="chip">${(preview.players || []).length || "?"} players</span>
      <span class="chip">${preview.response_count || 0} decisions</span>
      <span class="chip">${(preview.markers || []).length} markers</span>
    </div>`;
}

function openAdminModal() {
  byId("admin-modal").classList.remove("hidden");
  setAdminStatus("");
  byId("admin-password").focus();
}

function closeAdminModal() {
  byId("admin-modal").classList.add("hidden");
}

function renderAdminList() {
  const sessions = state.allSessions || [];
  byId("admin-list").innerHTML = sessions.map((session) => `
    <div class="admin-row" data-admin-session="${escapeHtml(session.name)}">
      <label class="check"><input type="checkbox" class="admin-available" ${session.available ? "checked" : ""}> Public: ${escapeHtml(session.name)}</label>
      <div class="note">${escapeHtml((session.players || []).join(", ") || "No players detected")} / ${session.response_count || 0} decisions</div>
      <label>Public description
        <textarea class="admin-description" maxlength="600">${escapeHtml(session.description || session.generated_description || "")}</textarea>
      </label>
    </div>
  `).join("") || '<div class="note">No sessions found.</div>';
}

async function unlockAdmin() {
  const password = byId("admin-password").value;
  setAdminStatus("Loading sessions...");
  const response = await fetch(`/api/admin/sessions?password=${encodeURIComponent(password)}`, {cache: "no-store"});
  const payload = await response.json();
  if (!response.ok) {
    adminUnlocked = false;
    byId("admin-list").classList.add("hidden");
    byId("admin-save").classList.add("hidden");
    setAdminStatus(payload.error || "Wrong admin password.", true);
    return;
  }
  adminUnlocked = true;
  state.allSessions = payload.sessions || [];
  byId("admin-list").classList.remove("hidden");
  byId("admin-save").classList.remove("hidden");
  renderAdminList();
  setAdminStatus(`${state.allSessions.length} sessions loaded.`);
}

async function saveAdmin() {
  if (!adminUnlocked) {
    setAdminStatus("Load sessions before saving.", true);
    return;
  }
  const sessions = {};
  document.querySelectorAll("[data-admin-session]").forEach((row) => {
    sessions[row.dataset.adminSession] = {
      available: row.querySelector(".admin-available").checked,
      description: row.querySelector(".admin-description").value
    };
  });
  byId("admin-save").disabled = true;
  setAdminStatus("Saving...");
  try {
    const response = await fetch("/api/admin/sessions", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({password: byId("admin-password").value, sessions})
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not save library settings.");
    state.allSessions = payload.sessions || [];
    state.sessions = payload.publicSessions || [];
    renderSessions();
    renderSessionPreview(null);
    renderAdminList();
    setAdminStatus("Saved. Public replay library updated.");
  } catch (error) {
    setAdminStatus(error.message, true);
  } finally {
    byId("admin-save").disabled = false;
  }
}

function collectNewGameFields() {
  const fields = new URLSearchParams();
  fields.set("run_mode", "new_game");
  fields.set("player_count", byId("player-count").value);
  fields.set("openrouter_api_key", byId("openrouter-key").value);
  fields.set("gemini_api_key", byId("gemini-key").value);
  fields.set("chat_language", byId("chat-language").value);
  fields.set("relationship_context_mode", byId("relationship-mode").value);
  fields.set("reaction_mode", byId("reaction-mode").value);
  fields.set("victory_points", byId("victory-points").value);
  fields.set("random_seed", byId("random-seed").value);
  fields.set("game_context", byId("game-context").value);
  fields.set("config_path", byId("config-path").value);
  fields.set("reaction_batch_size", byId("reaction-batch-size").value);
  fields.set("tts_provider", byId("tts-provider").value);
  fields.set("gemini_tts_model", byId("gemini-tts-model").value);
  fields.set("gemini_tts_voice", byId("gemini-tts-voice").value);
  if (byId("no-llm").checked) fields.set("no_llm", "on");
  for (let slot = 1; slot <= 4; slot += 1) {
    fields.set(`player_${slot}`, byId(`player-${slot}`).value);
    fields.set(`model_${slot}`, byId(`model-${slot}`).value);
  }
  return fields;
}

function collectReplayFields() {
  const fields = new URLSearchParams();
  fields.set("run_mode", "analyse_game");
  fields.set("replay_session", selectedSession);
  fields.set("replay_delay", byId("replay-delay").value);
  fields.set("replay_text_lead", byId("replay-text-lead").value);
  if (byId("replay-speak").checked) fields.set("replay_speak", "on");
  return fields;
}

async function postStart(fields) {
  showErrors([]);
  const response = await fetch("/start", {
    method: "POST",
    headers: {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
    body: fields.toString()
  });
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok && contentType.includes("application/json")) {
    const payload = await response.json();
    showErrors(payload.errors || [payload.error || "Could not start."]);
    return;
  }
  document.open();
  document.write(await response.text());
  document.close();
}

function resetDefaults() {
  byId("player-count").value = "4";
  byId("victory-points").value = "5";
  byId("chat-language").value = "english";
  byId("reaction-mode").value = "async";
  byId("game-context").value = "";
  updatePlayerCount();
}

byId("choose-new").addEventListener("click", () => setView("new"));
byId("choose-replay").addEventListener("click", () => setView("replay"));
byId("player-count").addEventListener("change", updatePlayerCount);
byId("session-search").addEventListener("input", renderSessions);
byId("refresh-sessions").addEventListener("click", refreshSessions);
byId("start-game").addEventListener("click", () => postStart(collectNewGameFields()));
byId("start-replay").addEventListener("click", () => {
  if (!selectedSession) {
    showErrors(["Choose a replay session first."]);
    return;
  }
  postStart(collectReplayFields());
});
byId("reset-defaults").addEventListener("click", resetDefaults);
byId("admin-open").addEventListener("click", openAdminModal);
byId("admin-close").addEventListener("click", closeAdminModal);
byId("admin-unlock").addEventListener("click", unlockAdmin);
byId("admin-save").addEventListener("click", saveAdmin);
byId("admin-modal").addEventListener("click", (event) => {
  if (event.target === byId("admin-modal")) closeAdminModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeAdminModal();
});

renderStatus();
renderStaticSelects();
renderModels();
renderPlayers();
renderSessions();
</script>
</body>
</html>"""
    return html.replace("__BOOTSTRAP_JSON__", safe_payload).encode("utf-8")


def _request_fields(handler: BaseHTTPRequestHandler) -> Dict[str, str]:
    length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(length).decode("utf-8")
    content_type = handler.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}
        return {str(key): str(value).strip() for key, value in payload.items()}
    raw_fields = parse_qs(body, keep_blank_values=True)
    return {key: values[0].strip() for key, values in raw_fields.items()}


def _request_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    try:
        payload = json.loads(handler.rfile.read(length).decode("utf-8"))
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _as_bool_field(fields: Dict[str, str], name: str) -> bool:
    return name in fields and fields.get(name, "").lower() not in {"", "0", "false", "no", "off"}


def _default_slot_llms(models: List[Dict[str, Any]], slots: int = 4) -> List[Dict[str, str]]:
    fallback_model = models[0]["id"] if models else "openai/gpt-4o-mini"
    return [
        {
            "provider": "openrouter",
            "model_provider": provider_from_model_id(fallback_model),
            "model_name": fallback_model,
            "api_key_env_var": "OPENROUTER_API_KEY",
        }
        for _ in range(slots)
    ]


def collect_public_settings(port: int = 5000, key_mode: str = "ask") -> Dict[str, Any]:
    ready = threading.Event()
    settings: Dict[str, Any] = {}
    use_env_keys = key_mode == "env_hidden"
    models = fetch_openrouter_models(os.environ.get("OPENROUTER_API_KEY", ""))
    valid_model_ids = {model["id"] for model in models}
    valid_providers = {model["provider"] for model in models}

    class ReusableThreadingHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True

    class PublicEntryHandler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed_url = urlparse(self.path)
            if parsed_url.path == "/healthz":
                _json_response(self, {"ok": True})
                return
            if parsed_url.path == "/api/sessions":
                _json_response(self, {"sessions": list_public_sessions()})
                return
            if parsed_url.path == "/api/admin/sessions":
                password = parse_qs(parsed_url.query).get("password", [""])[0]
                if not _admin_password_ok(password):
                    _json_response(self, {"error": "Wrong admin password."}, status=403)
                    return
                _json_response(self, {"sessions": list_all_sessions()})
                return
            if parsed_url.path == "/api/session":
                session_ref = parse_qs(parsed_url.query).get("session", [""])[0].strip()
                if not session_ref:
                    _json_response(self, {"error": "Missing session."}, status=400)
                    return
                try:
                    _json_response(self, _session_preview(session_ref))
                except Exception as exc:
                    _json_response(self, {"error": str(exc)}, status=400)
                return
            _html_response(self, render_public_spa(models, key_mode))

        def do_POST(self) -> None:
            if self.path == "/api/admin/sessions":
                try:
                    _save_admin_manifest(_request_json(self))
                    _json_response(self, {"sessions": list_all_sessions(), "publicSessions": list_public_sessions()})
                except PermissionError as exc:
                    _json_response(self, {"error": str(exc)}, status=403)
                except Exception as exc:
                    _json_response(self, {"error": str(exc)}, status=400)
                return

            if self.path != "/start":
                self.send_error(404)
                return

            fields = _request_fields(self)
            errors: List[str] = []
            run_mode = fields.get("run_mode", "new_game")
            if run_mode not in {"new_game", "analyse_game"}:
                errors.append("Choose a valid mode.")
            live_mode = run_mode == "new_game"
            no_llm = _as_bool_field(fields, "no_llm")

            api_key = fields.get("openrouter_api_key") or (
                os.environ.get("OPENROUTER_API_KEY", "") if use_env_keys else ""
            )
            if live_mode and not no_llm and not api_key:
                errors.append("Enter an OpenRouter API key or run with --use-env-keys and OPENROUTER_API_KEY.")

            replay_session = fields.get("replay_session", "")
            replay_session_path = None
            if run_mode == "analyse_game":
                if not replay_session:
                    errors.append("Choose a recorded replay session.")
                else:
                    try:
                        replay_session_path = resolve_session_path(replay_session)
                    except FileNotFoundError as exc:
                        errors.append(str(exc))

            config_path = fields.get("config_path", "")
            if config_path and not Path(config_path).exists():
                errors.append("Config file was not found.")

            player_count = _parse_optional_int(fields.get("player_count", "4"), errors, "Player count") or 4
            if player_count not in (2, 3, 4):
                errors.append("Choose 2, 3, or 4 players.")
                player_count = 4

            reaction_mode = fields.get("reaction_mode", "async")
            if reaction_mode not in {"default", "off", "sync", "async"}:
                errors.append("Choose a valid side-reaction mode.")

            relationship_context_mode = fields.get("relationship_context_mode", "legacy")
            valid_relationship_modes = {value for value, _label in RELATIONSHIP_CONTEXT_MODES}
            if relationship_context_mode not in valid_relationship_modes:
                errors.append("Choose a valid relationship memory mode.")
                relationship_context_mode = "legacy"

            reaction_batch_size = _parse_optional_int(
                fields.get("reaction_batch_size", ""), errors, "Reaction batch size"
            )
            victory_points = _parse_optional_int(fields.get("victory_points", "5"), errors, "Victory target") or 5
            game_context = fields.get("game_context", "").strip()
            if len(game_context) > 4000:
                errors.append("Optional story/context must be 4000 characters or less.")

            random_seed = 0
            if fields.get("random_seed"):
                try:
                    random_seed = int(fields["random_seed"])
                except ValueError:
                    errors.append("Random seed must be a whole number.")

            replay_delay = _parse_float(fields.get("replay_delay", "2.5"), 2.5, errors, "Replay delay")
            replay_text_lead = _parse_float(fields.get("replay_text_lead", "0.25"), 0.25, errors, "Text lead")
            replay_speak = _as_bool_field(fields, "replay_speak")

            tts_provider = fields.get("tts_provider", "gemini")
            if tts_provider not in {"off", "gemini"}:
                errors.append("Choose a valid voice provider.")
            gemini_api_key = fields.get("gemini_api_key") or (
                os.environ.get("GEMINI_API_KEY", "") if use_env_keys else ""
            )
            if live_mode and tts_provider == "gemini" and not gemini_api_key:
                errors.append("Enter a Gemini API key for table voice or run with --use-env-keys and GEMINI_API_KEY.")

            slot_llms: List[Dict[str, str]] = []
            player_configs: List[Dict[str, Any]] = []
            seen_names = set()
            if live_mode:
                for index in range(player_count):
                    slot = index + 1
                    name = fields.get(f"player_{slot}") or DEFAULT_PLAYER_NAMES[index]
                    model_id = fields.get(f"model_{slot}") or ""
                    provider = provider_from_model_id(model_id)
                    if not name:
                        errors.append(f"Player {slot} needs a name.")
                    if name.lower() in seen_names:
                        errors.append("Player names must be unique.")
                    seen_names.add(name.lower())
                    if provider and provider not in valid_providers:
                        errors.append(f"Unknown model provider for player {slot}: {provider}")
                    if not no_llm:
                        if not model_id:
                            errors.append(f"Player {slot} needs a model.")
                        elif model_id not in valid_model_ids:
                            errors.append(
                                f"Model for player {slot} is not suitable. Choose a listed model with tools, "
                                f"response_format, text output, >= {MIN_CONTEXT_LENGTH} context and "
                                f">= {MIN_COMPLETION_TOKENS} output tokens."
                            )
                    llm = {
                        "provider": "openrouter",
                        "model_provider": provider_from_model_id(model_id),
                        "model_name": model_id,
                        "api_key_env_var": "OPENROUTER_API_KEY",
                    }
                    slot_llms.append(llm)
                    player_configs.append({"name": name, "is_ai": True, "color": PLAYER_COLORS[index], "llm": llm})
            else:
                slot_llms = _default_slot_llms(models)

            if errors:
                _json_response(self, {"errors": errors}, status=400)
                return

            if api_key:
                os.environ["OPENROUTER_API_KEY"] = api_key
            if gemini_api_key:
                os.environ["GEMINI_API_KEY"] = gemini_api_key
            if tts_provider == "gemini":
                os.environ["TTS_PROVIDER"] = "gemini"
                os.environ["GEMINI_TTS_ENABLED"] = "true"
                os.environ["GEMINI_TTS_MODEL_ID"] = fields.get("gemini_tts_model", GEMINI_TTS_MODELS[0])
                os.environ["GEMINI_TTS_VOICE_NAME"] = fields.get("gemini_tts_voice", "Kore")
                os.environ.setdefault("GEMINI_TTS_PLAY_AUDIO", "true")
            else:
                os.environ["TTS_PROVIDER"] = "off"

            settings.update({
                "run_mode": run_mode,
                "player_configs": player_configs,
                "slot_llms": slot_llms,
                "chat_language": normalize_chat_language(fields.get("chat_language") or "english"),
                "relationship_context_mode": relationship_context_mode,
                "no_llm": no_llm,
                "reaction_mode": reaction_mode,
                "reaction_batch_size": reaction_batch_size,
                "victory_points": victory_points,
                "game_context": game_context,
                "random_seed": random_seed,
                "config_path": config_path or None,
                "replay_session": replay_session or None,
                "replay_session_path": str(replay_session_path) if replay_session_path else None,
                "replay_max_decisions": None,
                "replay_through": None,
                "replay_stop_before": None,
                "replay_skip_chat": False,
                "replay_delay": replay_delay,
                "replay_text_lead": replay_text_lead,
                "replay_speak": replay_speak,
                "tts": {
                    "provider": tts_provider,
                    "gemini_model": fields.get("gemini_tts_model", GEMINI_TTS_MODELS[0]),
                    "gemini_voice": fields.get("gemini_tts_voice", "Kore"),
                    "key_source": "env_or_redacted" if tts_provider != "off" else "off",
                },
            })

            starting_players = player_configs if live_mode else [
                {"name": replay_session or "recorded session", "llm": {"model_name": "analysed replay"}}
            ]
            _html_response(self, render_starting_page(starting_players, run_mode))
            ready.set()

    bind_host = os.environ.get("PYCATAN_BIND_HOST", "127.0.0.1")
    public_host = os.environ.get("PYCATAN_PUBLIC_HOST", "localhost")
    server = ReusableThreadingHTTPServer((bind_host, port), PublicEntryHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://{public_host}:{port}/"
    print(f"[SETUP] Public entry page: {url}")
    if os.environ.get("PYCATAN_NO_BROWSER", "").lower() not in {"1", "true", "yes", "on"}:
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"[SETUP] Could not open browser automatically: {exc}")
    print("[SETUP] Waiting for public entry settings...")
    try:
        while not ready.wait(timeout=0.25):
            pass
    finally:
        server.shutdown()
        server.server_close()
    return settings


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Public PyCatan AI entrypoint")
    parser.add_argument("--config", type=str, help="Optional AI config YAML")
    parser.add_argument("--port", type=int, default=5000, help="Setup and game web port")
    parser.add_argument(
        "--use-env-keys",
        action="store_true",
        help="Load keys from ENV/.env and hide the browser API-key step",
    )
    args = parser.parse_args()

    load_env_file()
    settings = collect_public_settings(port=args.port, key_mode=("env_hidden" if args.use_env_keys else "ask"))
    ai_config = load_ai_config(settings.get("config_path") or args.config)
    ai_config.llm.provider = "openrouter"
    ai_config.llm.api_key_env_var = "OPENROUTER_API_KEY"
    ai_config.llm.enable_streaming = True
    ai_config.agent.chat_language = settings["chat_language"]
    ai_config.agent.relationship_context_mode = settings["relationship_context_mode"]
    _apply_reaction_settings(ai_config, settings)

    replay_session_path = resolve_session_path(settings["replay_session"]) if settings["replay_session"] else None
    watch_mode = settings["run_mode"] == "analyse_game"
    if watch_mode and not replay_session_path:
        parser.error("Replay mode requires a replay session")

    if (
        watch_mode
        and replay_session_path
        and not os.environ.get("AI_TTS_CACHE_DIR")
        and not os.environ.get("PYCATAN_TTS_CACHE_DIR")
    ):
        os.environ["AI_TTS_CACHE_DIR"] = str(replay_session_path / "tts_cache")
        os.environ["AI_TTS_CACHE_DIR_AUTO"] = "replay_session_default"
        print(f"[REPLAY] TTS cache: {os.environ['AI_TTS_CACHE_DIR']}")
    elif not watch_mode and not os.environ.get("AI_TTS_CACHE_DIR") and not os.environ.get("PYCATAN_TTS_CACHE_DIR"):
        print("[TTS] Voice cache: per-session tts_cache/")

    replay_decision_list: List[Dict[str, Any]] = []
    replay_decisions_by_player: Dict[str, List[Dict[str, Any]]] = {}
    if replay_session_path:
        replay_decision_list = load_replay_decision_chain(replay_session_path)
        replay_decisions_by_player = group_replay_decisions(replay_decision_list)
        player_names = _infer_session_player_names(replay_session_path) or infer_players_from_decisions(replay_decision_list)
        player_configs = _player_configs_for_replay(player_names, settings["slot_llms"])
        print(f"[REPLAY] Source: {replay_session_path}")
        action_count = sum(1 for item in replay_decision_list if item.get("has_action"))
        print(f"[REPLAY] Loaded {len(replay_decision_list)} parsed responses ({action_count} actions)")
    else:
        player_configs = settings["player_configs"]

    if not player_configs:
        parser.error("No players could be inferred for this run")

    if not settings["no_llm"]:
        ai_config.llm.model_name = player_configs[0]["llm"]["model_name"]
    send_to_llm = (not settings["no_llm"]) and not watch_mode

    print(f"[MODE] LLM: {'ON' if send_to_llm else 'OFF'} | Actions: Auto")
    print(f"[CONFIG] Victory points to win: {settings['victory_points']}")
    print(f"[CONFIG] Relationship context: {settings['relationship_context_mode']}")
    print("[CONFIG] Public entry + OpenRouter per-agent models")
    game_manager, ai_manager, web_viz = create_game(
        player_configs,
        send_to_llm=send_to_llm,
        manual_actions=False,
        config=ai_config,
        replay_decisions=replay_decisions_by_player,
        replay_chat=not settings["replay_skip_chat"],
        replay_speak=(settings["replay_speak"] and not watch_mode),
        replay_only=watch_mode,
        web_port=args.port,
        random_seed=settings["random_seed"],
        game_config={
            "victory_points": settings["victory_points"],
            "game_context": settings.get("game_context", ""),
        },
    )
    write_run_settings_metadata(ai_manager.get_session_path(), settings, player_configs, source="play_public_entry")

    if send_to_llm:
        for player in player_configs:
            ai_manager.set_agent_llm_config(
                player_name=player["name"],
                provider=player["llm"]["provider"],
                model_name=player["llm"]["model_name"],
                api_key_env_var=player["llm"]["api_key_env_var"],
            )
            print(f"[OPENROUTER] {player['name']}: {player['llm']['model_name']}")

    if replay_session_path:
        annotate_replay_session(
            ai_manager,
            replay_session_path,
            replay_decision_list,
            settings["replay_through"],
            settings["replay_stop_before"],
            mode="analyse_game_visual_playback",
        )
        print(f"[REPLAY] New derived session: {ai_manager.get_session_path()}")

    if watch_mode:
        run_replay_viewer(
            game_manager,
            ai_manager,
            web_viz,
            delay_seconds=max(0.0, settings["replay_delay"]),
            source_session=replay_session_path,
            text_lead_seconds=max(0.0, settings["replay_text_lead"]),
            open_browser=False,
            replay_events=replay_decision_list,
        )
    else:
        run_game(game_manager, ai_manager, web_viz)


if __name__ == "__main__":
    main()
