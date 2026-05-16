"""
Memory compaction for AI agents.

The compactor uses the same compact board representation that regular prompts use:
H/N lookup arrays, state.bld/state.rds, players, and meta with the embedded legend.
"""

import json
import re
from typing import Any, Dict, List, Optional

from pycatan.ai.agent_state import AgentState
from pycatan.ai.config import AIConfig
from pycatan.ai.llm_client import LLMResponse, LLMClient
from pycatan.ai.prompt_templates import PromptBuilder


COMPACTION_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["compacted_memory", "recent_notes_to_keep"],
    "properties": {
        "compacted_memory": {
            "type": "string",
            "description": "Dense long-term strategic memory for future Catan decisions.",
        },
        "recent_notes_to_keep": {
            "type": "array",
            "description": "The newest recent notes, copied verbatim from input.",
            "items": {"type": "string"},
        },
        "discarded_as_irrelevant": {
            "type": "array",
            "description": "Short categories of information removed.",
            "items": {"type": "string"},
        },
        "relationship_updates": {
            "type": "array",
            "description": "New concise relationship shifts for future table talk, trust, trades, and tie-breakers. Empty if nothing changed.",
            "items": {"type": "string", "maxLength": 120},
        },
    },
    "propertyOrdering": [
        "compacted_memory",
        "recent_notes_to_keep",
        "relationship_updates",
        "discarded_as_irrelevant",
    ],
}


class MemoryCompactor:
    """Build and send compact-memory prompts for one agent at a time."""

    FALLBACK_SUMMARY_MAX_CHARS = 1800
    FALLBACK_KEEP_NOTES = 10
    STRATEGIC_KEYWORDS = (
        "win", "victory", "vp", "point", "need", "needs", "missing",
        "target", "goal", "priority", "plan", "next", "settlement",
        "city", "road", "port", "trade", "robber", "block", "ore",
        "brick", "wood", "sheep", "wheat",
        "ניצ", "נקוד", "צריך", "צריכה", "חסר", "מטרה", "יעד",
        "יישוב", "עיר", "דרך", "נמל", "סחר", "שודד", "לחסום",
        "טיט", "עץ", "כבש", "חיטה", "אבן",
    )

    def __init__(self, config: AIConfig):
        self.config = config
        self.prompt_builder = PromptBuilder()

    def should_compact(self, agent: AgentState) -> bool:
        """Return whether this agent has enough recent notes to compact."""
        memory_config = self.config.memory
        if not getattr(memory_config, "enable_memory_compaction", True):
            return False
        threshold = getattr(memory_config, "memory_compaction_threshold", 10)
        keep_recent = getattr(memory_config, "memory_compaction_keep_recent", 2)
        return len(agent.memory_history) >= max(threshold, keep_recent + 1)

    def compact(
        self,
        agent: AgentState,
        game_state: Dict[str, Any],
        chat_history: List[Dict[str, Any]],
        llm_client: LLMClient,
    ) -> Optional[Dict[str, Any]]:
        """
        Compact old agent memories with the current compact board state.

        Returns:
            Dict with compacted_memory and bookkeeping fields, or None on failure.
        """
        memory_config = self.config.memory
        keep_count = getattr(memory_config, "memory_compaction_keep_recent", 2)
        chat_limit = getattr(memory_config, "memory_compaction_chat_messages", 20)

        recent_entries = agent.memory_history[-keep_count:]
        old_entries = agent.memory_history[:-keep_count]
        if not old_entries:
            return None

        prompt = self._build_prompt(
            agent=agent,
            game_state=game_state,
            old_notes=old_entries,
            recent_notes=recent_entries,
            chat_history=self._relevant_chat(agent.player_name, chat_history, chat_limit),
        )

        try:
            response = llm_client.generate(
                json.dumps(prompt, ensure_ascii=False, indent=2),
                response_schema=COMPACTION_RESPONSE_SCHEMA,
                response_format="json",
                tools=[],
                enable_thinking=False,
                max_tokens=getattr(memory_config, "memory_compaction_max_tokens", 800),
            )
        except Exception as exc:
            response = LLMResponse(
                success=False,
                error=str(exc),
                model=getattr(llm_client, "model", ""),
            )

        relevant_chat = self._relevant_chat(agent.player_name, chat_history, chat_limit)
        parsed = self._parse_response(response)
        if parsed is None:
            return self._fallback_result(
                agent=agent,
                old_entries=old_entries,
                recent_entries=recent_entries,
                relevant_chat=relevant_chat,
                prompt=prompt,
                response=response,
                reason=self._fallback_reason(response, "unparseable_response"),
            )

        raw_compacted_memory = parsed.get("compacted_memory", "")
        compacted_memory = (
            raw_compacted_memory.strip()
            if isinstance(raw_compacted_memory, str)
            else ""
        )
        if not compacted_memory:
            return self._fallback_result(
                agent=agent,
                old_entries=old_entries,
                recent_entries=recent_entries,
                relevant_chat=relevant_chat,
                prompt=prompt,
                response=response,
                reason="empty_compacted_memory",
            )

        return {
            "compacted_memory": compacted_memory,
            "existing_compacted_memory": agent.compacted_memory,
            "existing_relationship_updates": agent.relationship_context_updates,
            "old_entries": old_entries,
            "recent_entries": recent_entries,
            "recent_notes_to_keep": parsed.get("recent_notes_to_keep", []),
            "fallback_used": False,
            "fallback_reason": None,
            "relationship_updates": self._clean_relationship_updates(
                parsed.get("relationship_updates", []),
                agent.relationship_context_updates,
            ),
            "discarded_as_irrelevant": parsed.get("discarded_as_irrelevant", []),
            "relevant_chat": relevant_chat,
            "prompt": prompt,
            "response": response,
        }

    def _build_prompt(
        self,
        agent: AgentState,
        game_state: Dict[str, Any],
        old_notes: List[Dict[str, Any]],
        recent_notes: List[Dict[str, Any]],
        chat_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        old_note_texts = [entry.get("note", str(entry)) for entry in old_notes]
        recent_note_texts = [entry.get("note", str(entry)) for entry in recent_notes]

        return {
            "meta_data": {
                "agent_name": agent.player_name,
                "task": "compact_agent_memory",
                "model_instruction": (
                    "You are compacting memory for one Catan AI agent. "
                    "Use the board only through the same compact H/N/state/players/meta format "
                    "used in normal decision prompts."
                ),
            },
            "task_context": {
                "instructions": (
                    "Compress old memories and relevant chat into one concise strategic memory. "
                    "Preserve future-useful facts: current goals, next planned actions, confirmed board facts, "
                    "known or likely opponent plans/resources/dev cards/trade tendencies, active negotiations, "
                    "social commitments, and mistakes to avoid. Discard repeated, completed, impossible, vague, "
                    "or superseded details. Do not invent facts; mark uncertainty clearly. "
                    "Also extract only new meaningful relationship shifts from the old notes and relevant chat: "
                    "trust changes, grudges, favors, threats, betrayals, promises, or emotional tension. "
                    "Do not repeat existing relationship updates; leave relationship_updates empty if nothing changed. "
                    "Target about 50% or less of the combined old memory length. "
                    "Keep recent_notes_to_keep copied verbatim from the provided recent notes."
                )
            },
            "game_state": self.prompt_builder._build_game_state_section(game_state),
            "memory_input": {
                "existing_compacted_memory": agent.compacted_memory,
                "existing_relationship_updates": agent.relationship_context_updates,
                "old_notes_to_compact": old_note_texts,
                "recent_notes_to_keep": recent_note_texts,
                "relevant_chat": chat_history,
            },
            "output_requirements": {
                "format": "valid JSON only",
                "schema": {
                    "compacted_memory": "string",
                    "recent_notes_to_keep": ["string"],
                    "relationship_updates": ["string"],
                    "discarded_as_irrelevant": ["string"],
                },
            },
        }

    def _clean_relationship_updates(
        self,
        updates: Any,
        existing_updates: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Return compact unique relationship updates from a model response."""
        if not isinstance(updates, list):
            return []

        result = []
        seen = {
            str(update.get("note", "")).strip().lower()
            for update in existing_updates or []
            if isinstance(update, dict) and update.get("note")
        }
        for update in updates:
            text = str(update).strip()
            if not text:
                continue
            text = re.sub(r"\s+", " ", text)[:120].strip()
            key = text.lower()
            if key in seen:
                continue
            result.append(text)
            seen.add(key)
            if len(result) >= 3:
                break
        return result

    def _relevant_chat(
        self,
        player_name: str,
        chat_history: List[Dict[str, Any]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Keep recent table talk, prioritizing messages involving this player."""
        if not chat_history:
            return []

        recent = chat_history[-limit:]
        player_lower = player_name.lower()
        relevant = [
            msg
            for msg in recent
            if msg.get("from") == player_name
            or player_lower in str(msg.get("message", "")).lower()
        ]

        combined = relevant + [msg for msg in recent if msg not in relevant]
        return combined[-limit:]

    def _parse_response(self, response: LLMResponse) -> Optional[Dict[str, Any]]:
        if not response.success or not response.content:
            return None

        content = response.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    def _fallback_reason(self, response: LLMResponse, default: str) -> str:
        if not response.success:
            return f"llm_error: {response.error or 'unknown error'}"
        if not response.content:
            return "empty_response"
        return default

    def _fallback_result(
        self,
        agent: AgentState,
        old_entries: List[Dict[str, Any]],
        recent_entries: List[Dict[str, Any]],
        relevant_chat: List[Dict[str, Any]],
        prompt: Dict[str, Any],
        response: LLMResponse,
        reason: str,
    ) -> Optional[Dict[str, Any]]:
        compacted_memory = self._build_fallback_summary(agent, old_entries, relevant_chat)
        if not compacted_memory:
            return None

        return {
            "compacted_memory": compacted_memory,
            "existing_compacted_memory": agent.compacted_memory,
            "existing_relationship_updates": agent.relationship_context_updates,
            "old_entries": old_entries,
            "recent_entries": recent_entries,
            "recent_notes_to_keep": [entry.get("note", str(entry)) for entry in recent_entries],
            "fallback_used": True,
            "fallback_reason": reason,
            "relationship_updates": [],
            "discarded_as_irrelevant": ["fallback_compaction_kept_recent_strategic_notes"],
            "relevant_chat": relevant_chat,
            "prompt": prompt,
            "response": response,
        }

    def _build_fallback_summary(
        self,
        agent: AgentState,
        old_entries: List[Dict[str, Any]],
        relevant_chat: List[Dict[str, Any]],
    ) -> str:
        """Create a deterministic summary when the LLM compaction response is unusable."""
        selected = self._select_fallback_notes(old_entries)

        parts = []
        if agent.compacted_memory:
            parts.append(f"Previous long-term memory: {agent.compacted_memory.strip()}")
        if selected:
            parts.append("Strategic notes: " + " | ".join(selected))

        chat_lines = []
        for chat in relevant_chat[-3:]:
            speaker = str(chat.get("from", "?")).strip() or "?"
            message = re.sub(r"\s+", " ", str(chat.get("message", ""))).strip()
            if message:
                chat_lines.append(f"{speaker}: {message}")
        if chat_lines:
            parts.append("Recent table talk: " + " | ".join(chat_lines))

        summary = " ".join(part for part in parts if part).strip()
        if not summary:
            return ""
        return self._trim_text(summary, self.FALLBACK_SUMMARY_MAX_CHARS)

    def _select_fallback_notes(self, entries: List[Dict[str, Any]]) -> List[str]:
        texts = [
            re.sub(r"\s+", " ", str(entry.get("note", entry))).strip()
            for entry in entries
        ]
        texts = [text for text in texts if text]
        if not texts:
            return []

        selected = []
        seen = set()
        for text in reversed(texts):
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            if self._looks_strategic(text) or len(selected) < 3:
                selected.append(text)
            if len(selected) >= self.FALLBACK_KEEP_NOTES:
                break

        selected.reverse()
        return [self._trim_text(text, 260) for text in selected]

    def _looks_strategic(self, text: str) -> bool:
        lower = text.lower()
        return any(keyword in lower for keyword in self.STRATEGIC_KEYWORDS)

    def _trim_text(self, text: str, max_chars: int) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= max_chars:
            return text
        trimmed = text[: max_chars - 3].rstrip()
        last_break = max(trimmed.rfind(". "), trimmed.rfind("; "), trimmed.rfind(" | "))
        if last_break > max_chars * 0.65:
            trimmed = trimmed[: last_break + 1].rstrip()
        return trimmed + "..."
