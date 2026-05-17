#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone browser replay viewer for recorded PyCatan AI sessions.

This entry point intentionally does not import or run the live game manager,
AI users, or server-side TTS providers. It reads a session folder, builds a
response timeline, and lets the browser own replay playback and audio.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import os
import re
import sys
import threading
import time
import wave
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = REPO_ROOT / "examples" / "ai_testing" / "my_games"
MANIFEST_NAME = "replay_viewer_manifest.json"
TRUE_VALUES = {"1", "true", "yes", "on"}


def _read_json(path: Path, fallback: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _safe_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", text).strip("_") or "event"


def _parse_time(value: Any) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return datetime.min


def _wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as wav_file:
            frame_rate = wav_file.getframerate() or 1
            return wav_file.getnframes() / float(frame_rate)
    except Exception:
        return 0.0


def resolve_session_path(session_ref: str) -> Path:
    raw = Path(session_ref)
    candidates = [
        raw,
        REPO_ROOT / raw,
        LOGS_DIR / session_ref,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
    raise FileNotFoundError(f"Session folder not found: {session_ref}")


def list_sessions(logs_dir: Path = LOGS_DIR) -> List[Dict[str, Any]]:
    if not logs_dir.exists():
        return []

    sessions: List[Dict[str, Any]] = []
    for session_dir in logs_dir.iterdir():
        if not session_dir.is_dir() or not session_dir.name.startswith("session_"):
            continue
        response_count = sum(1 for _ in session_dir.glob("*/responses/response_*.json"))
        if response_count == 0 and not (session_dir / "session_metadata.json").exists():
            continue
        metadata = _read_json(session_dir / "session_metadata.json", {}) or {}
        summary = _read_json(session_dir / "session_summary.json", {}) or {}
        artifact = _read_json(session_dir / ".replay_viewer" / MANIFEST_NAME, {}) or {}
        stats = artifact.get("stats") if isinstance(artifact.get("stats"), dict) else {}
        try:
            modified_at = datetime.fromtimestamp(session_dir.stat().st_mtime).isoformat(timespec="seconds")
        except Exception:
            modified_at = ""
        sessions.append({
            "name": session_dir.name,
            "path": str(session_dir.resolve()),
            "start_time": metadata.get("start_time") or summary.get("start_time") or "",
            "end_time": summary.get("end_time") or "",
            "modified_at": modified_at,
            "responses": response_count,
            "events": stats.get("events"),
            "actions": stats.get("actions"),
            "speech": stats.get("speech"),
            "audio": stats.get("audio"),
            "has_manifest": bool(stats),
        })

    sessions.sort(key=lambda item: item.get("start_time") or item.get("modified_at") or item.get("name"), reverse=True)
    return sessions


def _players_from_metadata(session_dir: Path) -> List[Dict[str, Any]]:
    metadata = _read_json(session_dir / "session_metadata.json", {}) or {}
    players = (((metadata.get("run_settings") or {}).get("players")) or [])
    if isinstance(players, list) and players:
        return [player for player in players if isinstance(player, dict)]

    inferred = []
    for child in session_dir.iterdir():
        if child.is_dir() and (child / "responses").exists():
            inferred.append({"slot": len(inferred) + 1, "name": child.name})
    return inferred


def _tts_settings(session_dir: Path) -> Dict[str, str]:
    metadata = _read_json(session_dir / "session_metadata.json", {}) or {}
    tts = (((metadata.get("run_settings") or {}).get("tts")) or {})
    chat_language = ((metadata.get("run_settings") or {}).get("chat_language") or "hebrew")
    prompt_template = (
        os.environ.get("GEMINI_TTS_PROMPT_TEMPLATE")
        or (
            "[casual, conversational, Israeli Hebrew pronunciation] {text}"
            if chat_language == "hebrew"
            else "[casual, conversational, natural English speech] {text}"
        )
    )
    return {
        "provider": str(tts.get("provider") or "gemini").strip().lower(),
        "gemini_model": str(tts.get("gemini_model") or os.environ.get("GEMINI_TTS_MODEL_ID") or "").strip(),
        "gemini_voice": str(tts.get("gemini_voice") or os.environ.get("GEMINI_TTS_VOICE_NAME") or "Kore").strip(),
        "gemini_prompt_template": prompt_template,
    }


def _candidate_speaker_keys(player_name: str, players: List[Dict[str, Any]]) -> List[str]:
    keys = [player_name]
    for idx, player in enumerate(players, start=1):
        if str(player.get("name") or "") == player_name:
            slot = player.get("slot") or idx
            keys.extend([f"player_{slot}", f"player_{idx}", str(slot)])
            break
    seen = set()
    return [key for key in keys if key and not (key in seen or seen.add(key))]


def _gemini_audio_path(
    session_dir: Path,
    player_name: str,
    message: str,
    players: List[Dict[str, Any]],
    tts: Dict[str, str],
) -> Optional[Path]:
    cache_dir = session_dir / "tts_cache" / "gemini"
    if not cache_dir.exists():
        return None

    models = [
        tts.get("gemini_model") or "",
        "gemini-2.5-flash-preview-tts",
        "gemini-3.1-flash-tts-preview",
    ]
    voices = [tts.get("gemini_voice") or "Kore", "Kore"]
    prompt_template = tts.get("gemini_prompt_template") or "{text}"

    for speaker_key in _candidate_speaker_keys(player_name, players):
        prompt = prompt_template.format(player=speaker_key, text=message.replace('"', "'"))
        for model in dict.fromkeys([item for item in models if item]):
            for voice in dict.fromkeys([item for item in voices if item]):
                cache_key = "\n".join(["gemini", model, voice, prompt])
                digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
                candidate = cache_dir / f"{digest}.wav"
                if candidate.exists():
                    return candidate.resolve()
    return None


def _load_responses(session_dir: Path) -> List[Dict[str, Any]]:
    responses: List[Dict[str, Any]] = []
    for path in session_dir.glob("*/responses/response_*.json"):
        if "intermediate" in path.parts:
            continue
        data = _read_json(path, None)
        if not isinstance(data, dict):
            continue
        parsed = data.get("parsed") if isinstance(data.get("parsed"), dict) else {}
        if data.get("type") and data.get("type") != "final":
            continue
        responses.append({
            "source_file": str(path.relative_to(session_dir)),
            "absolute_source_file": str(path.resolve()),
            "player_name": data.get("player_name") or path.parent.parent.name,
            "request_number": data.get("request_number"),
            "timestamp": data.get("timestamp"),
            "raw_content": data.get("raw_content") or "",
            "parsed": parsed,
            "model": data.get("model"),
            "tokens": data.get("tokens") or {},
            "success": data.get("success", True),
            "latency_seconds": data.get("latency_seconds"),
            "error": data.get("error"),
        })

    responses.sort(key=lambda item: (_parse_time(item.get("timestamp")), str(item.get("player_name")), int(item.get("request_number") or 0)))
    return responses


def _normalize_chat_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _load_chat_messages(session_dir: Path) -> List[Dict[str, Any]]:
    chat = _read_json(session_dir / "chat_history.json", {}) or {}
    messages = chat.get("messages") if isinstance(chat, dict) else chat
    if not isinstance(messages, list):
        return []

    loaded: List[Dict[str, Any]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        text = _normalize_chat_text(message.get("message"))
        if not text:
            continue
        loaded.append({
            "chat_index": index,
            "timestamp": message.get("timestamp"),
            "player_name": message.get("from") or "Unknown",
            "to": message.get("to") or "all",
            "message": text,
        })
    return loaded


def _audio_paths_from_existing_replay_logs(session_dir: Path) -> Dict[str, Path]:
    """Recover response->audio links from previous derived replay logs, if present."""
    mapping: Dict[str, Path] = {}
    if not LOGS_DIR.exists():
        return mapping

    session_marker = f"{session_dir.name}{os.sep}tts_cache"
    for log_path in LOGS_DIR.glob("session_*/replay_speech_log.json"):
        log = _read_json(log_path, [])
        if not isinstance(log, list):
            continue
        for entry in log:
            if not isinstance(entry, dict):
                continue
            response_id = entry.get("response_id")
            audio_cache_path = entry.get("audio_cache_path")
            if not response_id or not audio_cache_path:
                continue
            audio_path = (REPO_ROOT / str(audio_cache_path)).resolve() if not Path(str(audio_cache_path)).is_absolute() else Path(str(audio_cache_path))
            try:
                audio_path.relative_to(session_dir.resolve())
            except ValueError:
                if session_marker not in str(audio_path):
                    continue
            if audio_path.exists():
                mapping.setdefault(str(response_id), audio_path)
    return mapping


def _resolve_audio_path(session_dir: Path, value: Any) -> Optional[Path]:
    if not value:
        return None
    raw = Path(str(value))
    candidates = [
        raw,
        session_dir / raw,
        REPO_ROOT / raw,
    ]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            continue
        if resolved.exists() and resolved.is_file():
            return resolved
    return None


def _audio_paths_from_manifest(session_dir: Path) -> Dict[str, Path]:
    """Load an explicit response_id->audio file map written by newer recordings."""
    mapping: Dict[str, Path] = {}
    manifest_paths = [
        session_dir / "replay_audio_manifest.json",
        session_dir / "audio_manifest.json",
        session_dir / ".replay_viewer" / "audio_manifest.json",
        session_dir / "replay_speech_log.json",
    ]
    for manifest_path in manifest_paths:
        manifest = _read_json(manifest_path)
        if not manifest:
            continue
        if isinstance(manifest, dict):
            entries = manifest.get("items") or manifest.get("events") or manifest.get("audio") or []
            if not entries:
                entries = [
                    {"response_id": response_id, "audio_path": audio_path}
                    for response_id, audio_path in manifest.items()
                    if isinstance(audio_path, str)
                ]
        elif isinstance(manifest, list):
            entries = manifest
        else:
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            response_id = entry.get("response_id")
            audio_value = (
                entry.get("audio_path")
                or entry.get("path")
                or entry.get("file")
                or entry.get("audio_cache_path")
            )
            audio_path = _resolve_audio_path(session_dir, audio_value)
            if response_id and audio_path:
                mapping.setdefault(str(response_id), audio_path)
    return mapping


def build_manifest(session_dir: Path, max_gap_seconds: float = 2.5) -> Dict[str, Any]:
    players = _players_from_metadata(session_dir)
    tts = _tts_settings(session_dir)
    responses = _load_responses(session_dir)
    chat_messages = _load_chat_messages(session_dir)
    explicit_audio_paths = _audio_paths_from_manifest(session_dir)
    logged_audio_paths = _audio_paths_from_existing_replay_logs(session_dir)
    events: List[Dict[str, Any]] = []
    audio_by_id: Dict[str, Path] = {}
    response_speech_keys = set()

    for index, response in enumerate(responses):
        parsed = response.get("parsed") or {}
        player_name = str(response.get("player_name") or "Unknown")
        request_number = response.get("request_number")
        response_id = f"{player_name}:{request_number}" if request_number is not None else f"{player_name}:{index}"
        action_type = parsed.get("action_type")
        message = str(parsed.get("say_outloud") or "").strip()
        if message:
            response_speech_keys.add((player_name, _normalize_chat_text(message)))
        audio_path = explicit_audio_paths.get(response_id) or logged_audio_paths.get(response_id)
        if not audio_path and message:
            audio_path = _gemini_audio_path(session_dir, player_name, message, players, tts)
        audio_duration = _wav_duration(audio_path) if audio_path else 0.0
        safe_event_id = _safe_id(f"{player_name}_{request_number or index}_{index}")
        if audio_path:
            audio_by_id[safe_event_id] = audio_path

        events.append({
            "index": index,
            "id": safe_event_id,
            "response_id": response_id,
            "player_name": player_name,
            "request_number": request_number,
            "timestamp": response.get("timestamp"),
            "source_file": response.get("source_file"),
            "absolute_source_file": response.get("absolute_source_file"),
            "kind": "action" if action_type else "speech" if message else "memory" if parsed.get("note_to_self") else "response",
            "action_type": action_type,
            "parameters": parsed.get("parameters") or {},
            "say_outloud": message,
            "note_to_self": parsed.get("note_to_self") or "",
            "internal_thinking": parsed.get("internal_thinking") or "",
            "has_action": bool(action_type),
            "has_speech": bool(message),
            "has_audio": bool(audio_path),
            "audio_url": f"/api/audio/{safe_event_id}" if audio_path else "",
            "audio_duration_seconds": audio_duration,
            "model": response.get("model"),
            "tokens": response.get("tokens") or {},
            "success": response.get("success", True),
            "latency_seconds": response.get("latency_seconds"),
            "error": response.get("error"),
            "raw_content": response.get("raw_content") or "",
            "_sort_time": _parse_time(response.get("timestamp")),
        })

    for chat in chat_messages:
        player_name = str(chat.get("player_name") or "Unknown")
        message = str(chat.get("message") or "").strip()
        if (player_name, _normalize_chat_text(message)) in response_speech_keys:
            continue
        chat_index = int(chat.get("chat_index") or 0)
        safe_event_id = _safe_id(f"chat_{player_name}_{chat_index}")
        events.append({
            "index": len(events),
            "id": safe_event_id,
            "response_id": f"chat:{chat_index}",
            "player_name": player_name,
            "request_number": None,
            "timestamp": chat.get("timestamp"),
            "source_file": "chat_history.json",
            "absolute_source_file": str((session_dir / "chat_history.json").resolve()),
            "kind": "chat",
            "action_type": None,
            "parameters": {},
            "say_outloud": message,
            "note_to_self": "",
            "internal_thinking": "",
            "chat_to": chat.get("to") or "all",
            "has_action": False,
            "has_speech": True,
            "has_audio": False,
            "audio_url": "",
            "audio_duration_seconds": 0.0,
            "model": None,
            "tokens": {},
            "success": True,
            "latency_seconds": None,
            "error": None,
            "raw_content": "",
            "_sort_time": _parse_time(chat.get("timestamp")),
        })

    events.sort(key=lambda item: (item.get("_sort_time") or datetime.min, str(item.get("player_name") or ""), str(item.get("response_id") or "")))
    for index, event in enumerate(events):
        event["index"] = index
        event.pop("_sort_time", None)

    for index, event in enumerate(events):
        if index < len(events) - 1:
            current_dt = _parse_time(event.get("timestamp"))
            next_dt = _parse_time(events[index + 1].get("timestamp"))
            real_gap = max(0.0, (next_dt - current_dt).total_seconds()) if current_dt != datetime.min and next_dt != datetime.min else max_gap_seconds
            timeline_gap = min(real_gap, max_gap_seconds) if max_gap_seconds >= 0 else real_gap
        else:
            real_gap = 0.0
            timeline_gap = 0.0
        event["real_gap_seconds"] = real_gap
        event["timeline_gap_seconds"] = timeline_gap
        event["planned_delay_to_next_seconds"] = timeline_gap + float(event.get("audio_duration_seconds") or 0.0)

    manifest = {
        "schema_version": 1,
        "session": {
            "name": session_dir.name,
            "path": str(session_dir),
            "metadata": _read_json(session_dir / "session_metadata.json", {}) or {},
            "summary": _read_json(session_dir / "session_summary.json", {}) or {},
        },
        "players": players,
        "settings": {
            "max_gap_seconds": max_gap_seconds,
            "tts": tts,
        },
        "stats": {
            "events": len(events),
            "actions": sum(1 for event in events if event.get("has_action")),
            "speech": sum(1 for event in events if event.get("has_speech")),
            "chat": sum(1 for event in events if event.get("kind") == "chat"),
            "audio": sum(1 for event in events if event.get("has_audio")),
        },
        "events": events,
    }
    manifest["_audio_by_id"] = audio_by_id
    return manifest


def public_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    clone = dict(manifest)
    clone.pop("_audio_by_id", None)
    return clone


def write_manifest_artifact(session_dir: Path, manifest: Dict[str, Any]) -> Path:
    artifact_dir = session_dir / ".replay_viewer"
    artifact_dir.mkdir(exist_ok=True)
    path = artifact_dir / MANIFEST_NAME
    path.write_text(
        json.dumps(public_manifest(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PyCatan Replay Viewer</title>
  <style>
    :root { --bg:#f4f6fb; --panel:#ffffff; --ink:#172033; --muted:#64748b; --brand:#4f6bed; --line:#d9e1f2; --good:#168a55; --warn:#b7791f; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: Inter, Segoe UI, Arial, sans-serif; color:var(--ink); background:var(--bg); }
    header { height:72px; display:flex; align-items:center; gap:16px; padding:0 20px; background:#172033; color:white; box-shadow:0 2px 12px rgba(0,0,0,.18); }
    h1 { font-size:18px; margin:0; white-space:nowrap; }
    .session-chooser { display:flex; align-items:center; gap:8px; min-width:360px; }
    .session-chooser select { width:260px; border:1px solid #334155; background:#0f172a; color:white; border-radius:7px; padding:9px 10px; font-weight:700; }
    .session-chooser button { background:#e7eefc; border-color:#e7eefc; }
    .transport { margin-left:auto; display:flex; align-items:center; gap:8px; min-width:520px; }
    button { border:1px solid var(--line); background:white; color:var(--ink); border-radius:7px; padding:9px 12px; font-weight:700; cursor:pointer; }
    button.primary { background:#58b46e; color:#06240f; border-color:#58b46e; }
    button:disabled { opacity:.5; cursor:default; }
    input[type=range] { flex:1; }
    .counter { font-weight:800; min-width:72px; text-align:center; }
    .context { color:#cbd5e1; min-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .timeline { display:flex; gap:8px; overflow:auto; padding:12px 16px; border-bottom:1px solid var(--line); background:white; }
    .dot { width:32px; height:32px; border-radius:7px; display:grid; place-items:center; font-weight:900; border:1px solid var(--line); background:#f8fafc; }
    .dot.action { border-color:#f4c542; background:#fff7d6; }
    .dot.speech { border-color:#8bc7ff; background:#e9f5ff; }
    .dot.chat { border-color:#64d4a0; background:#e8fff3; }
    .dot.memory { border-color:#b9a7ff; background:#f0edff; }
    .dot.active { outline:3px solid var(--brand); }
    .layout { display:grid; grid-template-columns:280px minmax(420px,1fr) 420px; gap:14px; padding:14px; min-height:calc(100vh - 130px); }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; min-height:0; }
    .panel h2 { font-size:15px; margin:0; padding:14px 16px; border-bottom:1px solid var(--line); background:#fbfcff; }
    .body { padding:14px 16px; overflow:auto; max-height:calc(100vh - 190px); }
    .player-filter { display:flex; flex-wrap:wrap; gap:8px; }
    .player-filter button.active { background:var(--brand); color:white; border-color:var(--brand); }
    .stat { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #edf1f8; color:var(--muted); }
    .board-placeholder { height:360px; border:1px dashed var(--line); border-radius:8px; display:grid; place-items:center; color:var(--muted); background:#f8fbff; text-align:center; padding:24px; }
    .event-title { font-size:24px; margin:0 0 8px; }
    .meta { color:var(--muted); font-size:13px; margin-bottom:14px; }
    .speech { border-left:4px solid var(--brand); background:#eef4ff; padding:12px; border-radius:6px; margin:12px 0; line-height:1.5; direction:auto; }
    .action { border-left:4px solid #e7ad18; background:#fff8df; padding:12px; border-radius:6px; margin:12px 0; }
    pre { white-space:pre-wrap; word-break:break-word; background:#0f172a; color:#e2e8f0; padding:12px; border-radius:6px; max-height:260px; overflow:auto; }
    .log-item { border-bottom:1px solid #edf1f8; padding:10px 0; }
    .tag { display:inline-flex; align-items:center; border-radius:999px; padding:2px 8px; font-size:12px; font-weight:800; background:#edf2ff; color:#2f4ab8; margin-left:6px; }
    .audio-state { color:var(--good); font-weight:800; }
    @media (max-width:1100px) { .layout { grid-template-columns:1fr; } header { height:auto; flex-wrap:wrap; padding:14px; } .transport { min-width:100%; } }
  </style>
</head>
<body>
  <header>
    <h1>PyCatan Replay Viewer</h1>
    <div class="session-chooser">
      <select id="sessionSelect" title="Choose session"></select>
      <button id="loadSessionBtn">Load</button>
    </div>
    <div class="transport">
      <button id="startBtn">|&lt;</button>
      <button id="prevBtn">&lt;</button>
      <button id="playBtn" class="primary">Play</button>
      <button id="nextBtn">&gt;</button>
      <button id="endBtn">&gt;|</button>
      <input id="slider" type="range" min="0" max="0" value="0">
      <div id="counter" class="counter">0 / 0</div>
      <div id="context" class="context">Ready</div>
    </div>
  </header>
  <div id="timeline" class="timeline"></div>
  <main class="layout">
    <section class="panel">
      <h2>Players</h2>
      <div class="body">
        <div id="filters" class="player-filter"></div>
        <div id="stats" style="margin-top:16px"></div>
      </div>
    </section>
    <section class="panel">
      <h2>Replay</h2>
      <div class="body">
        <div class="board-placeholder">
          Board snapshots are not executed in this standalone viewer yet.<br>
          This view is driven by recorded responses and browser-owned audio.
        </div>
        <div id="currentEvent" style="margin-top:16px"></div>
      </div>
    </section>
    <section class="panel">
      <h2>Analysis</h2>
      <div class="body">
        <div id="analysis"></div>
      </div>
    </section>
  </main>
  <script>
    const state = { manifest:null, sessions:[], defaultSession:'', index:-1, playing:false, timer:null, audio:null, filter:'all' };
    const $ = id => document.getElementById(id);

    async function init() {
      await loadSessions();
      bind();
      const params = new URLSearchParams(location.search);
      const initialSession = params.get('session') || state.defaultSession || (state.sessions[0]?.name || '');
      if (initialSession) await loadManifest(initialSession);
      else renderCurrent();
    }

    async function loadSessions() {
      const res = await fetch('/api/sessions');
      const payload = await res.json();
      state.sessions = payload.sessions || [];
      state.defaultSession = payload.default_session || '';
      const selected = state.defaultSession || state.sessions[0]?.name || '';
      $('sessionSelect').innerHTML = state.sessions.length
        ? state.sessions.map(s => {
            const label = `${s.name} (${s.responses || 0} responses${s.audio != null ? ', ' + s.audio + ' audio' : ''})`;
            return `<option value="${escapeAttr(s.name)}" ${s.name === selected ? 'selected' : ''}>${escapeHtml(label)}</option>`;
          }).join('')
        : '<option value="">No sessions found</option>';
    }

    async function loadManifest(sessionName) {
      if (!sessionName) return;
      pause();
      $('context').textContent = `Loading ${sessionName}...`;
      const res = await fetch('/api/manifest?session=' + encodeURIComponent(sessionName));
      if (!res.ok) throw new Error(await res.text());
      state.manifest = await res.json();
      state.index = -1;
      state.filter = 'all';
      $('slider').max = Math.max(0, state.manifest.events.length - 1);
      $('slider').value = 0;
      const selected = $('sessionSelect');
      if (selected.value !== sessionName) selected.value = sessionName;
      history.replaceState(null, '', '?session=' + encodeURIComponent(sessionName));
      renderFilters();
      renderStats();
      renderTimeline();
      renderCurrent();
    }

    function bind() {
      $('playBtn').onclick = togglePlay;
      $('loadSessionBtn').onclick = () => loadManifest($('sessionSelect').value);
      $('sessionSelect').onchange = () => loadManifest($('sessionSelect').value);
      $('startBtn').onclick = () => { pause(); go(-1, false); };
      $('prevBtn').onclick = () => { pause(); go(Math.max(0, state.index - 1), false); };
      $('nextBtn').onclick = () => { pause(); go(Math.min(events().length - 1, state.index + 1), true); };
      $('endBtn').onclick = () => { pause(); go(events().length - 1, false); };
      $('slider').oninput = e => { pause(); go(Number(e.target.value), false); };
      window.addEventListener('pagehide', stopAudio);
      window.addEventListener('beforeunload', stopAudio);
    }

    function events() { return state.manifest?.events || []; }
    function current() { return state.index >= 0 ? events()[state.index] : null; }

    function renderFilters() {
      const players = [...new Set(events().map(e => e.player_name))];
      if (!players.length) {
        $('filters').innerHTML = '<p class="meta">Choose a session to load its players.</p>';
        return;
      }
      $('filters').innerHTML = ['all', ...players].map(name =>
        `<button class="${state.filter === name ? 'active' : ''}" data-player="${escapeAttr(name)}">${escapeHtml(name === 'all' ? 'All' : name)}</button>`
      ).join('');
      $('filters').querySelectorAll('button').forEach(btn => {
        btn.onclick = () => { state.filter = btn.dataset.player; renderFilters(); renderTimeline(); };
      });
    }

    function renderStats() {
      if (!state.manifest) {
        $('stats').innerHTML = `<div class="stat"><strong>Sessions</strong><span>${state.sessions.length}</span></div>`;
        return;
      }
      const s = state.manifest.stats;
      $('stats').innerHTML = [
        ['Session', state.manifest.session.name],
        ['Events', s.events],
        ['Actions', s.actions],
        ['Speech', s.speech],
        ['Chat-only', s.chat || 0],
        ['Audio found', s.audio],
      ].map(([k,v]) => `<div class="stat"><strong>${escapeHtml(k)}</strong><span>${escapeHtml(String(v))}</span></div>`).join('');
    }

    function renderTimeline() {
      $('timeline').innerHTML = events().map(e => {
        const hidden = state.filter !== 'all' && e.player_name !== state.filter;
        const letter = e.kind === 'action' ? 'A' : e.kind === 'speech' ? 'S' : e.kind === 'chat' ? 'C' : e.kind === 'memory' ? 'M' : 'R';
        return `<button class="dot ${e.kind} ${e.index === state.index ? 'active' : ''}" style="${hidden ? 'display:none' : ''}" title="${escapeAttr(e.player_name + ' #' + (e.request_number || '') + ' - ' + e.kind)}" data-index="${e.index}">${letter}</button>`;
      }).join('');
      $('timeline').querySelectorAll('.dot').forEach(btn => {
        btn.onclick = () => { pause(); go(Number(btn.dataset.index), true); };
      });
    }

    function renderCurrent() {
      const e = current();
      $('counter').textContent = `${state.index < 0 ? 0 : state.index + 1} / ${events().length}`;
      $('slider').value = Math.max(0, state.index);
      $('context').textContent = e ? `${e.player_name}${e.request_number ? ' #' + e.request_number : ''} ${e.kind}` : 'Ready';
      renderTimeline();

      if (!e) {
        const title = state.manifest ? 'Ready' : 'Choose Session';
        const message = state.manifest ? 'Press Play to start the replay.' : 'Pick a recorded session from the top bar.';
        $('currentEvent').innerHTML = `<h3 class="event-title">${title}</h3><p class="meta">${message}</p>`;
        $('analysis').innerHTML = '<p class="meta">No response selected yet.</p>';
        return;
      }

      const requestTag = e.request_number ? `<span class="tag">#${escapeHtml(String(e.request_number))}</span>` : '<span class="tag">chat</span>';
      $('currentEvent').innerHTML = `
        <h3 class="event-title">${escapeHtml(e.player_name)} ${requestTag}</h3>
        <div class="meta">${escapeHtml(e.timestamp || '')} · ${escapeHtml(e.kind)} · ${e.has_audio ? '<span class="audio-state">audio</span>' : 'no audio'}</div>
        ${e.say_outloud ? `<div class="speech">${escapeHtml(e.say_outloud)}</div>` : ''}
        ${e.action_type ? `<div class="action"><strong>${escapeHtml(e.action_type)}</strong><pre>${escapeHtml(JSON.stringify(e.parameters || {}, null, 2))}</pre></div>` : ''}
      `;
      $('analysis').innerHTML = `
        <div class="meta">${escapeHtml(e.source_file || '')}</div>
        ${e.note_to_self ? `<h3>Note to Self</h3><div class="speech">${escapeHtml(e.note_to_self)}</div>` : ''}
        ${e.internal_thinking ? `<h3>Thinking</h3><pre>${escapeHtml(e.internal_thinking)}</pre>` : ''}
        <h3>Parsed Response</h3><pre>${escapeHtml(JSON.stringify({
          action_type:e.action_type, parameters:e.parameters, say_outloud:e.say_outloud, chat_to:e.chat_to, tokens:e.tokens, model:e.model
        }, null, 2))}</pre>
        ${e.raw_content ? `<h3>Raw</h3><pre>${escapeHtml(e.raw_content)}</pre>` : ''}
      `;
    }

    function togglePlay() {
      if (state.playing) pause();
      else play();
    }

    function play() {
      if (state.playing) return;
      state.playing = true;
      $('playBtn').textContent = 'Pause';
      if (state.index < 0) go(0, true);
      else scheduleNext(current()?.timeline_gap_seconds || 0);
    }

    function pause() {
      state.playing = false;
      $('playBtn').textContent = 'Play';
      if (state.timer) clearTimeout(state.timer);
      state.timer = null;
      stopAudio();
    }

    function go(index, speak) {
      stopAudio();
      state.index = Math.max(-1, Math.min(index, events().length - 1));
      renderCurrent();
      const e = current();
      if (!e) return;
      if (speak && e.audio_url) {
        playAudio(e);
      } else if (state.playing) {
        scheduleNext(e.timeline_gap_seconds || 0);
      }
    }

    function playAudio(e) {
      const audio = new Audio(e.audio_url);
      state.audio = audio;
      audio.onended = () => { state.audio = null; if (state.playing) scheduleNext(e.timeline_gap_seconds || 0); };
      audio.onerror = () => { state.audio = null; if (state.playing) scheduleNext(e.timeline_gap_seconds || 0); };
      audio.play().catch(err => {
        console.warn('Audio play failed', err);
        state.audio = null;
        if (state.playing) scheduleNext(e.timeline_gap_seconds || 0);
      });
      if (!e.audio_url && state.playing) scheduleNext(e.timeline_gap_seconds || 0);
    }

    function stopAudio() {
      if (!state.audio) return;
      try { state.audio.pause(); state.audio.currentTime = 0; state.audio.src = ''; state.audio.load(); } catch {}
      state.audio = null;
    }

    function scheduleNext(seconds) {
      if (!state.playing) return;
      if (state.index >= events().length - 1) { pause(); return; }
      if (state.timer) clearTimeout(state.timer);
      state.timer = setTimeout(() => go(state.index + 1, true), Math.max(0, Number(seconds) || 0) * 1000);
    }

    function escapeHtml(value) {
      const div = document.createElement('div');
      div.textContent = value ?? '';
      return div.innerHTML;
    }
    function escapeAttr(value) { return escapeHtml(value).replace(/"/g, '&quot;'); }
    init().catch(err => { document.body.innerHTML = '<pre>' + escapeHtml(String(err.stack || err)) + '</pre>'; });
  </script>
</body>
</html>"""


class ReplayViewerServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address,
        handler_class,
        manifest: Optional[Dict[str, Any]],
        max_gap_seconds: float,
    ):
        super().__init__(server_address, handler_class)
        self.manifest = manifest
        self.max_gap_seconds = max_gap_seconds
        self.default_session = (manifest.get("session") or {}).get("name") if manifest else ""
        self._manifest_cache: Dict[str, Dict[str, Any]] = {}
        if manifest and self.default_session:
            self._manifest_cache[self.default_session] = manifest

    def get_manifest(self, session_ref: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not session_ref:
            return self.manifest
        session_dir = resolve_session_path(session_ref)
        cache_key = session_dir.name
        manifest = self._manifest_cache.get(cache_key)
        if not manifest:
            manifest = build_manifest(session_dir, max_gap_seconds=self.max_gap_seconds)
            write_manifest_artifact(session_dir, manifest)
            self._manifest_cache[cache_key] = manifest
        self.manifest = manifest
        self.default_session = cache_key
        return manifest


class ReplayViewerHandler(BaseHTTPRequestHandler):
    server: ReplayViewerServer

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path in {"/", "/index.html"}:
            self._send_bytes(HTML_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/sessions":
            self._send_json({
                "sessions": list_sessions(),
                "default_session": self.server.default_session,
            })
            return
        if path == "/api/manifest":
            query = parse_qs(parsed.query)
            session_ref = (query.get("session") or [""])[0].strip() or None
            manifest = self.server.get_manifest(session_ref)
            if not manifest:
                self._send_json({"error": "No session selected"}, status=400)
                return
            self._send_json(public_manifest(manifest))
            return
        if path.startswith("/api/audio/"):
            event_id = path.rsplit("/", 1)[-1]
            manifest = self.server.get_manifest()
            audio_path = (manifest or {}).get("_audio_by_id", {}).get(event_id)
            if not audio_path or not Path(audio_path).exists():
                self._send_json({"error": "Audio not found"}, status=404)
                return
            mime = mimetypes.guess_type(str(audio_path))[0] or "audio/wav"
            self._send_file(Path(audio_path), mime)
            return
        self._send_json({"error": "Not found"}, status=404)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8", status=status)

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self._send_bytes(data, content_type)

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(manifest: Optional[Dict[str, Any]], host: str, port: int, open_browser: bool, max_gap_seconds: float) -> None:
    server = ReplayViewerServer((host, port), ReplayViewerHandler, manifest, max_gap_seconds)
    url = f"http://{host}:{port}/"
    if manifest:
        print(f"[REPLAY_VIEWER] Serving {manifest['session']['name']} at {url}")
        print(
            "[REPLAY_VIEWER] "
            f"{manifest['stats']['events']} events, "
            f"{manifest['stats']['actions']} actions, "
            f"{manifest['stats']['speech']} speech, "
            f"{manifest['stats']['audio']} audio clips"
        )
    else:
        print(f"[REPLAY_VIEWER] Serving session picker at {url}")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[REPLAY_VIEWER] Stopped")
    finally:
        server.server_close()


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Standalone browser replay viewer for a PyCatan AI session")
    parser.add_argument("--session", help="Session folder path or session_YYYYMMDD_HHMMSS name. Omit to choose in the browser.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=5050, help="Port to bind")
    parser.add_argument("--max-gap", type=float, default=2.5, help="Maximum seconds between recorded response timestamps")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    parser.add_argument("--manifest-only", action="store_true", help="Build the manifest artifact and exit")
    args = parser.parse_args(argv)

    max_gap_seconds = max(0.0, args.max_gap)
    manifest = None
    if args.session:
        session_dir = resolve_session_path(args.session)
        manifest = build_manifest(session_dir, max_gap_seconds=max_gap_seconds)
        artifact = write_manifest_artifact(session_dir, manifest)
        print(f"[REPLAY_VIEWER] Manifest: {artifact}")

    if args.manifest_only:
        if not args.session:
            parser.error("--manifest-only requires --session")
        return

    serve(manifest, args.host, args.port, open_browser=not args.no_browser, max_gap_seconds=max_gap_seconds)


if __name__ == "__main__":
    main()
