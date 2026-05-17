#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Browser setup entrypoint for PyCatan with per-agent OpenRouter models."""

import html as html_lib
import json
import os
import re
import ssl
import sys
import threading
import webbrowser
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    os.environ.setdefault("GRPC_DEFAULT_SSL_ROOTS_FILE_PATH", certifi.where())
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.ai_testing.play_with_ai import (
    DEFAULT_PLAYER_NAMES,
    ELEVENLABS_TTS_MODELS,
    LOGS_DIR,
    PLAYER_COLORS,
    annotate_replay_session,
    create_game,
    group_replay_decisions,
    infer_players_from_decisions,
    infer_players_from_session,
    list_replay_marker_options,
    load_ai_config,
    load_env_file,
    load_replay_decision_chain,
    resolve_session_path,
    run_game,
    run_replay_viewer,
)
from pycatan.ai.config import normalize_chat_language


OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
MIN_CONTEXT_LENGTH = 32000
MIN_COMPLETION_TOKENS = 4096
PLAYER_GENDERS = {1: "female", 2: "male", 3: "male", 4: "female"}
VERIFIED_OPENROUTER_MODEL_IDS = [
    "openai/gpt-5.4-mini",
    "openai/gpt-5.4-nano",
    "openai/gpt-4.1-mini",
    "openai/gpt-4o-mini",
    "openai/gpt-5.1-codex-mini",
    "openai/gpt-5-mini",
    "anthropic/claude-haiku-4.5",
    "anthropic/claude-sonnet-4.5",
    "google/gemini-3.1-flash-lite",
    "google/gemini-3-flash-preview",
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.5-flash",
    "google/gemini-2.0-flash-001",
    "google/gemini-2.0-flash-lite-001",
    "mistralai/mistral-small-2603",
    "x-ai/grok-4.20",
]
VERIFIED_OPENROUTER_MODEL_ORDER = {
    model_id: index for index, model_id in enumerate(VERIFIED_OPENROUTER_MODEL_IDS)
}
RELATIONSHIP_CONTEXT_MODES = [
    ("legacy", "Classic table history"),
    ("ai_models", "AI model rivals"),
    ("off", "No relationship context"),
]

GEMINI_TTS_MODELS = [
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-preview-tts",
    "gemini-3.1-flash-tts-preview",
    "gemini-3.1-pro-tts-preview",
]
GEMINI_TTS_VOICES = [
    "Kore", "Puck", "Zephyr", "Charon", "Fenrir", "Leda", "Orus",
    "Aoede", "Callirrhoe", "Autonoe", "Enceladus", "Iapetus",
    "Umbriel", "Algieba", "Despina", "Erinome", "Algenib",
    "Rasalgethi", "Laomedeia", "Achernar", "Alnilam", "Schedar",
    "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]

FALLBACK_MODELS = [
    {
        "id": "openai/gpt-5.4-mini",
        "name": "OpenAI: GPT-5.4 Mini",
        "provider": "openai",
        "context_length": 400000,
        "max_completion_tokens": 128000,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "openai/gpt-5.4-nano",
        "name": "OpenAI: GPT-5.4 Nano",
        "provider": "openai",
        "context_length": 400000,
        "max_completion_tokens": 128000,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "openai/gpt-4.1-mini",
        "name": "OpenAI: GPT-4.1 Mini",
        "provider": "openai",
        "context_length": 1047576,
        "max_completion_tokens": 32768,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "openai/gpt-4o-mini",
        "name": "OpenAI: GPT-4o Mini",
        "provider": "openai",
        "context_length": 128000,
        "max_completion_tokens": 16384,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "openai/gpt-5.1-codex-mini",
        "name": "OpenAI: GPT-5.1 Codex Mini",
        "provider": "openai",
        "context_length": 400000,
        "max_completion_tokens": 128000,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "openai/gpt-5-mini",
        "name": "OpenAI: GPT-5 Mini",
        "provider": "openai",
        "context_length": 400000,
        "max_completion_tokens": 128000,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "anthropic/claude-haiku-4.5",
        "name": "Anthropic: Claude Haiku 4.5",
        "provider": "anthropic",
        "context_length": 200000,
        "max_completion_tokens": 64000,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "anthropic/claude-sonnet-4.5",
        "name": "Anthropic: Claude Sonnet 4.5",
        "provider": "anthropic",
        "context_length": 200000,
        "max_completion_tokens": 8192,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "google/gemini-3.1-flash-lite",
        "name": "Google: Gemini 3.1 Flash Lite",
        "provider": "google",
        "context_length": 1048576,
        "max_completion_tokens": 65536,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "google/gemini-3-flash-preview",
        "name": "Google: Gemini 3 Flash Preview",
        "provider": "google",
        "context_length": 1048576,
        "max_completion_tokens": 65536,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "google/gemini-2.5-flash-lite",
        "name": "Google: Gemini 2.5 Flash Lite",
        "provider": "google",
        "context_length": 1048576,
        "max_completion_tokens": 65535,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "google/gemini-2.5-flash",
        "name": "Google: Gemini 2.5 Flash",
        "provider": "google",
        "context_length": 1048576,
        "max_completion_tokens": 65535,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "google/gemini-2.0-flash-001",
        "name": "Google: Gemini 2.0 Flash",
        "provider": "google",
        "context_length": 1048576,
        "max_completion_tokens": 8192,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "google/gemini-2.0-flash-lite-001",
        "name": "Google: Gemini 2.0 Flash Lite",
        "provider": "google",
        "context_length": 1048576,
        "max_completion_tokens": 8192,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "mistralai/mistral-small-2603",
        "name": "Mistral: Mistral Small 4",
        "provider": "mistralai",
        "context_length": 262144,
        "max_completion_tokens": 0,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
    {
        "id": "x-ai/grok-4.20",
        "name": "xAI: Grok 4.20",
        "provider": "x-ai",
        "context_length": 2000000,
        "max_completion_tokens": 0,
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format", "structured_outputs", "temperature", "max_tokens"],
        "pricing": {"prompt": "", "completion": ""},
    },
]


def provider_from_model_id(model_id: str) -> str:
    return (model_id.split("/", 1)[0] if "/" in model_id else "custom").strip().lower()


def normalize_model(raw: Dict[str, Any]) -> Dict[str, Any]:
    model_id = str(raw.get("id", "")).strip()
    pricing = raw.get("pricing") or {}
    architecture = raw.get("architecture") or {}
    top_provider = raw.get("top_provider") or {}
    return {
        "id": model_id,
        "name": raw.get("name") or model_id,
        "provider": provider_from_model_id(model_id),
        "context_length": raw.get("context_length") or 0,
        "max_completion_tokens": top_provider.get("max_completion_tokens") or 0,
        "output_modalities": architecture.get("output_modalities") or ["text"],
        "supported_parameters": raw.get("supported_parameters") or [],
        "pricing": {
            "prompt": pricing.get("prompt", ""),
            "completion": pricing.get("completion", ""),
        },
    }


def is_suitable_openrouter_model(model: Dict[str, Any]) -> bool:
    supported = set(model.get("supported_parameters") or [])
    output_modalities = set(model.get("output_modalities") or ["text"])
    context_length = int(model.get("context_length") or 0)
    max_completion_tokens = int(model.get("max_completion_tokens") or 0)
    return (
        model.get("id") in VERIFIED_OPENROUTER_MODEL_IDS
        and "tools" in supported
        and "response_format" in supported
        and "text" in output_modalities
        and context_length >= MIN_CONTEXT_LENGTH
        and (max_completion_tokens == 0 or max_completion_tokens >= MIN_COMPLETION_TOKENS)
    )


def fetch_openrouter_models(api_key: str = "") -> List[Dict[str, Any]]:
    try:
        import requests

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        request_kwargs = {
            "headers": headers,
            "params": {"output_modalities": "text"},
            "timeout": 12,
            "verify": os.environ.get("REQUESTS_CA_BUNDLE") or True,
        }
        try:
            response = requests.get(OPENROUTER_MODELS_URL, **request_kwargs)
        except requests.exceptions.SSLError:
            requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
            response = requests.get(OPENROUTER_MODELS_URL, **{**request_kwargs, "verify": False})
        response.raise_for_status()
        models = [normalize_model(item) for item in response.json().get("data", [])]
    except Exception as exc:
        print(f"[OPENROUTER] Could not fetch model list, using fallback models: {exc}")
        models = list(FALLBACK_MODELS)

    usable = [model for model in models if is_suitable_openrouter_model(model)]
    usable = usable or [model for model in FALLBACK_MODELS if is_suitable_openrouter_model(model)]
    usable.sort(
        key=lambda item: (
            VERIFIED_OPENROUTER_MODEL_ORDER.get(item["id"], len(VERIFIED_OPENROUTER_MODEL_ORDER)),
            item["provider"],
            item["name"].lower(),
        )
    )
    return usable


def _env_has(name: str) -> bool:
    return bool(os.environ.get(name))


def _options(values: List[str], selected: str = "") -> str:
    return "".join(
        f'<option value="{html_lib.escape(value)}" {"selected" if value == selected else ""}>'
        f"{html_lib.escape(value)}</option>"
        for value in values
    )


def _tts_model_options(selected: str = "eleven_v3") -> str:
    return "".join(
        f'<option value="{html_lib.escape(model["id"])}" {"selected" if model["id"] == selected else ""}>'
        f'{html_lib.escape(model["label"])} - {html_lib.escape(model["id"])}</option>'
        for model in ELEVENLABS_TTS_MODELS
    )


def _relationship_context_mode_options(selected: str = "legacy") -> str:
    return "".join(
        f'<option value="{html_lib.escape(value)}" {"selected" if value == selected else ""}>'
        f"{html_lib.escape(label)}</option>"
        for value, label in RELATIONSHIP_CONTEXT_MODES
    )


def _recent_session_options() -> str:
    if not LOGS_DIR.exists():
        return ""
    sessions = sorted(
        [path.name for path in LOGS_DIR.iterdir() if path.is_dir() and path.name.startswith("session_")],
        reverse=True,
    )[:30]
    return "".join(f'<option value="{html_lib.escape(session)}"></option>' for session in sessions)


def _price_label(model: Dict[str, Any]) -> str:
    pricing = model.get("pricing") or {}
    prompt = pricing.get("prompt") or "?"
    completion = pricing.get("completion") or "?"
    return f"prompt {prompt} / completion {completion}"


def _slot_llm_from_selected(selected: Dict[str, Any], slot: int, models: List[Dict[str, Any]]) -> Dict[str, str]:
    providers = sorted({model["provider"] for model in models})
    provider = selected.get(f"provider_{slot}") or (providers[0] if providers else "openai")
    model_id = (
        selected.get(f"manual_model_{slot}")
        or selected.get(f"model_{slot}")
        or next((model["id"] for model in models if model["provider"] == provider), models[0]["id"])
    )
    return {
        "provider": "openrouter",
        "model_provider": provider_from_model_id(model_id),
        "model_name": model_id,
        "api_key_env_var": "OPENROUTER_API_KEY",
    }


def render_landing_page() -> bytes:
    recent_sessions = []
    if LOGS_DIR.exists():
        recent_sessions = sorted(
            [path.name for path in LOGS_DIR.iterdir() if path.is_dir() and path.name.startswith("session_")],
            reverse=True,
        )[:6]

    replay_links = "".join(
        "<a class=\"session-link\" href=\"/settings?mode=watch_replay"
        f"&session={html_lib.escape(session)}\">{html_lib.escape(session)}</a>"
        for session in recent_sessions
    )
    if not replay_links:
        replay_links = "<p class=\"muted\">No public replay sessions are bundled yet.</p>"

    return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PyCatan AI</title>
<style>
:root {{
  color-scheme: light;
  --ink: #17202a;
  --muted: #536273;
  --line: #d9e0e8;
  --surface: #ffffff;
  --wash: #f3f6f8;
  --accent: #226f68;
  --accent-dark: #18544f;
  --gold: #b7791f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  font-family: "Segoe UI", Arial, sans-serif;
  color: var(--ink);
  background: var(--wash);
}}
.page {{
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
  padding: 42px 0 34px;
}}
.hero {{
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(300px, 0.95fr);
  gap: 28px;
  align-items: stretch;
}}
.intro {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 34px;
}}
.eyebrow {{
  color: var(--gold);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
  margin-bottom: 12px;
}}
h1 {{
  margin: 0 0 14px;
  font-size: clamp(32px, 6vw, 60px);
  line-height: 1.02;
  letter-spacing: 0;
}}
.lead {{
  color: var(--muted);
  font-size: 18px;
  line-height: 1.65;
  max-width: 720px;
  margin: 0 0 26px;
}}
.actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}}
.button {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 18px;
  border-radius: 6px;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
  text-decoration: none;
  font-weight: 700;
}}
.button.secondary {{
  background: #fff;
  color: var(--accent-dark);
}}
.panel {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 24px;
}}
.panel h2 {{
  margin: 0 0 12px;
  font-size: 22px;
  letter-spacing: 0;
}}
.panel p {{
  color: var(--muted);
  line-height: 1.55;
}}
.session-list {{
  display: grid;
  gap: 8px;
  margin-top: 16px;
}}
.session-link {{
  display: block;
  direction: ltr;
  text-align: left;
  color: var(--accent-dark);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px 12px;
  text-decoration: none;
  background: #fbfcfd;
  font-family: Consolas, monospace;
  font-size: 13px;
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}}
.step {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
}}
.step strong {{ display: block; margin-bottom: 8px; }}
.step span {{ color: var(--muted); line-height: 1.5; }}
.muted {{ color: var(--muted); }}
@media (max-width: 860px) {{
  .hero, .grid {{ grid-template-columns: 1fr; }}
  .intro {{ padding: 26px; }}
}}
</style>
</head>
<body>
<main class="page">
  <section class="hero">
    <div class="intro">
      <div class="eyebrow">Public AI table</div>
      <h1>PyCatan AI</h1>
      <p class="lead">
        משחק קטאן עם שחקני AI, ריפליי של סשנים ציבוריים, וניתוח החלטות.
        אפשר לצפות בלי מפתח, או להתחיל משחק חי עם מפתח OpenRouter משלך.
      </p>
      <div class="actions">
        <a class="button" href="/settings">התחל משחק או ריפליי</a>
        <a class="button secondary" href="/settings?mode=watch_replay">צפה בריפליי</a>
      </div>
    </div>
    <aside class="panel">
      <h2>סשנים ציבוריים אחרונים</h2>
      <p>בחר סשן מהרשימה או עבור למסך ההגדרות כדי לבחור סשן אחר.</p>
      <div class="session-list">{replay_links}</div>
    </aside>
  </section>
  <section class="grid" aria-label="How it works">
    <div class="step"><strong>1. צופים</strong><span>ריפליי וניתוח החלטות זמינים בלי להזין מפתחות.</span></div>
    <div class="step"><strong>2. משחקים</strong><span>משחק חי עם LLM משתמש במפתח OpenRouter שהמשתמש מזין בעצמו.</span></div>
    <div class="step"><strong>3. משתפים</strong><span>הסשנים נשמרים כתוכן ציבורי של הדמו, בהתאם לאחסון הזמין.</span></div>
  </section>
</main>
</body>
</html>""".encode("utf-8")


def render_settings_page(
    models: List[Dict[str, Any]],
    key_mode: str,
    errors: Optional[List[str]] = None,
    selected: Optional[Dict[str, Any]] = None,
) -> str:
    selected = selected or {}
    player_count = int(selected.get("player_count", 4) or 4)
    providers = sorted({model["provider"] for model in models})
    provider_options = "".join(
        f'<option value="{html_lib.escape(provider)}">{html_lib.escape(provider.title())}</option>'
        for provider in providers
    )
    errors_html = ""
    if errors:
        errors_html = "<div class=\"errors\"><ul>" + "".join(
            f"<li>{html_lib.escape(error)}</li>" for error in errors
        ) + "</ul></div>"

    player_blocks = []
    for index in range(4):
        slot = index + 1
        slot_llm = _slot_llm_from_selected(selected, slot, models)
        name = selected.get(f"player_{slot}") or DEFAULT_PLAYER_NAMES[index]
        player_blocks.append(f"""
        <fieldset class="player-card" data-player-card="{slot}">
            <legend>P{slot} - {PLAYER_COLORS[index]} - {PLAYER_GENDERS[slot]}</legend>
            <label class="player-name-label">Name<input name="player_{slot}" data-player-name="{slot}" value="{html_lib.escape(name)}" maxlength="32"></label>
            <div class="form-grid">
                <label>Provider<select name="provider_{slot}" data-provider-select="{slot}">{provider_options}</select></label>
                <label>Model<select name="model_{slot}" data-model-select="{slot}"></select></label>
            </div>
            <label>Manual model id<input name="manual_model_{slot}" value="{html_lib.escape(selected.get(f'manual_model_{slot}', ''))}" placeholder="anthropic/claude-sonnet-4.5"></label>
            <input type="hidden" data-selected-provider="{slot}" value="{html_lib.escape(slot_llm['model_provider'])}">
            <input type="hidden" data-selected-model="{slot}" value="{html_lib.escape(slot_llm['model_name'])}">
        </fieldset>
        """)

    model_cards = []
    for model in models[:28]:
        model_cards.append(
            "<li>"
            f"<strong>{html_lib.escape(model['id'])}</strong>"
            f"<span>{html_lib.escape(model['name'])}</span>"
            f"<small>{int(model.get('context_length') or 0):,} ctx | {_price_label(model)}</small>"
            "</li>"
        )

    models_json = json.dumps(models, ensure_ascii=False)
    # Server-side validation below knows the selected run mode/TTS provider.
    # Avoid static browser "required" on fields that may be hidden by the UI.
    openrouter_required = ""
    gemini_required = ""
    eleven_key_required = ""
    eleven_voice_required = ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PyCatan OpenRouter Setup</title>
<style>
:root {{ --bg:#eef2f5; --ink:#18222d; --muted:#66717e; --panel:#fff; --line:#c9d3de; --accent:#1e6f5c; --danger:#b42318; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; min-height:100vh; font-family:"Segoe UI",Arial,sans-serif; background:var(--bg); color:var(--ink); padding:24px; }}
main {{ width:min(1180px,100%); margin:0 auto; display:grid; grid-template-columns:minmax(0,1.25fr) minmax(310px,.75fr); gap:22px; align-items:start; }}
section, aside {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 16px 38px rgba(24,34,45,.12); }}
section, aside {{ padding:24px; }}
aside {{ position:sticky; top:24px; }}
h1,h2 {{ margin:0; }}
p {{ color:var(--muted); line-height:1.5; }}
form {{ display:grid; gap:18px; margin-top:20px; }}
fieldset {{ border:1px solid var(--line); border-radius:8px; padding:16px; }}
legend {{ padding:0 8px; font-weight:800; }}
label {{ display:grid; gap:7px; font-weight:700; }}
input,select,textarea {{ width:100%; border:1px solid #b8c2cc; border-radius:6px; padding:10px 12px; font:inherit; background:#fbfcfd; color:var(--ink); }}
textarea {{ min-height:92px; resize:vertical; }}
.form-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin-top:12px; }}
.player-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
.player-card[data-hidden="true"], .hidden {{ display:none; }}
.locked-control {{ background:#eef2f5; color:var(--muted); }}
.player-name-label input[readonly] {{ background:#eef2f5; color:var(--muted); }}
.checkbox-row {{ display:flex; align-items:center; gap:8px; }}
.checkbox-row input {{ width:auto; }}
.errors {{ color:var(--danger); background:#fff0ed; border:1px solid #f4b4aa; border-radius:8px; padding:10px 14px; }}
button {{ border:0; border-radius:7px; padding:13px 18px; font:inherit; font-weight:850; color:white; background:var(--accent); cursor:pointer; }}
.model-list {{ margin:0; padding-left:18px; display:grid; gap:10px; color:var(--muted); font-size:13px; }}
.model-list strong,.model-list span,.model-list small {{ display:block; }}
.hint {{ margin:6px 0 0; font-size:13px; }}
@media (max-width:900px) {{ main {{ grid-template-columns:1fr; }} aside {{ position:static; }} .player-grid,.form-grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<main>
<section>
<h1>PyCatan OpenRouter Setup</h1>
<p>Full setup mode: run/replay, per-agent OpenRouter models, TTS, reactions, and player slots. TTS stays mapped to PLAYER_1 through PLAYER_4. P1 and P4 are female; P2 and P3 are male.</p>
{errors_html}
<form method="post" action="/start">
<fieldset>
<legend>Run Mode</legend>
<div class="form-grid">
<label>Mode<select name="run_mode" id="run-mode">
<option value="new_game" {"selected" if selected.get("run_mode", "new_game") == "new_game" else ""}>New live game</option>
<option value="resume_session" {"selected" if selected.get("run_mode") == "resume_session" else ""}>Fast replay, then continue live</option>
<option value="watch_replay" {"selected" if selected.get("run_mode") == "watch_replay" else ""}>Watch recorded session only</option>
<option value="analyse_game" {"selected" if selected.get("run_mode") == "analyse_game" else ""}>Analyse recorded session</option>
</select></label>
<label>Config file<input name="config_path" value="{html_lib.escape(selected.get('config_path', ''))}" placeholder="pycatan/ai/config_dev.yaml"></label>
</div>
<div id="replay-fields" class="form-grid">
<label>Session<input name="replay_session" list="recent-sessions" value="{html_lib.escape(selected.get('replay_session', ''))}" placeholder="session_YYYYMMDD_HHMMSS"><datalist id="recent-sessions">{_recent_session_options()}</datalist></label>
<label>Stop before<input name="replay_stop_before" list="replay-marker-options" value="{html_lib.escape(selected.get('replay_stop_before', ''))}" placeholder="Shon:4"></label>
<label>Replay through<input name="replay_through" list="replay-marker-options" value="{html_lib.escape(selected.get('replay_through', ''))}" placeholder="Ziv:8"></label>
<datalist id="replay-marker-options"></datalist>
<label>Max responses<input name="replay_max_decisions" type="number" min="1" step="1" value="{html_lib.escape(selected.get('replay_max_decisions', ''))}"></label>
<label>Replay delay<input name="replay_delay" type="number" min="0" step="0.1" value="{html_lib.escape(selected.get('replay_delay', '2.5'))}"></label>
<label>Text lead<input name="replay_text_lead" type="number" min="0" step="0.05" value="{html_lib.escape(selected.get('replay_text_lead', '0.25'))}"></label>
</div>
<label class="checkbox-row"><input name="replay_skip_chat" type="checkbox" {"checked" if selected.get("replay_skip_chat") else ""}>Skip recorded chat during fast replay</label>
<label class="checkbox-row"><input name="replay_speak" type="checkbox" {"checked" if selected.get("replay_speak") else ""}>Speak recorded replay chat from cache</label>
<p class="hint" id="replay-marker-status">Replay markers are loaded from recorded LLM responses.</p>
</fieldset>

<fieldset>
<legend>Execution</legend>
<div class="form-grid">
<label>OpenRouter API key<input name="openrouter_api_key" type="password" autocomplete="off" {openrouter_required} data-env-optional="{'true' if _env_has('OPENROUTER_API_KEY') else 'false'}" placeholder="{'ENV key available' if _env_has('OPENROUTER_API_KEY') else 'sk-or-...'}"></label>
<label>Table-talk language<select name="chat_language"><option value="hebrew" {"selected" if selected.get("chat_language", "hebrew") == "hebrew" else ""}>Hebrew</option><option value="english" {"selected" if selected.get("chat_language") == "english" else ""}>English</option></select></label>
<label>Relationship context<select name="relationship_context_mode">{_relationship_context_mode_options(selected.get('relationship_context_mode', 'legacy'))}</select></label>
<label>Off-turn reactions<select name="reaction_mode"><option value="default" {"selected" if selected.get("reaction_mode", "default") == "default" else ""}>Use config default</option><option value="off" {"selected" if selected.get("reaction_mode") == "off" else ""}>Off</option><option value="sync" {"selected" if selected.get("reaction_mode") == "sync" else ""}>Sync</option><option value="async" {"selected" if selected.get("reaction_mode") == "async" else ""}>Async</option></select></label>
<label>Reaction batch size<input name="reaction_batch_size" type="number" min="1" step="1" value="{html_lib.escape(selected.get('reaction_batch_size', ''))}" placeholder="5"></label>
<label>Victory points to win<input name="victory_points" type="number" min="1" step="1" value="{html_lib.escape(selected.get('victory_points', '5'))}" placeholder="5"></label>
<label>Random seed<input name="random_seed" type="number" step="1" value="{html_lib.escape(selected.get('random_seed', ''))}" placeholder="0"></label>
</div>
<label>Additional game context<textarea name="game_context" maxlength="4000" placeholder="Optional table-wide context that every agent should know.">{html_lib.escape(selected.get('game_context', ''))}</textarea></label>
<label class="checkbox-row"><input name="no_llm" type="checkbox" {"checked" if selected.get("no_llm") else ""}>Offline mode, no new LLM calls</label>
<p class="hint">Victory points are written into the game state and prompts. Leave random seed blank to use the current deterministic default: 0.</p>
</fieldset>

<fieldset id="voice-section">
<legend>Voice</legend>
<div class="form-grid">
<label>Provider<select name="tts_provider" id="tts-provider"><option value="gemini" {"selected" if selected.get("tts_provider", "gemini") == "gemini" else ""}>Gemini TTS</option><option value="elevenlabs" {"selected" if selected.get("tts_provider") == "elevenlabs" else ""}>ElevenLabs</option><option value="off" {"selected" if selected.get("tts_provider") == "off" else ""}>Off</option></select></label>
<label class="gemini-tts">Gemini API key<input name="gemini_api_key" type="password" autocomplete="off" {gemini_required} data-env-optional="{'true' if _env_has('GEMINI_API_KEY') else 'false'}" placeholder="{'ENV key available' if _env_has('GEMINI_API_KEY') else ''}"></label>
<label class="gemini-tts">Gemini TTS model<select name="gemini_tts_model">{_options(GEMINI_TTS_MODELS, selected.get('gemini_tts_model', 'gemini-2.5-flash-preview-tts'))}</select></label>
<label class="gemini-tts">Gemini voice<select name="gemini_tts_voice">{_options(GEMINI_TTS_VOICES, selected.get('gemini_tts_voice', 'Kore'))}</select></label>
<label class="eleven-tts">ElevenLabs model<select name="elevenlabs_tts_model">{_tts_model_options(selected.get('elevenlabs_tts_model', 'eleven_v3'))}</select></label>
<label class="eleven-tts">ElevenLabs API key<input name="elevenlabs_api_key" type="password" autocomplete="off" {eleven_key_required} data-env-optional="{'true' if _env_has('ELEVENLABS_API_KEY') else 'false'}" placeholder="{'ENV key available' if _env_has('ELEVENLABS_API_KEY') else ''}"></label>
<label class="eleven-tts">ElevenLabs default voice id<input name="elevenlabs_default_voice_id" autocomplete="off" {eleven_voice_required} data-env-optional="{'true' if _env_has('ELEVENLABS_DEFAULT_VOICE_ID') else 'false'}" placeholder="{'ENV voice available' if _env_has('ELEVENLABS_DEFAULT_VOICE_ID') else ''}"></label>
</div>
</fieldset>

<fieldset id="players-section">
<legend>Players and models</legend>
<label>Player count<select name="player_count" id="player-count"><option value="2" {"selected" if player_count == 2 else ""}>2</option><option value="3" {"selected" if player_count == 3 else ""}>3</option><option value="4" {"selected" if player_count == 4 else ""}>4</option></select></label>
<input type="hidden" name="player_count" id="locked-player-count" disabled>
<p class="hint" id="player-lock-status">For replay/resume modes, player names are loaded from the selected session; only models remain editable.</p>
<div class="player-grid">{''.join(player_blocks)}</div>
</fieldset>
<button type="submit">Start game</button>
</form>
</section>
<aside>
<h2>Suitable OpenRouter Models</h2>
<p>Only models with tools, response_format, text output, at least {MIN_CONTEXT_LENGTH:,} context, and at least {MIN_COMPLETION_TOKENS:,} output tokens are listed and accepted.</p>
<ol class="model-list">{''.join(model_cards)}</ol>
</aside>
</main>
<script>
const models = {models_json};
const runModeSelect = document.querySelector('#run-mode');
const replaySessionInput = document.querySelector('input[name="replay_session"]');
const replayMarkerOptions = document.getElementById('replay-marker-options');
const replayMarkerStatus = document.getElementById('replay-marker-status');
const playerCountSelect = document.querySelector('#player-count');
const lockedPlayerCount = document.getElementById('locked-player-count');
const playerLockStatus = document.getElementById('player-lock-status');
function optionText(model) {{
  const ctx = model.context_length ? ` - ${{Number(model.context_length).toLocaleString()}} ctx` : '';
  return `${{model.name}} - ${{model.id}}${{ctx}}`;
}}
function refreshPlayer(slot) {{
  const providerSelect = document.querySelector(`[data-provider-select="${{slot}}"]`);
  const modelSelect = document.querySelector(`[data-model-select="${{slot}}"]`);
  const selectedProvider = document.querySelector(`[data-selected-provider="${{slot}}"]`).value;
  const selectedModel = document.querySelector(`[data-selected-model="${{slot}}"]`).value;
  if (providerSelect.dataset.initialized !== 'true') {{ providerSelect.value = selectedProvider; providerSelect.dataset.initialized = 'true'; }}
  const filtered = models.filter((model) => model.provider === providerSelect.value);
  modelSelect.innerHTML = '';
  filtered.forEach((model) => {{
    const option = document.createElement('option');
    option.value = model.id;
    option.textContent = optionText(model);
    if (model.id === selectedModel) option.selected = true;
    modelSelect.appendChild(option);
  }});
}}
function refreshPlayers() {{
  const count = Number(playerCountSelect.value);
  for (let slot = 1; slot <= 4; slot++) {{
    document.querySelector(`[data-player-card="${{slot}}"]`).dataset.hidden = slot > count ? 'true' : 'false';
    refreshPlayer(slot);
  }}
}}
function setPlayerNamesLocked(locked) {{
  playerCountSelect.disabled = locked;
  playerCountSelect.classList.toggle('locked-control', locked);
  lockedPlayerCount.disabled = !locked;
  lockedPlayerCount.value = playerCountSelect.value;
  for (let slot = 1; slot <= 4; slot++) {{
    const input = document.querySelector(`[data-player-name="${{slot}}"]`);
    input.readOnly = locked;
  }}
  playerLockStatus.classList.toggle('hidden', !locked);
}}
function setSelectValue(name, value) {{
  if (value === undefined || value === null || value === '') return;
  const select = document.querySelector(`[name="${{name}}"]`);
  if (select && [...select.options].some((option) => option.value === String(value))) {{
    select.value = String(value);
  }}
}}
function setInputValue(name, value) {{
  if (value === undefined || value === null || value === '') return;
  const input = document.querySelector(`[name="${{name}}"]`);
  if (input) input.value = String(value);
}}
function applyRestoredSessionSettings(payload) {{
  if (!payload || payload.error) return [];
  const restored = [];
  const reactions = payload.reactions || {{}};
  const tts = payload.tts || {{}};
  setSelectValue('chat_language', payload.chat_language);
  setSelectValue('relationship_context_mode', payload.relationship_context_mode);
  setSelectValue('reaction_mode', reactions.mode);
  setInputValue('reaction_batch_size', reactions.batch_size);
  setInputValue('victory_points', payload.victory_points);
  setInputValue('random_seed', payload.random_seed);
  setInputValue('game_context', payload.game_context);
  setInputValue('config_path', payload.config_path);
  setSelectValue('tts_provider', tts.provider);
  setSelectValue('gemini_tts_model', tts.gemini_model);
  setSelectValue('gemini_tts_voice', tts.gemini_voice);
  setSelectValue('elevenlabs_tts_model', tts.elevenlabs_model);
  refreshTts();

  const players = (payload.players || []).slice(0, 4);
  if (players.length) {{
    const count = Math.min(4, Math.max(2, players.length));
    playerCountSelect.value = String(count);
    lockedPlayerCount.value = String(count);
    players.forEach((player, index) => {{
      const slot = index + 1;
      const nameInput = document.querySelector(`[data-player-name="${{slot}}"]`);
      if (nameInput && player.name) nameInput.value = player.name;
      const llm = player.llm || {{}};
      const provider = llm.model_provider || '';
      const modelName = llm.model_name || '';
      const providerSelect = document.querySelector(`[data-provider-select="${{slot}}"]`);
      const modelSelect = document.querySelector(`[data-model-select="${{slot}}"]`);
      const manualModel = document.querySelector(`[name="manual_model_${{slot}}"]`);
      const selectedProvider = document.querySelector(`[data-selected-provider="${{slot}}"]`);
      const selectedModel = document.querySelector(`[data-selected-model="${{slot}}"]`);
      if (selectedProvider && provider) selectedProvider.value = provider;
      if (selectedModel && modelName) selectedModel.value = modelName;
      if (providerSelect && provider && [...providerSelect.options].some((option) => option.value === provider)) {{
        providerSelect.value = provider;
        providerSelect.dataset.initialized = 'true';
        refreshPlayer(slot);
      }}
      if (modelSelect && modelName && [...modelSelect.options].some((option) => option.value === modelName)) {{
        modelSelect.value = modelName;
        if (manualModel) manualModel.value = '';
      }} else if (manualModel && modelName) {{
        manualModel.value = modelName;
      }}
    }});
    restored.push('players/models');
  }}
  if (payload.chat_language) restored.push('language');
  if (payload.relationship_context_mode) restored.push('relationship');
  if (reactions.mode) restored.push('reactions');
  if (payload.victory_points) restored.push('victory points');
  return restored;
}}
async function loadSessionPlayers() {{
  if (runModeSelect.value === 'new_game') {{
    setPlayerNamesLocked(false);
    refreshPlayers();
    return;
  }}
  setPlayerNamesLocked(true);
  const sessionName = replaySessionInput.value.trim();
  if (!sessionName) {{
    playerLockStatus.textContent = 'Choose a session to lock player names from that recording.';
    refreshPlayers();
    return;
  }}
  playerLockStatus.textContent = 'Loading session settings...';
  try {{
    const response = await fetch(`/session-settings?session=${{encodeURIComponent(sessionName)}}`);
    const payload = await response.json();
    if (!response.ok) {{
      playerLockStatus.textContent = payload.error || 'Could not load settings from session.';
      refreshPlayers();
      return;
    }}
    const restored = applyRestoredSessionSettings(payload);
    const names = (payload.players || []).map((player) => player.name || player).slice(0, 4);
    if (names.length) {{
      const count = Math.min(4, Math.max(2, names.length));
      playerCountSelect.value = String(count);
      lockedPlayerCount.value = String(count);
      names.forEach((name, index) => {{
        const input = document.querySelector(`[data-player-name="${{index + 1}}"]`);
        if (input) input.value = name;
      }});
      const suffix = restored.length ? ` Restored: ${{restored.join(', ')}}.` : '';
      playerLockStatus.textContent = `Locked to session players: ${{names.join(', ')}}.${{suffix}} You can still change models/settings before start.`;
    }} else {{
      playerLockStatus.textContent = 'No player names were found in this session yet.';
    }}
  }} catch (error) {{
    playerLockStatus.textContent = 'Could not load settings from session.';
  }}
  refreshPlayers();
}}
function refreshMode() {{
  const mode = runModeSelect.value;
  const needsReplay = mode !== 'new_game';
  document.querySelector('#replay-fields').classList.toggle('hidden', !needsReplay);
  replaySessionInput.required = needsReplay;
  if (needsReplay) {{
    loadReplayMarkers();
    loadSessionPlayers();
  }} else {{
    setPlayerNamesLocked(false);
  }}
  refreshPlayers();
}}
let replaySessionLoadTimer = null;
function scheduleReplaySessionLoad() {{
  clearTimeout(replaySessionLoadTimer);
  replaySessionLoadTimer = setTimeout(() => {{
    loadReplayMarkers();
    loadSessionPlayers();
  }}, 200);
}}
async function loadReplayMarkers() {{
  const sessionName = replaySessionInput.value.trim();
  replayMarkerOptions.innerHTML = '';
  if (!sessionName) {{
    replayMarkerStatus.textContent = 'Choose a session to see valid replay markers.';
    return;
  }}
  replayMarkerStatus.textContent = 'Loading replay markers...';
  try {{
    const response = await fetch(`/replay-markers?session=${{encodeURIComponent(sessionName)}}`);
    const payload = await response.json();
    if (!response.ok) {{
      replayMarkerStatus.textContent = payload.error || 'Could not load replay markers.';
      return;
    }}
    payload.markers.forEach((marker) => {{
      const option = document.createElement('option');
      option.value = marker.value;
      option.label = marker.label;
      replayMarkerOptions.appendChild(option);
    }});
    replayMarkerStatus.textContent = payload.markers.length
      ? `${{payload.markers.length}} valid action markers available. Reactions/table talk are intentionally excluded.`
      : 'No action markers were found in this session.';
  }} catch (error) {{
    replayMarkerStatus.textContent = 'Could not load replay markers.';
  }}
}}
function refreshTts() {{
  const provider = document.querySelector('#tts-provider').value;
  document.querySelectorAll('.gemini-tts').forEach((el) => el.classList.toggle('hidden', provider !== 'gemini'));
  document.querySelectorAll('.eleven-tts').forEach((el) => el.classList.toggle('hidden', provider !== 'elevenlabs'));
}}
for (let slot = 1; slot <= 4; slot++) document.querySelector(`[data-provider-select="${{slot}}"]`).addEventListener('change', () => refreshPlayer(slot));
playerCountSelect.addEventListener('change', () => {{
  lockedPlayerCount.value = playerCountSelect.value;
  refreshPlayers();
}});
runModeSelect.addEventListener('change', refreshMode);
document.querySelector('#tts-provider').addEventListener('change', refreshTts);
replaySessionInput.addEventListener('input', scheduleReplaySessionLoad);
replaySessionInput.addEventListener('change', () => {{
  loadReplayMarkers();
  loadSessionPlayers();
}});
refreshPlayers(); refreshMode(); refreshTts();
</script>
</body>
</html>"""


def render_starting_page(player_configs: List[Dict[str, Any]], run_mode: str) -> bytes:
    rows = "".join(
        f"<li>P{index + 1}: {html_lib.escape(player['name'])} - "
        f"{html_lib.escape(player.get('llm', {}).get('model_name', 'offline'))}</li>"
        for index, player in enumerate(player_configs)
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Starting PyCatan</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#eef2f5;color:#18222d;display:grid;place-items:center;min-height:100vh;">
<main style="background:white;border:1px solid #c9d3de;border-radius:8px;padding:28px;width:min(620px,calc(100% - 32px));">
<h1>Starting game...</h1><p><strong>Mode:</strong> {html_lib.escape(run_mode)}</p><ul>{rows}</ul>
<p>The board will open here as soon as the game server is ready.</p>
<script>async function waitForGame(){{try{{const r=await fetch('/api/game-state',{{cache:'no-store'}});if(r.ok){{window.location.href='/unified';return;}}}}catch(e){{}}setTimeout(waitForGame,1000);}}setTimeout(waitForGame,1000);</script>
</main></body></html>""".encode("utf-8")


def _as_bool_field(fields: Dict[str, str], name: str) -> bool:
    return name in fields


def _parse_optional_int(value: str, errors: List[str], label: str) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = int(value)
        if parsed < 1:
            errors.append(f"{label} must be at least 1.")
        return parsed
    except ValueError:
        errors.append(f"{label} must be a number.")
        return None


def _parse_float(value: str, default: float, errors: List[str], label: str) -> float:
    try:
        parsed = float(value or default)
        if parsed < 0:
            errors.append(f"{label} cannot be negative.")
        return parsed
    except ValueError:
        errors.append(f"{label} must be a number.")
        return default


def _settings_selection_from_query(query: Dict[str, List[str]]) -> Dict[str, Any]:
    mode = (query.get("mode") or query.get("run_mode") or [""])[0].strip()
    session = (query.get("session") or query.get("replay_session") or [""])[0].strip()
    selected: Dict[str, Any] = {}

    if mode in {"new_game", "resume_session", "watch_replay", "analyse_game"}:
        selected["run_mode"] = mode
    if session:
        selected["replay_session"] = session
    if mode in {"watch_replay", "analyse_game"}:
        selected["tts_provider"] = "off"

    return selected


def _infer_session_player_names(session_dir: Path) -> List[str]:
    """Infer locked player names for a replay/resume source session."""
    names = infer_players_from_session(session_dir)
    if names:
        return names[:4]
    try:
        decisions = load_replay_decision_chain(session_dir)
    except Exception:
        return []
    return infer_players_from_decisions(decisions)[:4]


def _load_session_final_state(session_dir: Path) -> Optional[Dict[str, Any]]:
    summary_file = session_dir / "session_summary.json"
    if not summary_file.exists():
        return None
    try:
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    final_state = summary.get("final_game_state")
    return final_state if isinstance(final_state, dict) else None


def _minimum_recorded_actions_for_state(final_state: Optional[Dict[str, Any]]) -> int:
    if not final_state:
        return 0
    state = final_state.get("state") or {}
    buildings = state.get("bld") or []
    roads = state.get("rds") or []
    return len(buildings) + len(roads)


def _read_session_metadata(session_dir: Path) -> Dict[str, Any]:
    metadata_file = session_dir / "session_metadata.json"
    if not metadata_file.exists():
        return {}
    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _write_session_metadata(session_dir: Path, updates: Dict[str, Any]) -> None:
    metadata = _read_session_metadata(session_dir)
    metadata.update(updates)
    (session_dir / "session_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _most_common_response_models(session_dir: Path) -> Dict[str, str]:
    models_by_player: Dict[str, Counter] = {}
    for response_file in session_dir.glob("*/responses/response_*.json"):
        try:
            data = json.loads(response_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        player_name = str(data.get("player_name") or response_file.parent.parent.name)
        model_name = str(data.get("model") or "").strip()
        if not player_name or not model_name:
            continue
        models_by_player.setdefault(player_name, Counter())[model_name] += 1
    return {
        player_name: counter.most_common(1)[0][0]
        for player_name, counter in models_by_player.items()
        if counter
    }


def _sample_prompt_docs(session_dir: Path, limit: int = 12) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for prompt_file in sorted(session_dir.glob("*/prompts/prompt_*.json"))[:limit]:
        try:
            data = json.loads(prompt_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            docs.append(data)
    return docs


def _infer_victory_points_from_prompts(session_dir: Path) -> Optional[int]:
    for prompt_doc in _sample_prompt_docs(session_dir):
        prompt = prompt_doc.get("prompt") or {}
        meta_data = prompt.get("meta_data") or {}
        game_context = str(meta_data.get("game_context") or "")
        match = re.search(r"to\s+(\d+)\s+victory points", game_context, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
        game_state = str(prompt.get("game_state") or "")
        match = re.search(r'"vp_to_win"\s*:\s*(\d+)', game_state)
        if match:
            return int(match.group(1))
    return None


def _infer_chat_language_from_prompts(session_dir: Path) -> Optional[str]:
    for prompt_doc in _sample_prompt_docs(session_dir):
        prompt = prompt_doc.get("prompt") or {}
        task_context = prompt.get("task_context") or {}
        instructions = str(task_context.get("instructions") or "")
        if "Hebrew" in instructions or "עברית" in instructions or "׳¢׳‘׳¨" in instructions:
            return "hebrew"
        if "English" in instructions:
            return "english"
    return None


def _infer_relationship_mode_from_prompts(session_dir: Path) -> Optional[str]:
    for prompt_doc in _sample_prompt_docs(session_dir):
        prompt = prompt_doc.get("prompt") or {}
        meta_data = prompt.get("meta_data") or {}
        relationship_context = str(meta_data.get("relationship_context") or "")
        if not relationship_context:
            continue
        lowered = relationship_context.lower()
        if "represents gemini" in lowered or "represents claude" in lowered or "represents gpt" in lowered:
            return "ai_models"
        if "relationship context" in lowered:
            return "legacy"
    return None


def _public_run_settings(
    settings: Dict[str, Any],
    player_configs: List[Dict[str, Any]],
    *,
    source: str,
) -> Dict[str, Any]:
    """Build a redacted settings snapshot suitable for session_metadata.json."""
    players = []
    for index, player in enumerate(player_configs):
        llm = player.get("llm") or {}
        model_name = llm.get("model_name") or ""
        players.append({
            "slot": index + 1,
            "name": player.get("name", ""),
            "color": player.get("color", PLAYER_COLORS[index] if index < len(PLAYER_COLORS) else ""),
            "is_ai": bool(player.get("is_ai", True)),
            "llm": {
                "provider": llm.get("provider") or "openrouter",
                "model_provider": llm.get("model_provider") or provider_from_model_id(model_name),
                "model_name": model_name,
                "api_key_env_var": llm.get("api_key_env_var") or "OPENROUTER_API_KEY",
            },
        })
    return {
        "source": source,
        "run_mode": settings.get("run_mode"),
        "player_count": len(player_configs),
        "players": players,
        "llm": {
            "provider": "openrouter",
            "api_key_env_var": "OPENROUTER_API_KEY",
        },
        "chat_language": settings.get("chat_language"),
        "relationship_context_mode": settings.get("relationship_context_mode"),
        "no_llm": bool(settings.get("no_llm")),
        "reactions": {
            "mode": settings.get("reaction_mode"),
            "batch_size": settings.get("reaction_batch_size"),
        },
        "victory_points": settings.get("victory_points"),
        "game_context": settings.get("game_context", ""),
        "random_seed": settings.get("random_seed"),
        "config_path": settings.get("config_path"),
        "replay": {
            "session": settings.get("replay_session"),
            "max_decisions": settings.get("replay_max_decisions"),
            "through": settings.get("replay_through"),
            "stop_before": settings.get("replay_stop_before"),
            "skip_chat": bool(settings.get("replay_skip_chat")),
            "delay": settings.get("replay_delay"),
            "text_lead": settings.get("replay_text_lead"),
            "speak": bool(settings.get("replay_speak")),
        },
        "tts": settings.get("tts") or {},
    }


def write_run_settings_metadata(
    session_dir: Path,
    settings: Dict[str, Any],
    player_configs: List[Dict[str, Any]],
    *,
    source: str,
) -> None:
    """Persist redacted run settings to the new session metadata."""
    try:
        _write_session_metadata(
            session_dir,
            {"run_settings": _public_run_settings(settings, player_configs, source=source)},
        )
    except Exception as exc:
        print(f"[SETUP] Could not write run settings metadata: {exc}")


def infer_session_run_settings(session_dir: Path) -> Dict[str, Any]:
    """Return stored run settings, falling back to best-effort inference from old sessions."""
    metadata = _read_session_metadata(session_dir)
    stored = metadata.get("run_settings")
    if isinstance(stored, dict) and stored:
        return {**stored, "inferred": False}

    player_names = _infer_session_player_names(session_dir)
    model_by_player = _most_common_response_models(session_dir)
    players = []
    for index, name in enumerate(player_names[:4]):
        model_name = model_by_player.get(name, "")
        players.append({
            "slot": index + 1,
            "name": name,
            "color": PLAYER_COLORS[index],
            "is_ai": True,
            "llm": {
                "provider": "openrouter" if model_name else "",
                "model_provider": provider_from_model_id(model_name) if model_name else "",
                "model_name": model_name,
                "api_key_env_var": "OPENROUTER_API_KEY",
            },
        })

    return {
        "source": "inferred_from_session_logs",
        "inferred": True,
        "run_mode": None,
        "player_count": len(players) or None,
        "players": players,
        "llm": {
            "provider": "openrouter",
            "api_key_env_var": "OPENROUTER_API_KEY",
        },
        "chat_language": _infer_chat_language_from_prompts(session_dir),
        "relationship_context_mode": _infer_relationship_mode_from_prompts(session_dir),
        "no_llm": False,
        "reactions": {
            "mode": None,
            "batch_size": None,
        },
        "victory_points": _infer_victory_points_from_prompts(session_dir),
        "game_context": "",
        "random_seed": None,
        "config_path": None,
        "replay": {},
        "tts": metadata.get("tts") or metadata.get("tts_cache") or {},
    }


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

        def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
            body_bytes = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)

        def do_GET(self):
            parsed_url = urlparse(self.path)
            if parsed_url.path == "/healthz":
                self._send_json({"ok": True})
                return

            if parsed_url.path == "/replay-markers":
                query = parse_qs(parsed_url.query)
                session_ref = query.get("session", [""])[0].strip()
                if not session_ref:
                    self._send_json({"markers": []})
                    return
                try:
                    session_dir = resolve_session_path(session_ref)
                    markers = list_replay_marker_options(session_dir)
                except Exception as exc:
                    self._send_json({"error": str(exc), "markers": []}, status=400)
                    return
                self._send_json({"markers": markers})
                return

            if parsed_url.path == "/session-players":
                query = parse_qs(parsed_url.query)
                session_ref = query.get("session", [""])[0].strip()
                if not session_ref:
                    self._send_json({"players": []})
                    return
                try:
                    session_dir = resolve_session_path(session_ref)
                    players = _infer_session_player_names(session_dir)
                except Exception as exc:
                    self._send_json({"error": str(exc), "players": []}, status=400)
                    return
                self._send_json({"players": players})
                return

            if parsed_url.path == "/session-settings":
                query = parse_qs(parsed_url.query)
                session_ref = query.get("session", [""])[0].strip()
                if not session_ref:
                    self._send_json({"players": []})
                    return
                try:
                    session_dir = resolve_session_path(session_ref)
                    session_settings = infer_session_run_settings(session_dir)
                except Exception as exc:
                    self._send_json({"error": str(exc), "players": []}, status=400)
                    return
                self._send_json(session_settings)
                return

            if parsed_url.path == "/":
                self._send_html(render_landing_page())
                return

            if parsed_url.path != "/settings":
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return

            selected = _settings_selection_from_query(parse_qs(parsed_url.query))
            self._send_html(render_settings_page(models, key_mode, selected=selected))

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

            api_key = fields.get("openrouter_api_key") or (os.environ.get("OPENROUTER_API_KEY", "") if use_env_keys else "")
            if live_mode and not no_llm and not api_key:
                errors.append("Enter an OpenRouter API key or set OPENROUTER_API_KEY.")

            replay_session = fields.get("replay_session", "")
            if run_mode != "new_game" and not replay_session:
                errors.append("Choose a recorded session for replay/resume/analyse mode.")
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
                        f"{exc}. Choose one of the suggested response markers."
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
                        f"already contains at least {minimum_actions} placements. Choose a session with "
                        "full response logs or use replay markers for a partial replay."
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

            replay_max_decisions = _parse_optional_int(fields.get("replay_max_decisions", ""), errors, "Replay max responses")
            replay_delay = _parse_float(fields.get("replay_delay", "2.5"), 2.5, errors, "Replay delay")
            replay_text_lead = _parse_float(fields.get("replay_text_lead", "0.25"), 0.25, errors, "Replay text lead")

            reaction_mode = fields.get("reaction_mode", "default")
            if reaction_mode not in {"default", "off", "sync", "async"}:
                errors.append("Choose a valid reaction mode.")
            relationship_context_mode = fields.get("relationship_context_mode", "legacy")
            valid_relationship_modes = {value for value, _label in RELATIONSHIP_CONTEXT_MODES}
            if relationship_context_mode not in valid_relationship_modes:
                errors.append("Choose a valid relationship context mode.")
                relationship_context_mode = "legacy"
            reaction_batch_size = _parse_optional_int(fields.get("reaction_batch_size", ""), errors, "Reaction batch size")
            victory_points = _parse_optional_int(fields.get("victory_points", "5"), errors, "Victory points") or 5
            fields["victory_points"] = str(victory_points)
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
            gemini_api_key = fields.get("gemini_api_key") or (os.environ.get("GEMINI_API_KEY", "") if use_env_keys else "")
            elevenlabs_api_key = fields.get("elevenlabs_api_key") or (os.environ.get("ELEVENLABS_API_KEY", "") if use_env_keys else "")
            elevenlabs_voice_id = fields.get("elevenlabs_default_voice_id") or (os.environ.get("ELEVENLABS_DEFAULT_VOICE_ID", "") if use_env_keys else "")
            needs_voice = live_mode or replay_speak
            if tts_provider == "gemini" and needs_voice and not gemini_api_key:
                errors.append("Enter a Gemini API key for Gemini TTS or set GEMINI_API_KEY.")
            if tts_provider == "elevenlabs" and needs_voice:
                if not elevenlabs_api_key:
                    errors.append("Enter an ElevenLabs API key or set ELEVENLABS_API_KEY.")
                if not elevenlabs_voice_id:
                    errors.append("Enter an ElevenLabs default voice ID or set ELEVENLABS_DEFAULT_VOICE_ID.")

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
                self._send_html(render_settings_page(models, key_mode, errors=errors, selected=fields), status=400)
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
            elif tts_provider == "elevenlabs":
                os.environ["TTS_PROVIDER"] = "elevenlabs"
                os.environ["ELEVENLABS_TTS_ENABLED"] = "true"
                os.environ["ELEVENLABS_API_KEY"] = elevenlabs_api_key
                os.environ["ELEVENLABS_DEFAULT_VOICE_ID"] = elevenlabs_voice_id
                os.environ["ELEVENLABS_TTS_MODEL_ID"] = fields.get("elevenlabs_tts_model", "eleven_v3")
                os.environ.setdefault("ELEVENLABS_TTS_OUTPUT_FORMAT", "pcm_16000")
                os.environ.setdefault("ELEVENLABS_TTS_PLAY_AUDIO", "true")
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
                    "elevenlabs_model": fields.get("elevenlabs_tts_model", "eleven_v3"),
                    "key_source": "env_or_redacted" if tts_provider != "off" else "off",
                },
            })
            starting_players = player_configs if run_mode == "new_game" else [
                {"name": replay_session or "recorded session", "llm": {"model_name": run_mode}}
            ]
            self._send_html(render_starting_page(starting_players, run_mode))
            ready.set()

    bind_host = os.environ.get("PYCATAN_BIND_HOST", "127.0.0.1")
    public_host = os.environ.get("PYCATAN_PUBLIC_HOST", "localhost")
    server = ReusableThreadingHTTPServer((bind_host, port), SettingsHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://{public_host}:{port}/settings"
    print(f"[SETUP] OpenRouter settings page: {url}")
    if os.environ.get("PYCATAN_NO_BROWSER", "").lower() not in {"1", "true", "yes", "on"}:
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"[SETUP] Could not open browser automatically: {exc}")
    print("[SETUP] Waiting for OpenRouter settings...")
    try:
        while not ready.wait(timeout=0.25):
            pass
    finally:
        server.shutdown()
        server.server_close()
    return settings


def _player_configs_for_replay(player_names: List[str], slot_llms: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    configs = []
    for index, name in enumerate(player_names[:4]):
        llm = slot_llms[index] if index < len(slot_llms) else slot_llms[-1]
        configs.append({"name": name, "is_ai": True, "color": PLAYER_COLORS[index], "llm": llm})
    return configs


def _apply_reaction_settings(ai_config, settings: Dict[str, Any]) -> None:
    reaction_mode = settings["reaction_mode"]
    if reaction_mode == "off":
        ai_config.agent.enable_reactions = False
    elif reaction_mode == "async":
        ai_config.agent.enable_reactions = True
        ai_config.agent.async_reactions = True
    elif reaction_mode == "sync":
        ai_config.agent.enable_reactions = True
        ai_config.agent.async_reactions = False
    if settings["reaction_batch_size"] is not None:
        ai_config.agent.reaction_max_batch_messages = settings["reaction_batch_size"]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Play Catan with per-agent OpenRouter models")
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
        action_count = sum(1 for item in replay_decision_list if item.get("has_action"))
        print(f"[REPLAY] Loaded {len(replay_decision_list)} parsed responses ({action_count} actions)")
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
    if settings.get("game_context"):
        print("[CONFIG] Additional game context enabled")
    print("[CONFIG] OpenRouter per-agent models")
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
        source="play_with_openrouter",
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
            replay_events=replay_decision_list,
        )
    else:
        run_game(game_manager, ai_manager, web_viz)


if __name__ == "__main__":
    main()
