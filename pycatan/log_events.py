"""
Log Events - Structured logging for game actions
Provides EventType enum and LogEntry dataclass for detailed game logging
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List


class EventType(Enum):
    """All possible game events for structured logging"""
    # Game flow
    GAME_START = "GAME_START"
    GAME_END = "GAME_END"
    TURN_START = "TURN_START"
    TURN_END = "TURN_END"
    PHASE_CHANGE = "PHASE_CHANGE"
    
    # Dice and resources
    DICE_ROLL = "DICE_ROLL"
    RESOURCE_DIST = "RESOURCE_DIST"
    RESOURCE_LOSS = "RESOURCE_LOSS"
    
    # Building actions
    BUILD_SETTLEMENT = "BUILD_SETTLEMENT"
    BUILD_CITY = "BUILD_CITY"
    BUILD_ROAD = "BUILD_ROAD"
    
    # Development cards
    BUY_DEV_CARD = "BUY_DEV_CARD"
    USE_DEV_CARD = "USE_DEV_CARD"
    
    # Trading
    TRADE_PROPOSE = "TRADE_PROPOSE"
    TRADE_RESPONSE = "TRADE_RESPONSE"
    TRADE_EXECUTE = "TRADE_EXECUTE"
    TRADE_BANK = "TRADE_BANK"
    
    # Robber
    ROBBER_MOVE = "ROBBER_MOVE"
    ROBBER_STEAL = "ROBBER_STEAL"
    DISCARD_CARDS = "DISCARD_CARDS"
    
    # Special
    LONGEST_ROAD = "LONGEST_ROAD"
    LARGEST_ARMY = "LARGEST_ARMY"
    VICTORY = "VICTORY"
    
    # Errors
    ACTION_FAILED = "ACTION_FAILED"


@dataclass
class LogEntry:
    """Structured log entry for a game event"""
    timestamp: datetime
    event_type: EventType
    turn: int
    player_id: Optional[int] = None
    player_name: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    status: str = "SUCCESS"  # SUCCESS, FAIL, WAITING, PENDING
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'turn': self.turn,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'data': self.data,
            'status': self.status,
            'error': self.error
        }
    
    def to_log_string(self) -> str:
        """
        Convert to structured log string format:
        [timestamp] EVENT_TYPE | key=value | key=value | ...
        """
        parts = [
            f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}]",
            self.event_type.value
        ]
        
        # Add turn
        parts.append(f"turn={self.turn}")
        
        # Add player info
        if self.player_id is not None and self.player_name:
            parts.append(f"player={self.player_id}({self.player_name})")
        elif self.player_id is not None:
            parts.append(f"player={self.player_id}")
        
        # Add all data fields
        for key, value in self.data.items():
            if isinstance(value, list):
                value_str = f"[{','.join(str(v) for v in value)}]"
            elif isinstance(value, dict):
                items = [f"{k}:{v}" for k, v in value.items()]
                value_str = f"{{{','.join(items)}}}"
            else:
                value_str = str(value)
            parts.append(f"{key}={value_str}")
        
        # Add status if not SUCCESS
        if self.status != "SUCCESS":
            parts.append(f"status={self.status}")
        
        # Add error if present
        if self.error:
            parts.append(f"error={self.error}")
        
        return " | ".join(parts)
    
    def to_human_string(self) -> str:
        """Convert to human-readable string for display"""
        # Player identifier
        if self.player_name:
            player_str = self.player_name
        elif self.player_id is not None:
            player_str = f"Player {self.player_id}"
        else:
            player_str = "System"
        
        # Build message based on event type
        if self.event_type == EventType.DICE_ROLL:
            dice = self.data.get('dice', [])
            total = self.data.get('total', sum(dice))
            return f"🎲 {player_str} rolled {dice} = {total}"
        
        elif self.event_type == EventType.RESOURCE_DIST:
            # Check if we have the new format (resources dict)
            if 'resources' in self.data:
                resources = self.data['resources']
                resource_str = ' '.join([f"{count}×{res}" for res, count in resources.items()])
                return f"📦 {player_str}: {resource_str}"
            else:
                # Old format
                resource = self.data.get('resource', '?')
                recipients = self.data.get('recipients', [])
                amounts = self.data.get('amounts', [])
                distrib = ', '.join([f"Player {r}: {a}×{resource}" for r, a in zip(recipients, amounts)])
                return f"📦 {distrib}"
        
        elif self.event_type == EventType.BUILD_SETTLEMENT:
            point = self.data.get('point', '?')
            if self.status == "SUCCESS":
                return f"🏠 {player_str} built settlement at point {point}"
            else:
                return f"❌ {player_str} failed to build settlement at point {point}: {self.error}"
        
        elif self.event_type == EventType.BUILD_CITY:
            point = self.data.get('point', '?')
            if self.status == "SUCCESS":
                return f"🏛️ {player_str} built city at point {point}"
            else:
                return f"❌ {player_str} failed to build city at point {point}: {self.error}"
        
        elif self.event_type == EventType.BUILD_ROAD:
            points = self.data.get('points', [])
            if self.status == "SUCCESS":
                return f"🛤️ {player_str} built road {points[0]}→{points[1]}"
            else:
                return f"❌ {player_str} failed to build road {points}: {self.error}"
        
        elif self.event_type == EventType.BUY_DEV_CARD:
            card = self.data.get('card', '?')
            return f"🎴 {player_str} bought development card: {card}"
        
        elif self.event_type == EventType.USE_DEV_CARD:
            card = self.data.get('card', '?')
            return f"✨ {player_str} used {card}"
        
        elif self.event_type == EventType.TRADE_PROPOSE:
            to_player = self.data.get('to_player', '?')
            offer = self.data.get('offer', {})
            request = self.data.get('request', {})
            offer_str = ', '.join([f"{v}×{k}" for k, v in offer.items()])
            request_str = ', '.join([f"{v}×{k}" for k, v in request.items()])
            return f"💱 {player_str} proposed trade to {to_player}: [{offer_str}] for [{request_str}]"
        
        elif self.event_type == EventType.TRADE_RESPONSE:
            response = self.data.get('response', '?')
            return f"💬 {player_str} {response} trade"
        
        elif self.event_type == EventType.TRADE_EXECUTE:
            details = self.data.get('details', '')
            return f"✅ Trade executed: {details}"
        
        elif self.event_type == EventType.ROBBER_MOVE:
            tile = self.data.get('tile', '?')
            return f"🦹 {player_str} moved robber to tile {tile}"
        
        elif self.event_type == EventType.ROBBER_STEAL:
            victim = self.data.get('victim', '?')
            card = self.data.get('card', 'a card')
            # Card names come from enum.name which is already capitalized (Wood, Brick, etc.)
            # Just display as-is
            return f"🦹 {player_str} stole {card} from {victim}"
        
        elif self.event_type == EventType.TURN_START:
            phase = self.data.get('phase', 'MAIN')
            return f"➤ Turn {self.turn}: {player_str}'s turn begins ({phase})"
        
        elif self.event_type == EventType.TURN_END:
            vp = self.data.get('vp', '?')
            cards = self.data.get('cards', '?')
            return f"⏹️ {player_str} ended turn [VP: {vp}, Cards: {cards}]"
        
        elif self.event_type == EventType.VICTORY:
            vp = self.data.get('vp', 10)
            return f"🏆 {player_str} WON with {vp} victory points!"
        
        else:
            # Generic fallback
            return f"• {player_str} performed {self.event_type.value}"


def create_log_entry(event_type: EventType, turn: int, player_id: Optional[int] = None,
                    player_name: Optional[str] = None, data: Optional[Dict[str, Any]] = None,
                    status: str = "SUCCESS", error: Optional[str] = None) -> LogEntry:
    """Helper function to create a log entry"""
    return LogEntry(
        timestamp=datetime.now(),
        event_type=event_type,
        turn=turn,
        player_id=player_id,
        player_name=player_name,
        data=data or {},
        status=status,
        error=error
    )
