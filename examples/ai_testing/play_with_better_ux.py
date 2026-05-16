#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-page browser setup for PyCatan OpenRouter runs and replays."""

import html as html_lib
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
    _as_bool_field,
    _infer_session_player_names,
    _load_session_final_state,
    _minimum_recorded_actions_for_state,
    _parse_float,
    _parse_optional_int,
    _player_configs_for_replay,
    fetch_openrouter_models,
    infer_session_run_settings,
    is_suitable_openrouter_model,
    provider_from_model_id,
    render_starting_page,
    write_run_settings_metadata,
)
from pycatan.ai.config import normalize_chat_language


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
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _session_sort_key(path: Path) -> str:
    return path.name.replace("session_", "")


def _session_summary(session_dir: Path) -> Dict[str, Any]:
    metadata = _read_json(session_dir / "session_metadata.json")
    summary = _read_json(session_dir / "session_summary.json")
    players = _infer_session_player_names(session_dir)
    response_count = len(list(session_dir.glob("*/responses/response_*.json")))
    prompt_count = len(list(session_dir.glob("*/prompts/prompt_*.json")))
    has_tts = (session_dir / "tts_cache").exists()
    replay = metadata.get("replay") or {}
    mode = replay.get("mode") or metadata.get("mode") or ("summary" if summary else "recorded")
    return {
        "name": session_dir.name,
        "path": str(session_dir),
        "start_time": metadata.get("start_time", ""),
        "mode": mode,
        "derived_from": metadata.get("derived_from", ""),
        "source_session": replay.get("source_session", ""),
        "players": players,
        "response_count": response_count,
        "prompt_count": prompt_count,
        "has_summary": bool(summary),
        "has_tts": has_tts,
    }


def list_sessions(limit: int = 120) -> List[Dict[str, Any]]:
    if not LOGS_DIR.exists():
        return []
    session_dirs = [
        path for path in LOGS_DIR.iterdir()
        if path.is_dir() and path.name.startswith("session_")
    ]
    session_dirs.sort(key=_session_sort_key, reverse=True)
    return [_session_summary(path) for path in session_dirs[:limit]]


def _session_preview(session_ref: str) -> Dict[str, Any]:
    session_dir = resolve_session_path(session_ref)
    summary = _session_summary(session_dir)
    markers = list_replay_marker_options(session_dir)
    final_state = _load_session_final_state(session_dir)
    minimum_actions = _minimum_recorded_actions_for_state(final_state)
    settings = infer_session_run_settings(session_dir)
    return {
        **summary,
        "markers": markers,
        "settings": settings,
        "minimum_actions_for_resume": minimum_actions,
        "can_resume_full": not minimum_actions or summary["response_count"] >= minimum_actions,
    }


def render_spa(models: List[Dict[str, Any]], key_mode: str) -> bytes:
    bootstrap = {
        "models": models,
        "sessions": list_sessions(),
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
    payload = json.dumps(bootstrap, ensure_ascii=False)
    safe_payload = payload.replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PyCatan Better UX</title>
<style>
:root {{
  color-scheme: light;
  --bg: #edf1f4;
  --ink: #17202a;
  --muted: #5e6b78;
  --line: #cbd5df;
  --panel: #ffffff;
  --soft: #f7f9fb;
  --accent: #236b5e;
  --accent-dark: #174d44;
  --warn: #9a5b12;
  --danger: #b42318;
  --blue: #1f5f8b;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  font-family: "Segoe UI", Arial, sans-serif;
  color: var(--ink);
  background: var(--bg);
}}
button, input, select, textarea {{ font: inherit; }}
button {{ cursor: pointer; }}
.shell {{
  min-height: 100vh;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
}}
.drawer {{
  background: #17202a;
  color: #fff;
  padding: 24px 18px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}}
.brand {{ padding: 4px 6px 14px; border-bottom: 1px solid rgba(255,255,255,.16); }}
.brand h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
.brand p {{ margin: 8px 0 0; color: rgba(255,255,255,.72); line-height: 1.45; }}
.nav {{ display: grid; gap: 10px; }}
.nav button {{
  width: 100%;
  min-height: 48px;
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 8px;
  padding: 10px 12px;
  text-align: right;
  color: #fff;
  background: rgba(255,255,255,.06);
  font-weight: 800;
}}
.nav button.active {{ background: #fff; color: #17202a; }}
.drawer-note {{
  margin-top: auto;
  color: rgba(255,255,255,.7);
  font-size: 13px;
  line-height: 1.55;
}}
.workspace {{ padding: 26px; }}
.topbar {{
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 20px;
}}
.topbar h2 {{ margin: 0; font-size: 30px; letter-spacing: 0; }}
.topbar p {{ margin: 8px 0 0; color: var(--muted); line-height: 1.5; max-width: 820px; }}
.pill {{
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0 10px;
  background: #fff;
  color: var(--muted);
  font-size: 13px;
  white-space: nowrap;
}}
.layout {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 18px;
  align-items: start;
}}
.panel {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
}}
.panel h3 {{ margin: 0 0 12px; font-size: 18px; }}
.stack {{ display: grid; gap: 14px; }}
.grid-2 {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
.grid-3 {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
label {{ display: grid; gap: 7px; font-weight: 750; color: var(--ink); }}
input, select, textarea {{
  width: 100%;
  border: 1px solid #b7c3ce;
  border-radius: 6px;
  padding: 10px 11px;
  background: #fbfcfd;
  color: var(--ink);
}}
textarea {{ min-height: 86px; resize: vertical; }}
.segmented {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}}
.segmented button {{
  min-height: 52px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--soft);
  color: var(--ink);
  font-weight: 850;
}}
.segmented button.active {{ border-color: var(--accent); color: #fff; background: var(--accent); }}
.session-tools {{ display: flex; gap: 8px; margin-bottom: 12px; }}
.session-tools input {{ min-width: 0; }}
.session-list {{ display: grid; gap: 8px; max-height: 580px; overflow: auto; padding-left: 4px; }}
.session-row {{
  width: 100%;
  text-align: right;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 11px 12px;
  display: grid;
  gap: 6px;
}}
.session-row.active {{ border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }}
.session-name {{ direction: ltr; text-align: left; font-family: Consolas, monospace; font-size: 13px; font-weight: 850; }}
.meta {{ color: var(--muted); font-size: 13px; line-height: 1.4; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.chip {{ border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; color: var(--muted); font-size: 12px; background: var(--soft); }}
.preview-empty {{ min-height: 280px; display: grid; place-items: center; color: var(--muted); text-align: center; }}
.preview-title {{ direction: ltr; text-align: left; font-family: Consolas, monospace; font-weight: 850; }}
.player-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
.player-card {{ border: 1px solid var(--line); border-radius: 8px; padding: 13px; background: #fff; display: grid; gap: 10px; }}
.player-card.hidden {{ display: none; }}
.player-head {{ display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 13px; }}
.actions {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
.check {{ display: flex; align-items: center; gap: 8px; font-weight: 700; }}
.check input {{ width: auto; }}
details {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: var(--soft); }}
summary {{ cursor: pointer; font-weight: 850; }}
.primary, .secondary, .link-button {{
  min-height: 42px;
  border-radius: 7px;
  padding: 0 15px;
  font-weight: 850;
}}
.primary {{ border: 1px solid var(--accent); background: var(--accent); color: #fff; }}
.secondary {{ border: 1px solid var(--line); background: #fff; color: var(--accent-dark); }}
.link-button {{ border: 0; background: transparent; color: var(--blue); padding: 0 4px; }}
.danger {{ color: var(--danger); }}
.errors {{ display: none; border: 1px solid #f0aaa0; background: #fff3f0; color: var(--danger); border-radius: 8px; padding: 12px 14px; }}
.errors.visible {{ display: block; }}
.errors ul {{ margin: 0; padding-right: 20px; }}
.hidden {{ display: none !important; }}
.model-help {{ color: var(--muted); font-size: 13px; line-height: 1.45; }}
.side {{ position: sticky; top: 18px; }}
.model-list {{ margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; max-height: 360px; overflow: auto; }}
.model-list li {{ border: 1px solid var(--line); border-radius: 7px; padding: 9px; background: var(--soft); }}
.model-list strong {{ direction: ltr; display: block; font-size: 12px; text-align: left; }}
@media (max-width: 1050px) {{
  .shell {{ grid-template-columns: 1fr; }}
  .drawer {{ position: static; }}
  .layout {{ grid-template-columns: 1fr; }}
  .side {{ position: static; }}
}}
@media (max-width: 720px) {{
  .workspace {{ padding: 16px; }}
  .grid-2, .grid-3, .player-grid {{ grid-template-columns: 1fr; }}
  .topbar {{ display: grid; }}
}}
</style>
</head>
<body>
<div class="shell">
  <aside class="drawer">
    <div class="brand">
      <h1>PyCatan</h1>
      <p>מסך אחד להפעלה, המשך משחק, וצפייה/ניתוח של סשנים קיימים.</p>
    </div>
    <nav class="nav">
      <button id="nav-run" class="active" type="button">הרצת משחק</button>
      <button id="nav-replay" type="button">צפייה וניתוח סשן</button>
    </nav>
    <div class="drawer-note">
      ברירת המחדל למשחק חי היא OpenRouter למודלים ו-Gemini לקול. תגובות צד רצות Async כברירת מחדל.
    </div>
  </aside>
  <main class="workspace">
    <div class="topbar">
      <div>
        <h2 id="page-title">הרצת משחק</h2>
        <p id="page-subtitle">בחר משחק חדש או המשך מסשן מוקלט, הזן מפתחות, וקבע מודלים לשחקנים.</p>
      </div>
      <span class="pill" id="env-pill"></span>
    </div>
    <div id="errors" class="errors"></div>
    <section id="run-view" class="layout">
      <div class="stack">
        <div class="panel">
          <h3>מסלול</h3>
          <div class="segmented">
            <button id="new-game-tab" type="button" class="active">להתחיל מחדש</button>
            <button id="resume-tab" type="button">שחזור והמשך משחק קיים</button>
          </div>
        </div>
        <div class="panel">
          <h3>מפתחות</h3>
          <div class="grid-2">
            <label>OpenRouter API key
              <input id="openrouter-key" type="password" autocomplete="off">
            </label>
            <label>Gemini API key
              <input id="gemini-key" type="password" autocomplete="off">
            </label>
          </div>
        </div>
        <div id="resume-panel" class="panel hidden">
          <h3>נקודת שחזור</h3>
          <div class="grid-2">
            <label>סשן מקור
              <select id="resume-session"></select>
            </label>
            <label>מאיפה להמשיך
              <select id="resume-point-mode">
                <option value="">כל מה שניתן, ואז Live</option>
                <option value="stop_before">עצור לפני פעולה</option>
                <option value="through">נגן עד פעולה כולל</option>
                <option value="max">מספר החלטות מקסימלי</option>
              </select>
            </label>
            <label id="resume-marker-label">Marker
              <select id="resume-marker"></select>
            </label>
            <label id="resume-max-label" class="hidden">Max decisions
              <input id="resume-max" type="number" min="1" step="1">
            </label>
          </div>
          <p class="model-help" id="resume-status">בחר סשן כדי לטעון שחקנים ונקודות עצירה.</p>
        </div>
        <div class="panel">
          <h3>הגדרות מינימליות</h3>
          <div class="grid-3">
            <label>תגובות צד
              <select id="reaction-mode">
                <option value="async" selected>Async parallel</option>
                <option value="sync">Sync, בלי מקביליות</option>
                <option value="off">כבוי</option>
                <option value="default">לפי config</option>
              </select>
            </label>
            <label>שפה בצ'אט
              <select id="chat-language">
                <option value="hebrew" selected>עברית</option>
                <option value="english">English</option>
              </select>
            </label>
            <label>Victory points
              <input id="victory-points" type="number" min="1" step="1" value="5">
            </label>
            <label>Relationship context
              <select id="relationship-mode"></select>
            </label>
            <label>Player count
              <select id="player-count">
                <option value="2">2</option>
                <option value="3">3</option>
                <option value="4" selected>4</option>
              </select>
            </label>
            <label>Random seed
              <input id="random-seed" type="number" step="1" placeholder="0">
            </label>
          </div>
          <label style="margin-top:12px">Additional game context
            <textarea id="game-context" maxlength="4000"></textarea>
          </label>
          <details style="margin-top:12px">
            <summary>אפשרויות מתקדמות</summary>
            <div class="grid-3" style="margin-top:12px">
              <label>Config file
                <input id="config-path" placeholder="pycatan/ai/config_dev.yaml">
              </label>
              <label>Reaction batch size
                <input id="reaction-batch-size" type="number" min="1" step="1" placeholder="5">
              </label>
              <label>Voice
                <select id="tts-provider">
                  <option value="gemini" selected>Gemini TTS</option>
                  <option value="off">Off</option>
                </select>
              </label>
            </div>
            <div class="actions" style="margin-top:12px">
              <label class="check"><input id="no-llm" type="checkbox"> Offline / no new LLM calls</label>
              <label class="check" id="replay-skip-wrap"><input id="replay-skip-chat" type="checkbox"> לא לשדר צ'אט מוקלט בזמן fast replay</label>
              <label class="check" id="replay-speak-wrap"><input id="replay-speak" type="checkbox"> להשמיע צ'אט מוקלט מה-cache</label>
            </div>
          </details>
        </div>
        <div class="panel">
          <h3>מודלים לשחקנים</h3>
          <div class="player-grid" id="players"></div>
        </div>
        <div class="actions">
          <button class="primary" type="button" id="start-run">התחל</button>
          <button class="secondary" type="button" id="refresh-sessions">רענן סשנים</button>
        </div>
      </div>
      <aside class="panel side">
        <h3>מודלים זמינים</h3>
        <p class="model-help">מוצגים רק מודלים עם tools, response_format, פלט טקסט, לפחות {MIN_CONTEXT_LENGTH:,} context ולפחות {MIN_COMPLETION_TOKENS:,} output tokens.</p>
        <ol id="model-list" class="model-list"></ol>
      </aside>
    </section>
    <section id="replay-view" class="layout hidden">
      <div class="panel">
        <h3>ספריית סשנים</h3>
        <div class="actions" style="margin-bottom:12px">
          <button class="secondary" type="button" id="replay-back-home">Back to main screen</button>
        </div>
        <div id="session-library">
          <div class="session-tools">
            <input id="session-search" placeholder="חיפוש לפי שם סשן או שחקן">
            <button class="secondary" type="button" id="clear-session-search">נקה</button>
          </div>
          <div id="session-list" class="session-list"></div>
        </div>
        <div id="session-preview" class="hidden"></div>
      </div>
      <aside class="panel side">
        <h3>אפשרויות צפייה וניתוח</h3>
        <div class="grid-2">
          <label>Delay
            <input id="replay-delay" type="number" min="0" step="0.1" value="2.5">
          </label>
          <label>Text lead
            <input id="replay-text-lead" type="number" min="0" step="0.05" value="0.25">
          </label>
        </div>
        <label style="margin-top:12px">מצב
          <select id="replay-mode">
            <option value="analyse_game" selected>צפייה עם Analyse</option>
            <option value="watch_replay">צפייה בלבד</option>
          </select>
        </label>
        <label class="check" style="margin-top:12px">
          <input id="analysis-replay-speak" type="checkbox" checked>
          השמע הקלטות/צ'אט מה-cache בזמן playback
        </label>
        <label style="margin-top:12px">Gemini API key לאודיו
          <input id="replay-gemini-key" type="password" autocomplete="off">
        </label>
        <div class="actions" style="margin-top:14px">
          <button class="primary" type="button" id="start-replay">פתח צפייה וניתוח</button>
        </div>
      </aside>
    </section>
  </main>
</div>
<script id="bootstrap" type="application/json">{safe_payload}</script>
<script>
const state = JSON.parse(document.getElementById('bootstrap').textContent);
let view = 'run';
let runMode = 'new_game';
let selectedReplaySession = '';
const byId = (id) => document.getElementById(id);
const modelsByProvider = state.models.reduce((acc, model) => {{
  (acc[model.provider] ||= []).push(model);
  return acc;
}}, {{}});
const providers = Object.keys(modelsByProvider).sort();

function setErrors(errors) {{
  const box = byId('errors');
  if (!errors || !errors.length) {{
    box.classList.remove('visible');
    box.innerHTML = '';
    return;
  }}
  box.classList.add('visible');
  box.innerHTML = '<ul>' + errors.map((error) => `<li>${{escapeHtml(error)}}</li>`).join('') + '</ul>';
  window.scrollTo({{ top: 0, behavior: 'smooth' }});
}}
function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
}}
function modelLabel(model) {{
  const ctx = model.context_length ? ` - ${{Number(model.context_length).toLocaleString()}} ctx` : '';
  return `${{model.name}} - ${{model.id}}${{ctx}}`;
}}
function sessionLine(session) {{
  const players = (session.players || []).join(', ') || 'ללא שחקנים מזוהים';
  return `<span class="session-name">${{escapeHtml(session.name)}}</span>
    <span class="meta">${{escapeHtml(players)}} · ${{session.response_count || 0}} responses</span>
    <span class="chips">
      <span class="chip">${{escapeHtml(session.mode || 'recorded')}}</span>
      ${{session.has_summary ? '<span class="chip">summary</span>' : ''}}
      ${{session.has_tts ? '<span class="chip">tts</span>' : ''}}
    </span>`;
}}
function renderModels() {{
  byId('model-list').innerHTML = state.models.slice(0, 28).map((model) =>
    `<li><strong>${{escapeHtml(model.id)}}</strong><span class="meta">${{escapeHtml(model.name)}}</span></li>`
  ).join('');
}}
function renderRelationshipModes() {{
  byId('relationship-mode').innerHTML = state.defaults.relationshipModes.map(([value, label]) =>
    `<option value="${{escapeHtml(value)}}">${{escapeHtml(label)}}</option>`
  ).join('');
}}
function renderPlayers(names = null, lockedNames = false) {{
  const count = Number(byId('player-count').value || 4);
  const container = byId('players');
  container.innerHTML = '';
  for (let slot = 1; slot <= 4; slot++) {{
    const defaultName = names?.[slot - 1] || state.defaults.players[slot - 1] || `Player ${{slot}}`;
    const firstModel = state.models[slot - 1] || state.models[0] || {{}};
    const provider = firstModel.provider || providers[0] || '';
    const modelOptions = (modelsByProvider[provider] || []).map((model) =>
      `<option value="${{escapeHtml(model.id)}}">${{escapeHtml(modelLabel(model))}}</option>`
    ).join('');
    const providerOptions = providers.map((item) =>
      `<option value="${{escapeHtml(item)}}" ${{item === provider ? 'selected' : ''}}>${{escapeHtml(item)}}</option>`
    ).join('');
    const hidden = slot > count ? ' hidden' : '';
    container.insertAdjacentHTML('beforeend', `
      <div class="player-card${{hidden}}" data-player-card="${{slot}}">
        <div class="player-head"><strong>P${{slot}}</strong><span>${{escapeHtml(state.defaults.colors[slot - 1] || '')}} · ${{escapeHtml(state.defaults.genders[slot] || '')}}</span></div>
        <label>שם<input data-player-name="${{slot}}" value="${{escapeHtml(defaultName)}}" maxlength="32" ${{lockedNames ? 'readonly' : ''}}></label>
        <label>Provider<select data-provider="${{slot}}">${{providerOptions}}</select></label>
        <label>Model<select data-model="${{slot}}">${{modelOptions}}</select></label>
        <label>Manual model id<input data-manual-model="${{slot}}" placeholder="anthropic/claude-sonnet-4.5"></label>
      </div>
    `);
  }}
  for (let slot = 1; slot <= 4; slot++) {{
    const select = document.querySelector(`[data-provider="${{slot}}"]`);
    if (!select) continue;
    select.addEventListener('change', () => {{
      const modelSelect = document.querySelector(`[data-model="${{slot}}"]`);
      modelSelect.innerHTML = (modelsByProvider[select.value] || []).map((model) =>
        `<option value="${{escapeHtml(model.id)}}">${{escapeHtml(modelLabel(model))}}</option>`
      ).join('');
    }});
  }}
}}
function setSelectById(id, value) {{
  if (value === undefined || value === null || value === '') return false;
  const select = byId(id);
  if (!select) return false;
  const stringValue = String(value);
  if (![...select.options].some((option) => option.value === stringValue)) return false;
  select.value = stringValue;
  return true;
}}
function setValueById(id, value) {{
  if (value === undefined || value === null || value === '') return false;
  const input = byId(id);
  if (!input) return false;
  input.value = String(value);
  return true;
}}
function restorePlayerModels(players) {{
  (players || []).slice(0, 4).forEach((player, index) => {{
    const slot = index + 1;
    const llm = player.llm || {{}};
    const provider = llm.model_provider || '';
    const modelName = llm.model_name || '';
    const providerSelect = document.querySelector(`[data-provider="${{slot}}"]`);
    const modelSelect = document.querySelector(`[data-model="${{slot}}"]`);
    const manualInput = document.querySelector(`[data-manual-model="${{slot}}"]`);
    if (providerSelect && provider && [...providerSelect.options].some((option) => option.value === provider)) {{
      providerSelect.value = provider;
      modelSelect.innerHTML = (modelsByProvider[provider] || []).map((model) =>
        `<option value="${{escapeHtml(model.id)}}">${{escapeHtml(modelLabel(model))}}</option>`
      ).join('');
    }}
    if (modelSelect && modelName && [...modelSelect.options].some((option) => option.value === modelName)) {{
      modelSelect.value = modelName;
      if (manualInput) manualInput.value = '';
    }} else if (manualInput && modelName) {{
      manualInput.value = modelName;
    }}
  }});
}}
function applyRestoredRunSettings(settings) {{
  if (!settings) return [];
  const restored = [];
  const reactions = settings.reactions || {{}};
  const tts = settings.tts || {{}};
  if (setSelectById('chat-language', settings.chat_language)) restored.push('language');
  if (setSelectById('relationship-mode', settings.relationship_context_mode)) restored.push('relationship');
  if (setSelectById('reaction-mode', reactions.mode)) restored.push('reactions');
  if (setValueById('reaction-batch-size', reactions.batch_size)) restored.push('batch size');
  if (setValueById('victory-points', settings.victory_points)) restored.push('victory points');
  if (setValueById('random-seed', settings.random_seed)) restored.push('seed');
  if (setValueById('game-context', settings.game_context)) restored.push('context');
  if (setValueById('config-path', settings.config_path)) restored.push('config');
  setSelectById('tts-provider', tts.provider);
  if (settings.no_llm) byId('no-llm').checked = true;
  restorePlayerModels(settings.players || []);
  if ((settings.players || []).some((player) => player.llm && player.llm.model_name)) restored.push('models');
  return restored;
}}
function refreshPlayerVisibility() {{
  const count = Number(byId('player-count').value || 4);
  document.querySelectorAll('[data-player-card]').forEach((card) => {{
    card.classList.toggle('hidden', Number(card.dataset.playerCard) > count);
  }});
}}
function renderSessionSelect() {{
  const options = state.sessions.map((session) =>
    `<option value="${{escapeHtml(session.name)}}">${{escapeHtml(session.name)}} - ${{escapeHtml((session.players || []).join(', '))}}</option>`
  ).join('');
  byId('resume-session').innerHTML = '<option value="">בחר סשן</option>' + options;
}}
function renderSessionList() {{
  const query = byId('session-search').value.trim().toLowerCase();
  const sessions = state.sessions.filter((session) => {{
    const haystack = `${{session.name}} ${{(session.players || []).join(' ')}} ${{session.mode || ''}}`.toLowerCase();
    return !query || haystack.includes(query);
  }});
  byId('session-list').innerHTML = sessions.map((session) =>
    `<button class="session-row ${{selectedReplaySession === session.name ? 'active' : ''}}" data-session="${{escapeHtml(session.name)}}" type="button">${{sessionLine(session)}}</button>`
  ).join('') || '<div class="preview-empty">לא נמצאו סשנים מתאימים.</div>';
  document.querySelectorAll('[data-session]').forEach((button) => {{
    button.addEventListener('click', () => openPreview(button.dataset.session));
  }});
}}
async function refreshSessions() {{
  const response = await fetch('/api/sessions', {{ cache: 'no-store' }});
  const payload = await response.json();
  state.sessions = payload.sessions || [];
  renderSessionSelect();
  renderSessionList();
}}
async function openPreview(sessionName) {{
  selectedReplaySession = sessionName;
  setErrors([]);
  const response = await fetch(`/api/session?session=${{encodeURIComponent(sessionName)}}`, {{ cache: 'no-store' }});
  const preview = await response.json();
  if (!response.ok) {{
    setErrors([preview.error || 'לא ניתן לטעון את הסשן']);
    return;
  }}
  byId('session-library').classList.add('hidden');
  byId('session-preview').classList.remove('hidden');
  byId('session-preview').innerHTML = `
    <button class="link-button" type="button" id="back-to-library">חזרה לספריה ובחירת סשן אחר</button>
    <button class="link-button" type="button" id="preview-back-home">Back to main screen</button>
    <div style="height:10px"></div>
    <div class="preview-title">${{escapeHtml(preview.name)}}</div>
    <p class="meta">${{escapeHtml((preview.players || []).join(', ') || 'ללא שחקנים מזוהים')}}</p>
    <div class="chips">
      <span class="chip">${{preview.response_count || 0}} responses</span>
      <span class="chip">${{(preview.markers || []).length}} markers</span>
      <span class="chip">${{escapeHtml(preview.mode || 'recorded')}}</span>
    </div>
    <div style="height:16px"></div>
    <div class="panel" style="box-shadow:none">
      <h3>Preview</h3>
      <p class="meta">הסשן ייפתח בלוח המשחק הרגיל עם יכולת צפייה וניתוח החלטות. אפשר לחזור לכאן לפני ההפעלה ולבחור סשן אחר.</p>
      <label>Marker לצפייה חלקית
        <select id="watch-marker">
          <option value="">כל הסשן</option>
          ${{(preview.markers || []).map((marker) => `<option value="${{escapeHtml(marker.value)}}">${{escapeHtml(marker.label || marker.value)}}</option>`).join('')}}
        </select>
      </label>
    </div>
  `;
  byId('back-to-library').addEventListener('click', () => {{
    byId('session-preview').classList.add('hidden');
    byId('session-library').classList.remove('hidden');
    renderSessionList();
  }});
  byId('preview-back-home').addEventListener('click', () => setView('run'));
}}
async function loadResumeSession() {{
  const sessionName = byId('resume-session').value;
  const status = byId('resume-status');
  byId('resume-marker').innerHTML = '';
  if (!sessionName) {{
    status.textContent = 'בחר סשן כדי לטעון שחקנים ונקודות עצירה.';
    renderPlayers(null, false);
    return;
  }}
  status.textContent = 'טוען סשן...';
  const response = await fetch(`/api/session?session=${{encodeURIComponent(sessionName)}}`, {{ cache: 'no-store' }});
  const preview = await response.json();
  if (!response.ok) {{
    status.textContent = preview.error || 'לא ניתן לטעון את הסשן.';
    return;
  }}
  const names = (preview.players || []).slice(0, 4);
  byId('player-count').value = String(Math.min(4, Math.max(2, names.length || 4)));
  renderPlayers(names, true);
  const restored = applyRestoredRunSettings(preview.settings);
  byId('resume-marker').innerHTML = '<option value="">בחר marker</option>' + (preview.markers || []).map((marker) =>
    `<option value="${{escapeHtml(marker.value)}}">${{escapeHtml(marker.label || marker.value)}}</option>`
  ).join('');
  status.textContent = names.length
    ? `שחקנים נעולים מהסשן: ${{names.join(', ')}}. אפשר לשנות מודלים בלבד.`
    : 'לא נמצאו שחקנים בסשן; אפשר לבחור סשן אחר.';
}}
function setView(next) {{
  view = next;
  byId('nav-run').classList.toggle('active', next === 'run');
  byId('nav-replay').classList.toggle('active', next === 'replay');
  byId('run-view').classList.toggle('hidden', next !== 'run');
  byId('replay-view').classList.toggle('hidden', next !== 'replay');
  byId('page-title').textContent = next === 'run' ? 'הרצת משחק' : 'צפייה וניתוח סשן';
  byId('page-subtitle').textContent = next === 'run'
    ? 'בחר משחק חדש או המשך מסשן מוקלט, הזן מפתחות, וקבע מודלים לשחקנים.'
    : 'בחר סשן כלשהו מתוך הספריה, פתח preview, וצפה בו עם ניתוח החלטות.';
  setErrors([]);
}}
function setRunMode(next) {{
  runMode = next;
  byId('new-game-tab').classList.toggle('active', next === 'new_game');
  byId('resume-tab').classList.toggle('active', next === 'resume_session');
  byId('resume-panel').classList.toggle('hidden', next !== 'resume_session');
  byId('replay-skip-wrap').classList.toggle('hidden', next !== 'resume_session');
  byId('replay-speak-wrap').classList.toggle('hidden', next !== 'resume_session');
  if (next === 'new_game') renderPlayers(null, false);
  if (next === 'resume_session') loadResumeSession();
}}
function refreshResumePointMode() {{
  const value = byId('resume-point-mode').value;
  byId('resume-marker-label').classList.toggle('hidden', !['stop_before', 'through'].includes(value));
  byId('resume-max-label').classList.toggle('hidden', value !== 'max');
}}
function collectCommonFields(runModeValue) {{
  const form = new FormData();
  form.set('run_mode', runModeValue);
  form.set('config_path', byId('config-path').value.trim());
  form.set('openrouter_api_key', byId('openrouter-key').value.trim());
  form.set('gemini_api_key', byId('gemini-key').value.trim());
  form.set('tts_provider', runModeValue === 'watch_replay' || runModeValue === 'analyse_game' ? 'off' : byId('tts-provider').value);
  form.set('gemini_tts_model', state.defaults.geminiTtsModels[0] || 'gemini-2.5-flash-preview-tts');
  form.set('gemini_tts_voice', 'Kore');
  form.set('chat_language', byId('chat-language').value);
  form.set('relationship_context_mode', byId('relationship-mode').value);
  form.set('reaction_mode', byId('reaction-mode').value);
  form.set('reaction_batch_size', byId('reaction-batch-size').value.trim());
  form.set('victory_points', byId('victory-points').value || '5');
  form.set('random_seed', byId('random-seed').value.trim());
  form.set('game_context', byId('game-context').value.trim());
  form.set('player_count', byId('player-count').value);
  if (byId('no-llm').checked) form.set('no_llm', 'on');
  for (let slot = 1; slot <= 4; slot++) {{
    const name = document.querySelector(`[data-player-name="${{slot}}"]`)?.value || '';
    const provider = document.querySelector(`[data-provider="${{slot}}"]`)?.value || '';
    const model = document.querySelector(`[data-model="${{slot}}"]`)?.value || '';
    const manual = document.querySelector(`[data-manual-model="${{slot}}"]`)?.value || '';
    form.set(`player_${{slot}}`, name);
    form.set(`provider_${{slot}}`, provider);
    form.set(`model_${{slot}}`, model);
    form.set(`manual_model_${{slot}}`, manual);
  }}
  return form;
}}
async function submitForm(form) {{
  setErrors([]);
  const response = await fetch('/start', {{ method: 'POST', body: new URLSearchParams(form) }});
  const contentType = response.headers.get('content-type') || '';
  if (!response.ok) {{
    if (contentType.includes('application/json')) {{
      const payload = await response.json();
      setErrors(payload.errors || [payload.error || 'ההפעלה נכשלה']);
    }} else {{
      setErrors(['ההפעלה נכשלה']);
    }}
    return;
  }}
  const html = await response.text();
  document.open();
  document.write(html);
  document.close();
}}
function startRun() {{
  const form = collectCommonFields(runMode);
  if (runMode === 'resume_session') {{
    form.set('replay_session', byId('resume-session').value);
    const pointMode = byId('resume-point-mode').value;
    if (pointMode === 'stop_before') form.set('replay_stop_before', byId('resume-marker').value);
    if (pointMode === 'through') form.set('replay_through', byId('resume-marker').value);
    if (pointMode === 'max') form.set('replay_max_decisions', byId('resume-max').value);
    if (byId('replay-skip-chat').checked) form.set('replay_skip_chat', 'on');
    if (byId('replay-speak').checked) form.set('replay_speak', 'on');
  }}
  submitForm(form);
}}
function startReplay() {{
  const sessionName = selectedReplaySession;
  if (!sessionName) {{
    setErrors(['בחר סשן מהרשימה לפני פתיחת צפייה וניתוח.']);
    return;
  }}
  const mode = byId('replay-mode').value;
  const form = collectCommonFields(mode);
  const speak = byId('analysis-replay-speak').checked;
  form.set('replay_session', sessionName);
  form.set('replay_delay', byId('replay-delay').value || '2.5');
  form.set('replay_text_lead', byId('replay-text-lead').value || '0.25');
  form.set('tts_provider', speak ? 'gemini' : 'off');
  form.set('gemini_api_key', byId('replay-gemini-key').value.trim() || byId('gemini-key').value.trim());
  if (speak) form.set('replay_speak', 'on');
  const marker = byId('watch-marker')?.value || '';
  if (marker) form.set('replay_through', marker);
  submitForm(form);
}}
function init() {{
  byId('env-pill').textContent = `ENV: OpenRouter ${{state.env.openrouter ? 'קיים' : 'חסר'}} · Gemini ${{state.env.gemini ? 'קיים' : 'חסר'}}`;
  byId('openrouter-key').placeholder = state.env.openrouter ? 'ENV key available' : 'sk-or-...';
  byId('gemini-key').placeholder = state.env.gemini ? 'ENV key available' : '';
  byId('replay-gemini-key').placeholder = state.env.gemini ? 'ENV key available' : '';
  renderModels();
  renderRelationshipModes();
  renderPlayers();
  renderSessionSelect();
  renderSessionList();
  byId('replay-skip-wrap').classList.add('hidden');
  byId('replay-speak-wrap').classList.add('hidden');
  byId('nav-run').addEventListener('click', () => setView('run'));
  byId('nav-replay').addEventListener('click', () => setView('replay'));
  byId('replay-back-home').addEventListener('click', () => setView('run'));
  byId('new-game-tab').addEventListener('click', () => setRunMode('new_game'));
  byId('resume-tab').addEventListener('click', () => setRunMode('resume_session'));
  byId('player-count').addEventListener('change', refreshPlayerVisibility);
  byId('resume-session').addEventListener('change', loadResumeSession);
  byId('resume-point-mode').addEventListener('change', refreshResumePointMode);
  byId('session-search').addEventListener('input', renderSessionList);
  byId('clear-session-search').addEventListener('click', () => {{ byId('session-search').value = ''; renderSessionList(); }});
  byId('refresh-sessions').addEventListener('click', refreshSessions);
  byId('start-run').addEventListener('click', startRun);
  byId('start-replay').addEventListener('click', startReplay);
  refreshResumePointMode();
}}
init();
</script>
</body>
</html>""".encode("utf-8")


def collect_settings(port: int = 5000, key_mode: str = "env") -> Dict[str, Any]:
    settings: Dict[str, Any] = {}
    ready = threading.Event()
    models = fetch_openrouter_models(os.environ.get("OPENROUTER_API_KEY", ""))
    suitable_by_id = {model["id"]: model for model in models if is_suitable_openrouter_model(model)}
    valid_model_ids = set(suitable_by_id)
    valid_providers = {model["provider"] for model in models}
    use_env_keys = key_mode == "env"

    class ReusableThreadingHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True

    class BetterUxHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_GET(self):
            parsed_url = urlparse(self.path)
            if parsed_url.path == "/healthz":
                _json_response(self, {"ok": True})
                return
            if parsed_url.path == "/api/sessions":
                _json_response(self, {"sessions": list_sessions()})
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
            if parsed_url.path in {"/replay-markers", "/session-players"}:
                session_ref = parse_qs(parsed_url.query).get("session", [""])[0].strip()
                if not session_ref:
                    _json_response(self, {"markers": [], "players": []})
                    return
                try:
                    session_dir = resolve_session_path(session_ref)
                    if parsed_url.path == "/replay-markers":
                        _json_response(self, {"markers": list_replay_marker_options(session_dir)})
                    else:
                        _json_response(self, {"players": _infer_session_player_names(session_dir)})
                except Exception as exc:
                    _json_response(self, {"error": str(exc), "markers": [], "players": []}, status=400)
                return
            _html_response(self, render_spa(models, key_mode))

        def do_POST(self):
            if self.path != "/start":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw_fields = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            fields = {key: values[0].strip() for key, values in raw_fields.items()}
            errors: List[str] = []

            run_mode = fields.get("run_mode", "new_game")
            valid_run_modes = {"new_game", "resume_session", "watch_replay", "analyse_game"}
            if run_mode not in valid_run_modes:
                errors.append("Choose a valid run mode.")
            live_mode = run_mode in {"new_game", "resume_session"}
            no_llm = _as_bool_field(fields, "no_llm")
            replay_speak = _as_bool_field(fields, "replay_speak")

            api_key = fields.get("openrouter_api_key") or (
                os.environ.get("OPENROUTER_API_KEY", "") if use_env_keys else ""
            )
            if live_mode and not no_llm and not api_key:
                errors.append("Enter an OpenRouter API key or set OPENROUTER_API_KEY.")

            replay_session = fields.get("replay_session", "")
            if run_mode != "new_game" and not replay_session:
                errors.append("Choose a recorded session.")
            if fields.get("replay_through") and fields.get("replay_stop_before"):
                errors.append("Use either replay-through or replay-stop-before, not both.")

            replay_session_path_for_validation = None
            locked_player_names: List[str] = []
            if run_mode != "new_game" and replay_session:
                try:
                    replay_session_path_for_validation = resolve_session_path(replay_session)
                    locked_player_names = _infer_session_player_names(replay_session_path_for_validation)
                except FileNotFoundError as exc:
                    errors.append(str(exc))
            if replay_session_path_for_validation and (fields.get("replay_through") or fields.get("replay_stop_before")):
                try:
                    load_replay_decision_chain(
                        replay_session_path_for_validation,
                        replay_through=fields.get("replay_through") or None,
                        replay_stop_before=fields.get("replay_stop_before") or None,
                    )
                except (TypeError, ValueError) as exc:
                    errors.append(
                        f"{exc}. Choose one of the suggested action markers; reaction-only table talk is not replayable as a marker."
                    )
            if (
                run_mode == "resume_session"
                and replay_session_path_for_validation
                and not fields.get("replay_through")
                and not fields.get("replay_stop_before")
            ):
                try:
                    decisions_for_resume = load_replay_decision_chain(replay_session_path_for_validation)
                except Exception:
                    decisions_for_resume = []
                minimum_actions = _minimum_recorded_actions_for_state(
                    _load_session_final_state(replay_session_path_for_validation)
                )
                if minimum_actions and len(decisions_for_resume) < minimum_actions:
                    errors.append(
                        "This session cannot be resumed by fast replay: "
                        f"it has {len(decisions_for_resume)} recorded action(s), but the saved board "
                        f"already contains at least {minimum_actions} placements. Choose a fuller session "
                        "or use a replay marker for a partial replay."
                    )

            if fields.get("config_path") and not Path(fields["config_path"]).exists():
                errors.append("Config file was not found.")

            player_count = _parse_optional_int(fields.get("player_count", "4"), errors, "Player count") or 4
            if run_mode != "new_game" and locked_player_names:
                player_count = min(4, max(2, len(locked_player_names)))
                for index, name in enumerate(locked_player_names[:player_count]):
                    fields[f"player_{index + 1}"] = name
            if player_count not in (2, 3, 4):
                errors.append("Choose 2, 3, or 4 players.")
                player_count = 4
            fields["player_count"] = str(player_count)

            replay_max_decisions = _parse_optional_int(
                fields.get("replay_max_decisions", ""), errors, "Replay max decisions"
            )
            replay_delay = _parse_float(fields.get("replay_delay", "2.5"), 2.5, errors, "Replay delay")
            replay_text_lead = _parse_float(
                fields.get("replay_text_lead", "0.25"), 0.25, errors, "Replay text lead"
            )

            reaction_mode = fields.get("reaction_mode", "async")
            if reaction_mode not in {"default", "off", "sync", "async"}:
                errors.append("Choose a valid reaction mode.")
            relationship_context_mode = fields.get("relationship_context_mode", "legacy")
            valid_relationship_modes = {value for value, _label in RELATIONSHIP_CONTEXT_MODES}
            if relationship_context_mode not in valid_relationship_modes:
                errors.append("Choose a valid relationship context mode.")
                relationship_context_mode = "legacy"
            reaction_batch_size = _parse_optional_int(
                fields.get("reaction_batch_size", ""), errors, "Reaction batch size"
            )
            victory_points = _parse_optional_int(fields.get("victory_points", "5"), errors, "Victory points") or 5
            game_context = fields.get("game_context", "").strip()
            if len(game_context) > 4000:
                errors.append("Additional game context must be 4000 characters or less.")
            random_seed = 0
            if fields.get("random_seed"):
                try:
                    random_seed = int(fields["random_seed"])
                except ValueError:
                    errors.append("Random seed must be a whole number.")

            tts_provider = fields.get("tts_provider", "gemini")
            if tts_provider not in {"off", "gemini", "elevenlabs"}:
                errors.append("Choose a valid voice provider.")
            gemini_api_key = fields.get("gemini_api_key") or (
                os.environ.get("GEMINI_API_KEY", "") if use_env_keys else ""
            )
            needs_voice = live_mode or replay_speak
            if tts_provider == "gemini" and needs_voice and not gemini_api_key:
                errors.append("Enter a Gemini API key for Gemini TTS or set GEMINI_API_KEY.")

            slot_llms: List[Dict[str, str]] = []
            player_configs: List[Dict[str, Any]] = []
            seen_names = set()
            for index in range(player_count):
                slot = index + 1
                name = fields.get(f"player_{slot}") or DEFAULT_PLAYER_NAMES[index]
                model_id = fields.get(f"manual_model_{slot}") or fields.get(f"model_{slot}") or ""
                provider = fields.get(f"provider_{slot}") or provider_from_model_id(model_id)
                if run_mode == "new_game":
                    if not name:
                        errors.append(f"P{slot} needs a name.")
                    if name.lower() in seen_names:
                        errors.append("Player names must be unique.")
                    seen_names.add(name.lower())
                if provider and provider not in valid_providers:
                    errors.append(f"Unknown provider for P{slot}: {provider}")
                if live_mode and not no_llm:
                    if not model_id:
                        errors.append(f"P{slot} needs a model.")
                    elif model_id not in valid_model_ids:
                        errors.append(
                            f"Model for P{slot} is not suitable. Choose a listed model with tools, "
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
                "player_configs": player_configs if run_mode == "new_game" else [],
                "slot_llms": slot_llms,
                "chat_language": normalize_chat_language(fields.get("chat_language") or "hebrew"),
                "relationship_context_mode": relationship_context_mode,
                "no_llm": no_llm,
                "reaction_mode": reaction_mode,
                "reaction_batch_size": reaction_batch_size,
                "victory_points": victory_points,
                "game_context": game_context,
                "random_seed": random_seed,
                "config_path": fields.get("config_path") or None,
                "replay_session": replay_session or None,
                "replay_max_decisions": replay_max_decisions,
                "replay_through": fields.get("replay_through") or None,
                "replay_stop_before": fields.get("replay_stop_before") or None,
                "replay_skip_chat": _as_bool_field(fields, "replay_skip_chat"),
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
            starting_players = player_configs if run_mode == "new_game" else [
                {"name": replay_session or "recorded session", "llm": {"model_name": run_mode}}
            ]
            _html_response(self, render_starting_page(starting_players, run_mode))
            ready.set()

    bind_host = os.environ.get("PYCATAN_BIND_HOST", "127.0.0.1")
    public_host = os.environ.get("PYCATAN_PUBLIC_HOST", "localhost")
    server = ReusableThreadingHTTPServer((bind_host, port), BetterUxHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://{public_host}:{port}/"
    print(f"[SETUP] Better UX setup page: {url}")
    if os.environ.get("PYCATAN_NO_BROWSER", "").lower() not in {"1", "true", "yes", "on"}:
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"[SETUP] Could not open browser automatically: {exc}")
    print("[SETUP] Waiting for Better UX settings...")
    try:
        while not ready.wait(timeout=0.25):
            pass
    finally:
        server.shutdown()
        server.server_close()
    return settings


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Play Catan with a better single-page web UX")
    parser.add_argument("--config", type=str, help="Optional AI config YAML")
    parser.add_argument("--port", type=int, default=5000, help="Setup and game web port")
    parser.add_argument("--use-env-keys", action="store_true", help="Use ENV/.env keys when browser fields are blank")
    parser.add_argument("--ask-api-keys", "--ask-keys", action="store_true", help="Require keys typed into the browser form")
    args = parser.parse_args()

    if args.use_env_keys and args.ask_api_keys:
        parser.error("--use-env-keys and --ask-api-keys cannot be used together")

    load_env_file()
    settings = collect_settings(port=args.port, key_mode=("ask" if args.ask_api_keys else "env"))
    ai_config = load_ai_config(settings.get("config_path") or args.config)
    ai_config.llm.provider = "openrouter"
    ai_config.llm.api_key_env_var = "OPENROUTER_API_KEY"
    ai_config.llm.enable_streaming = True
    ai_config.agent.chat_language = settings["chat_language"]
    ai_config.agent.relationship_context_mode = settings["relationship_context_mode"]
    _apply_reaction_settings(ai_config, settings)

    replay_session_path = resolve_session_path(settings["replay_session"]) if settings["replay_session"] else None
    watch_mode = settings["run_mode"] in {"watch_replay", "analyse_game"}
    analyse_mode = settings["run_mode"] == "analyse_game"
    if watch_mode and not replay_session_path:
        parser.error("watch/analyse mode requires a replay session")

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
        replay_decision_list = load_replay_decision_chain(
            replay_session_path,
            max_decisions=settings["replay_max_decisions"],
            replay_through=settings["replay_through"],
            replay_stop_before=settings["replay_stop_before"],
        )
        replay_decisions_by_player = group_replay_decisions(replay_decision_list)
        player_names = _infer_session_player_names(replay_session_path) or infer_players_from_decisions(replay_decision_list)
        player_configs = _player_configs_for_replay(player_names, settings["slot_llms"])
        print(f"[REPLAY] Source: {replay_session_path}")
        print(f"[REPLAY] Loaded {len(replay_decision_list)} parsed decisions")
    else:
        player_configs = settings["player_configs"]

    if not player_configs:
        parser.error("No players could be inferred for this run")

    if not settings["no_llm"]:
        ai_config.llm.model_name = player_configs[0]["llm"]["model_name"]
    send_to_llm = (not settings["no_llm"]) and not watch_mode
    manual_actions = False

    print(f"[MODE] LLM: {'ON' if send_to_llm else 'OFF'} | Actions: Auto")
    print(f"[CONFIG] Victory points to win: {settings['victory_points']}")
    print(f"[CONFIG] Relationship context: {settings['relationship_context_mode']}")
    print("[CONFIG] Better UX + OpenRouter per-agent models")
    game_manager, ai_manager, web_viz = create_game(
        player_configs,
        send_to_llm=send_to_llm,
        manual_actions=manual_actions,
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
    write_run_settings_metadata(
        ai_manager.get_session_path(),
        settings,
        player_configs,
        source="play_with_better_ux",
    )

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
            mode=(
                "analyse_game_visual_playback"
                if analyse_mode
                else "watch_replay_visual_playback"
                if watch_mode
                else "fast_action_replay_then_live_ai"
            ),
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
        )
    else:
        run_game(game_manager, ai_manager, web_viz)


if __name__ == "__main__":
    main()
