"""
Utilities for reconstructing an AI decision trace from a logged game session.

The analyzer intentionally works from files already written by older sessions:
prompt_N.json, response_N.json, intermediate tool-call responses, optional
tool follow-up prompts, and tool_executions.json.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def build_decision_analysis(
    source_session: Path,
    decision: Dict[str, Any],
    action_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a human-readable decision trace for one replay decision."""
    session_dir = _resolve_session_for_decision(source_session, decision)
    player_name = str(decision.get("player_name") or "")
    request_number = int(decision.get("request_number") or 0)

    prompt_doc = _load_prompt(session_dir, player_name, request_number)
    response_doc = _load_response(session_dir, player_name, request_number)
    if not isinstance(prompt_doc, dict):
        prompt_doc = {}
    if not isinstance(response_doc, dict):
        response_doc = {}
    parsed = (
        copy.deepcopy(response_doc.get("parsed"))
        if isinstance(response_doc, dict) and isinstance(response_doc.get("parsed"), dict)
        else copy.deepcopy(decision.get("parsed") or {})
    )

    prompt = prompt_doc.get("prompt") if isinstance(prompt_doc, dict) else {}
    if not isinstance(prompt, dict):
        prompt = {}

    tool_trace = _load_tool_trace(session_dir, player_name, request_number)
    memory_before = copy.deepcopy(prompt.get("memory") or {})
    social_context = copy.deepcopy(prompt.get("social_context") or {})
    constraints = copy.deepcopy(prompt.get("constraints") or {})
    allowed_actions = copy.deepcopy(prompt_doc.get("allowed_actions") or constraints.get("allowed_actions") or [])
    compact_state_text = prompt.get("game_state") or ""
    compact_state_json = _extract_embedded_json(compact_state_text)
    observed_facts = _build_observed_facts(
        compact_state_json,
        allowed_actions,
        prompt.get("task_context") or {},
    )

    action_type = parsed.get("action_type") or (parsed.get("action") or {}).get("type")
    action_parameters = parsed.get("parameters")
    if action_parameters is None and isinstance(parsed.get("action"), dict):
        action_parameters = parsed["action"].get("parameters")

    return {
        "available": bool(prompt_doc or response_doc or parsed),
        "session": session_dir.name if session_dir else "",
        "session_path": str(session_dir) if session_dir else "",
        "player_name": player_name,
        "request_number": request_number,
        "timestamp": (
            response_doc.get("timestamp")
            or prompt_doc.get("timestamp")
            or decision.get("timestamp")
            or ""
        ),
        "label": f"{player_name} #{request_number}: {action_type or 'decision'}",
        "worldview": {
            "task_context": copy.deepcopy(prompt.get("task_context") or {}),
            "memory_before": memory_before,
            "social_context": social_context,
            "constraints": constraints,
            "compact_game_state": compact_state_text,
            "compact_game_state_json": compact_state_json,
            "observed_facts": observed_facts,
            "allowed_actions": allowed_actions,
        },
        "tool_trace": tool_trace,
        "thinking": parsed.get("internal_thinking") or "",
        "memory_write": parsed.get("note_to_self") or "",
        "say_outloud": parsed.get("say_outloud") or "",
        "action": {
            "type": action_type,
            "parameters": action_parameters,
        },
        "engine_result": copy.deepcopy(action_result or {}),
        "raw": {
            "prompt": prompt_doc,
            "response": response_doc,
        },
    }


def build_turn_flow(
    source_session: Path,
    decisions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build lightweight summaries for every decision in the selected turn."""
    flow: List[Dict[str, Any]] = []
    for item in decisions:
        decision = item.get("decision") or {}
        action_result = item.get("action_result") or {}
        parsed = decision.get("parsed") or {}
        action_type = parsed.get("action_type") or (parsed.get("action") or {}).get("type")
        response_doc = _load_response(
            _resolve_session_for_decision(source_session, decision),
            str(decision.get("player_name") or ""),
            int(decision.get("request_number") or 0),
        )
        if isinstance(response_doc.get("parsed"), dict):
            parsed = response_doc["parsed"]
            action_type = parsed.get("action_type") or (parsed.get("action") or {}).get("type")

        flow.append({
            "snapshot_index": item.get("snapshot_index"),
            "label": item.get("label") or "",
            "player_name": decision.get("player_name") or "",
            "request_number": decision.get("request_number") or 0,
            "action_type": action_type,
            "say_outloud": parsed.get("say_outloud") or "",
            "memory_write": parsed.get("note_to_self") or "",
            "success": action_result.get("success"),
            "message": action_result.get("message") or "",
            "turn_number": action_result.get("turn_number"),
        })
    return flow


def _load_tool_trace(session_dir: Path, player_name: str, request_number: int) -> List[Dict[str, Any]]:
    intermediate_responses = _load_intermediate_responses(session_dir, player_name, request_number)
    followups = _load_tool_followups(session_dir, player_name, request_number)
    execution_batches = _load_tool_executions(session_dir)
    used_batch_indexes: set[int] = set()
    trace = []

    for intermediate in intermediate_responses:
        iteration = int(intermediate.get("iteration") or 0)
        tool_calls = copy.deepcopy(intermediate.get("tool_calls") or [])
        followup = next((item for item in followups if int(item.get("iteration") or 0) == iteration), {})
        batch_index = _match_tool_execution_batch(
            execution_batches,
            intermediate,
            tool_calls,
            used_batch_indexes,
        )
        batch = execution_batches[batch_index] if batch_index is not None else {}
        if batch_index is not None:
            used_batch_indexes.add(batch_index)

        trace.append({
            "iteration": iteration,
            "timestamp": intermediate.get("timestamp") or followup.get("timestamp") or batch.get("timestamp") or "",
            "tool_calls": tool_calls,
            "tool_results_text": followup.get("tool_results") or _format_batch_results(batch),
            "execution_batch": batch,
            "followup_context_available": bool(followup.get("full_context_sent")),
            "full_context_sent": followup.get("full_context_sent") or "",
        })

    for followup in followups:
        iteration = int(followup.get("iteration") or 0)
        if any(item["iteration"] == iteration for item in trace):
            continue
        trace.append({
            "iteration": iteration,
            "timestamp": followup.get("timestamp") or "",
            "tool_calls": [],
            "tool_results_text": followup.get("tool_results") or "",
            "execution_batch": {},
            "followup_context_available": bool(followup.get("full_context_sent")),
            "full_context_sent": followup.get("full_context_sent") or "",
        })

    trace.sort(key=lambda item: item.get("iteration") or 0)
    return trace


def _resolve_session_for_decision(source_session: Path, decision: Dict[str, Any]) -> Path:
    absolute_source_file = decision.get("absolute_source_file")
    if absolute_source_file:
        response_path = Path(absolute_source_file)
        if response_path.exists():
            return response_path.parent.parent.parent

    source_file = decision.get("source_file")
    if source_file:
        response_path = Path(source_file)
        if response_path.exists():
            return response_path.parent.parent.parent
    return Path(source_session)


def _player_dir(session_dir: Path, player_name: str) -> Optional[Path]:
    direct = session_dir / player_name
    if direct.exists():
        return direct
    wanted = player_name.lower()
    for child in session_dir.iterdir() if session_dir.exists() else []:
        if child.is_dir() and child.name.lower() == wanted:
            return child
    return None


def _load_prompt(session_dir: Path, player_name: str, request_number: int) -> Dict[str, Any]:
    player_dir = _player_dir(session_dir, player_name)
    if not player_dir:
        return {}
    return _read_json(player_dir / "prompts" / f"prompt_{request_number}.json")


def _load_response(session_dir: Path, player_name: str, request_number: int) -> Dict[str, Any]:
    player_dir = _player_dir(session_dir, player_name)
    if not player_dir:
        return {}
    return _read_json(player_dir / "responses" / f"response_{request_number}.json")


def _load_intermediate_responses(session_dir: Path, player_name: str, request_number: int) -> List[Dict[str, Any]]:
    player_dir = _player_dir(session_dir, player_name)
    if not player_dir:
        return []
    intermediate_dir = player_dir / "responses" / "intermediate"
    items = []
    for path in sorted(intermediate_dir.glob(f"response_{request_number}_iter*.json")):
        data = _read_json(path)
        if data:
            items.append(data)
    return items


def _load_tool_followups(session_dir: Path, player_name: str, request_number: int) -> List[Dict[str, Any]]:
    player_dir = _player_dir(session_dir, player_name)
    if not player_dir:
        return []
    iterations_dir = player_dir / "prompts" / "iterations"
    items = []
    for path in sorted(iterations_dir.glob(f"prompt_{request_number}_iter*.json")):
        data = _read_json(path)
        if data:
            items.append(data)
    return items


def _load_tool_executions(session_dir: Path) -> List[Dict[str, Any]]:
    data = _read_json(session_dir / "tool_executions.json")
    return data if isinstance(data, list) else []


def _match_tool_execution_batch(
    batches: List[Dict[str, Any]],
    intermediate: Dict[str, Any],
    tool_calls: List[Dict[str, Any]],
    used_batch_indexes: set[int],
) -> Optional[int]:
    expected_names = [str(call.get("name") or "") for call in tool_calls]
    intermediate_ts = _parse_timestamp(intermediate.get("timestamp"))
    best_index = None
    best_delta = None

    for index, batch in enumerate(batches):
        if index in used_batch_indexes:
            continue
        batch_names = [str(call.get("name") or "") for call in batch.get("calls") or []]
        if expected_names and batch_names[: len(expected_names)] != expected_names:
            continue
        batch_ts = _parse_timestamp(batch.get("timestamp"))
        if intermediate_ts and batch_ts and batch_ts < intermediate_ts:
            continue
        delta = (
            (batch_ts - intermediate_ts).total_seconds()
            if intermediate_ts and batch_ts
            else float(index)
        )
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_index = index

    return best_index


def _format_batch_results(batch: Dict[str, Any]) -> str:
    calls = batch.get("calls") or []
    if not calls:
        return ""
    lines = ["=== Tool Results ===\n"]
    for call in calls:
        lines.append(f"Tool: {call.get('name', '')}")
        lines.append(f"Parameters: {json.dumps(call.get('parameters') or {}, indent=2, ensure_ascii=False)}")
        if call.get("success", True):
            lines.append("Result:")
            lines.append(json.dumps(call.get("result"), indent=2, ensure_ascii=False))
        else:
            lines.append(f"Error: {call.get('error') or ''}")
        lines.append("---\n")
    return "\n".join(lines)


def _extract_embedded_json(text: str) -> Optional[Dict[str, Any]]:
    marker = "JSON:"
    if not isinstance(text, str) or marker not in text:
        return None
    candidate = text.split(marker, 1)[1].strip()
    try:
        return json.loads(candidate)
    except Exception:
        return None


def _build_observed_facts(
    compact_state: Optional[Dict[str, Any]],
    allowed_actions: List[Dict[str, Any]],
    task_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract the high-signal facts that were visible in compact game_state."""
    if not isinstance(compact_state, dict):
        return {
            "expected_action": _expected_action_from_allowed(allowed_actions),
            "prompt_warnings": _prompt_consistency_warnings(allowed_actions, task_context),
        }

    meta = compact_state.get("meta") or {}
    dice = meta.get("dice")
    dice_total = sum(dice) if isinstance(dice, list) and all(isinstance(x, (int, float)) for x in dice) else None
    current_player = meta.get("curr")
    players = compact_state.get("players") or {}
    current_player_state = (
        copy.deepcopy(players.get(current_player) or {})
        if current_player is not None and isinstance(players, dict)
        else {}
    )

    return {
        "current_player": current_player,
        "phase": meta.get("phase"),
        "robber_hex": meta.get("robber"),
        "dice": dice,
        "dice_total": dice_total,
        "expected_action": _expected_action_from_allowed(allowed_actions),
        "prompt_warnings": _prompt_consistency_warnings(allowed_actions, task_context),
        "current_player_state": current_player_state,
        "players": copy.deepcopy(players) if isinstance(players, dict) else {},
    }


def _allowed_types(allowed_actions: List[Dict[str, Any]]) -> set[str]:
    result = set()
    for action in allowed_actions or []:
        if isinstance(action, dict):
            value = action.get("type")
        else:
            value = str(action)
        if value:
            result.add(str(value).lower())
    return result


def _expected_action_from_allowed(allowed_actions: List[Dict[str, Any]]) -> str:
    allowed = _allowed_types(allowed_actions)
    if "roll_dice" in allowed and allowed <= {"roll_dice", "use_dev_card"}:
        if "use_dev_card" in allowed:
            return "Start the turn: roll dice, or optionally use a development card before rolling."
        return "Start the turn: roll dice."
    if {"build_settlement", "build_city", "build_road", "trade_propose", "trade_bank", "buy_dev_card", "end_turn"} & allowed:
        return "Post-roll actions: build, trade, buy/use development card, or end turn."
    if allowed:
        return "Allowed now: " + ", ".join(sorted(allowed))
    return ""


def _prompt_consistency_warnings(
    allowed_actions: List[Dict[str, Any]],
    task_context: Dict[str, Any],
) -> List[str]:
    allowed = _allowed_types(allowed_actions)
    what_happened = str((task_context or {}).get("what_just_happened") or "").lower()
    warnings = []
    if "roll_dice" in allowed and allowed <= {"roll_dice", "use_dev_card"}:
        if "build, trade, or end" in what_happened:
            warnings.append(
                "The prompt text says build/trade/end, but the allowed actions show this is a pre-roll decision."
            )
    return warnings


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _read_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}
