"""
Agent State Management for PyCatan AI Agents

This module defines the AgentState dataclass that holds all state information
for a single AI agent, including:
- Player identification
- Request tracking
- Memory and notes
- Event history
- Statistics

Each AI agent has its own AgentState instance managed by the AIManager.
"""

import time
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class AgentState:
    """
    State for a single AI agent.
    
    Manages all agent-specific data including memory, pending requests,
    recent events, and tracking information.
    
    Attributes:
        player_name: Display name of the player
        player_id: Unique player ID (0-based index)
        player_color: Color assigned to player (e.g., "Red", "Blue")
        pending_request: True if waiting for LLM response
        last_request_time: Timestamp of last request sent
        memory: Agent's note_to_self from last response
        chat_summaries: List of chat summary strings
        recent_events: Events since last prompt
        last_state_hash: Hash of game state at last prompt
        last_prompt_time: When last prompt was sent
        total_requests: Total API requests made
        total_tokens_used: Total tokens consumed
    """
    
    # === Identification ===
    player_name: str
    player_id: int
    player_color: str = ""
    
    # === Request Status ===
    pending_request: bool = False
    last_request_time: Optional[float] = None
    
    # === Memory ===
    memory: Optional[str] = None  # note_to_self from last response
    
    # === Chat Summaries (for future use) ===
    chat_summaries: List[str] = field(default_factory=list)
    
    # === Recent Events ===
    # Events that occurred since last prompt was sent
    # Each event: {"type": str, "message": str, "timestamp": float}
    recent_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # === Change Tracking ===
    last_state_hash: Optional[str] = None
    last_prompt_time: Optional[float] = None
    last_prompt_number: int = 0
    
    # === Statistics ===
    total_requests: int = 0
    total_tokens_used: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    def add_event(self, event_type: str, message: str, data: Optional[Dict] = None) -> None:
        """
        Add a new event to the agent's recent events.
        
        Args:
            event_type: Type of event (e.g., "dice_roll", "build", "trade")
            message: Human-readable description of the event
            data: Optional additional data about the event
        """
        event = {
            "type": event_type,
            "message": message,
            "timestamp": time.time()
        }
        if data:
            event["data"] = data
        self.recent_events.append(event)
    
    def clear_events(self) -> List[Dict[str, Any]]:
        """
        Clear recent events and return them.
        
        Returns:
            List of events that were cleared
        """
        events = self.recent_events.copy()
        self.recent_events = []
        return events
    
    def get_events_summary(self) -> str:
        """
        Generate a summary of recent events for prompt.
        
        Returns:
            Human-readable summary string of recent events
        """
        if not self.recent_events:
            return "No recent events."
        
        # Group events by type and create summary
        lines = []
        for event in self.recent_events:
            lines.append(f"- {event['message']}")
        
        return "\n".join(lines)
    
    def mark_request_sent(self) -> None:
        """Mark that a request has been sent to the LLM."""
        self.pending_request = True
        self.last_request_time = time.time()
        self.total_requests += 1
        self.last_prompt_number += 1
    
    def mark_request_complete(self, success: bool = True, tokens: int = 0) -> None:
        """
        Mark that a request has completed.
        
        Args:
            success: Whether the request was successful
            tokens: Number of tokens used in the request
        """
        self.pending_request = False
        self.total_tokens_used += tokens
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
    
    def update_memory(self, note_to_self: Optional[str]) -> None:
        """
        Update the agent's memory with a new note.
        
        Args:
            note_to_self: The new note to remember
        """
        if note_to_self:
            self.memory = note_to_self
    
    def update_state_hash(self, state_hash: str) -> bool:
        """
        Update the state hash and return whether it changed.
        
        Args:
            state_hash: New hash of the game state
            
        Returns:
            True if the state changed, False otherwise
        """
        changed = self.last_state_hash != state_hash
        self.last_state_hash = state_hash
        return changed
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about this agent.
        
        Returns:
            Dictionary with agent statistics
        """
        return {
            "player_name": self.player_name,
            "player_id": self.player_id,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_tokens_used": self.total_tokens_used,
            "success_rate": (
                f"{self.successful_requests / self.total_requests * 100:.1f}%"
                if self.total_requests > 0 else "N/A"
            )
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert agent state to dictionary for serialization.
        
        Returns:
            Dictionary representation of agent state
        """
        return {
            "player_name": self.player_name,
            "player_id": self.player_id,
            "player_color": self.player_color,
            "memory": self.memory,
            "chat_summaries": self.chat_summaries,
            "recent_events": self.recent_events,
            "last_prompt_number": self.last_prompt_number,
            "stats": self.get_stats()
        }


def compute_state_hash(state: Dict[str, Any]) -> str:
    """
    Compute a hash of the game state for change detection.
    
    Args:
        state: Game state dictionary
        
    Returns:
        Hash string
    """
    import json
    state_str = json.dumps(state, sort_keys=True, default=str)
    return hashlib.md5(state_str.encode()).hexdigest()[:16]
