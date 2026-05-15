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
from pycatan.ai.llm_client import LLMResponse, GeminiClient
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
    },
    "propertyOrdering": [
        "compacted_memory",
        "recent_notes_to_keep",
        "discarded_as_irrelevant",
    ],
}


class MemoryCompactor:
    """Build and send compact-memory prompts for one agent at a time."""

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
        llm_client: GeminiClient,
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

        response = llm_client.generate(
            json.dumps(prompt, ensure_ascii=False, indent=2),
            response_schema=COMPACTION_RESPONSE_SCHEMA,
            response_format="json",
            tools=[],
            enable_thinking=False,
            max_tokens=getattr(memory_config, "memory_compaction_max_tokens", 800),
        )
        parsed = self._parse_response(response)
        if parsed is None:
            return None

        compacted_memory = parsed.get("compacted_memory", "").strip()
        if not compacted_memory:
            return None

        return {
            "compacted_memory": compacted_memory,
            "existing_compacted_memory": agent.compacted_memory,
            "old_entries": old_entries,
            "recent_entries": recent_entries,
            "recent_notes_to_keep": parsed.get("recent_notes_to_keep", []),
            "discarded_as_irrelevant": parsed.get("discarded_as_irrelevant", []),
            "relevant_chat": self._relevant_chat(agent.player_name, chat_history, chat_limit),
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
                    "Target about 50% or less of the combined old memory length. "
                    "Keep recent_notes_to_keep copied verbatim from the provided recent notes."
                )
            },
            "game_state": self.prompt_builder._build_game_state_section(game_state),
            "memory_input": {
                "existing_compacted_memory": agent.compacted_memory,
                "old_notes_to_compact": old_note_texts,
                "recent_notes_to_keep": recent_note_texts,
                "relevant_chat": chat_history,
            },
            "output_requirements": {
                "format": "valid JSON only",
                "schema": {
                    "compacted_memory": "string",
                    "recent_notes_to_keep": ["string"],
                    "discarded_as_irrelevant": ["string"],
                },
            },
        }

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
