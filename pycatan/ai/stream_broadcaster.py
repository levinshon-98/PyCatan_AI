"""
Stream Broadcaster - Sends streaming chunks to web viewer via HTTP.
"""

import json
import logging
import requests
from typing import Optional
from pycatan.ai.llm_client import StreamChunk

logger = logging.getLogger(__name__)


class StreamBroadcaster:
    """
    Broadcasts streaming chunks to the web viewer via HTTP POST.
    
    The web viewer has an SSE endpoint that clients connect to,
    and this broadcaster pushes events to that endpoint.
    """
    
    def __init__(self, web_viewer_url: str = "http://localhost:5001"):
        """
        Initialize the stream broadcaster.
        
        Args:
            web_viewer_url: Base URL of the web viewer (default: http://localhost:5001)
        """
        self.web_viewer_url = web_viewer_url
        self.broadcast_url = f"{web_viewer_url}/api/stream/broadcast"
        self.enabled = True
        
        # Test connection
        try:
            response = requests.get(web_viewer_url, timeout=1)
            logger.info(f"✅ Connected to web viewer at {web_viewer_url}")
        except:
            logger.warning(f"⚠️ Could not connect to web viewer at {web_viewer_url}")
            logger.warning("   Streaming broadcasts will be disabled.")
            self.enabled = False
    
    def broadcast(self, player_name: str, chunk: StreamChunk) -> None:
        """
        Broadcast a streaming chunk to the web viewer.
        
        Args:
            player_name: Name of the player/agent
            chunk: StreamChunk object to broadcast
        """
        if not self.enabled:
            return
        
        try:
            # Build event payload
            payload = {
                "player_name": player_name,
                "chunk_type": chunk.chunk_type,
            }
            
            if chunk.content:
                payload["content"] = chunk.content
            
            if chunk.function_call:
                payload["function_call"] = chunk.function_call
            
            # Send to web viewer (non-blocking, short timeout)
            requests.post(
                self.broadcast_url,
                json=payload,
                timeout=0.5
            )
            
        except Exception as e:
            # Don't let broadcasting errors stop the AI
            logger.debug(f"Failed to broadcast chunk: {e}")
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable broadcasting."""
        self.enabled = enabled
