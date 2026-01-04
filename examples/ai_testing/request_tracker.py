"""
Request Tracker - Track all AI requests with metadata
------------------------------------------------------
Saves structured data about each AI request including:
- What triggered it
- Game context
- Request/response data
- Timing information
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List


class RequestTracker:
    """Tracks all AI requests with full context and metadata."""
    
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.requests_file = session_dir / "requests.json"
        self.requests: List[Dict[str, Any]] = []
        self.load()
    
    def load(self):
        """Load existing requests from file."""
        if self.requests_file.exists():
            try:
                with open(self.requests_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.requests = data.get("requests", [])
            except Exception as e:
                print(f"Warning: Could not load requests: {e}")
                self.requests = []
    
    def add_request(
        self,
        player_name: str,
        trigger: str,
        game_phase: str,
        current_player: str,
        prompt_data: Dict[str, Any],
        response_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a new AI request.
        
        Args:
            player_name: Name of the player/agent
            trigger: What caused this request (e.g., "turn_start", "state_change")
            game_phase: Current game phase (e.g., "SETUP_FIRST_ROUND", "MAIN_GAME")
            current_player: Who's turn it is
            prompt_data: The prompt sent to LLM
            response_data: The response from LLM (optional, can be added later)
            metadata: Additional metadata (timing, tokens, etc.)
        
        Returns:
            Request ID
        """
        request_id = f"req_{len(self.requests) + 1:04d}"
        timestamp = datetime.now().isoformat()
        
        request = {
            "request_id": request_id,
            "timestamp": timestamp,
            "player_name": player_name,
            "trigger": trigger,
            "game_context": {
                "phase": game_phase,
                "current_player": current_player,
            },
            "prompt": prompt_data,
            "response": response_data,
            "raw_response": None,  # Store unprocessed LLM response
            "metadata": metadata or {},
            "is_new": True  # Flag for UI to show as new
        }
        
        self.requests.append(request)
        self.save()
        return request_id
    
    def update_response(self, request_id: str, response_data: Dict[str, Any], raw_response: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Update request with response data."""
        for req in self.requests:
            if req["request_id"] == request_id:
                req["response"] = response_data
                if raw_response:
                    req["raw_response"] = raw_response
                if metadata:
                    req["metadata"].update(metadata)
                req["response_timestamp"] = datetime.now().isoformat()
                self.save()
                return True
        return False
    
    def mark_as_viewed(self, request_id: str):
        """Mark request as viewed (not new anymore)."""
        for req in self.requests:
            if req["request_id"] == request_id:
                req["is_new"] = False
                self.save()
                return True
        return False
    
    def mark_all_as_viewed(self):
        """Mark all requests as viewed."""
        for req in self.requests:
            req["is_new"] = False
        self.save()
    
    def get_new_count(self) -> int:
        """Get count of new (unviewed) requests."""
        return sum(1 for req in self.requests if req.get("is_new", False))
    
    def get_player_requests(self, player_name: str) -> List[Dict[str, Any]]:
        """Get all requests for a specific player."""
        return [req for req in self.requests if req["player_name"] == player_name]
    
    def get_new_player_requests(self, player_name: str) -> List[Dict[str, Any]]:
        """Get new requests for a specific player."""
        return [req for req in self.requests 
                if req["player_name"] == player_name and req.get("is_new", False)]
    
    def save(self):
        """Save requests to file."""
        try:
            with open(self.requests_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "requests": self.requests,
                    "total_count": len(self.requests),
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving requests: {e}")
    
    def get_all_requests(self) -> List[Dict[str, Any]]:
        """Get all requests."""
        return self.requests
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about requests."""
        players = {}
        for req in self.requests:
            player = req["player_name"]
            if player not in players:
                players[player] = {
                    "total": 0,
                    "new": 0,
                    "phases": set()
                }
            players[player]["total"] += 1
            if req.get("is_new", False):
                players[player]["new"] += 1
            players[player]["phases"].add(req["game_context"]["phase"])
        
        # Convert sets to lists for JSON serialization
        for player_data in players.values():
            player_data["phases"] = list(player_data["phases"])
        
        return {
            "total_requests": len(self.requests),
            "new_requests": self.get_new_count(),
            "players": players
        }
