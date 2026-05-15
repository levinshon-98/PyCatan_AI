# 🌊 Streaming System - Real-Time AI Updates

## Overview

The PyCatan AI system now supports **real-time streaming** of AI agent thoughts, actions, and tool calls! This provides immediate visibility into what the AI is thinking and doing as it plays.

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│             │ Stream  │              │  SSE    │             │
│  LLM Client ├────────►│  AI Manager  ├────────►│ Web Viewer  │
│             │ Chunks  │              │  Events │             │
└─────────────┘         └──────────────┘         └─────────────┘
                              │
                              │ HTTP POST
                              ▼
                        ┌──────────────┐
                        │Stream        │
                        │Broadcaster   │
                        └──────────────┘
```

## Components

### 1. LLM Client (`llm_client.py`)

**New:** `generate_stream()` method
- Uses `client.models.generate_content_stream()` for streaming
- Yields `StreamChunk` objects in real-time
- Supports `include_thoughts=True` in ThinkingConfig
- Handles three chunk types:
  - `thought` - AI reasoning/thinking
  - `text` - Regular response text
  - `function_call` - Tool/function calls

**StreamChunk dataclass:**
```python
@dataclass
class StreamChunk:
    chunk_type: str  # 'thought', 'text', 'function_call', 'done'
    content: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    is_complete: bool = False
```

### 2. AI Manager (`ai_manager.py`)

**New:** `_send_to_llm_stream()` method
- Similar to `_send_to_llm()` but uses streaming
- Broadcasts chunks via `_broadcast_stream_chunk()`
- Supports tool calling loop with streaming
- Each iteration can stream thoughts and tool calls

**Configuration:**
- `config.llm.enable_streaming` - Enable/disable streaming (default: True)
- Falls back to regular mode if disabled

### 3. Stream Broadcaster (`stream_broadcaster.py`)

**New component** that pushes events to web viewer:
- Sends HTTP POST to `http://localhost:5001/api/stream/broadcast`
- Non-blocking with short timeout (0.5s)
- Automatically disables if web viewer not available
- Converts StreamChunk → JSON event

### 4. Web Viewer (`web_viewer.py`)

**New endpoints:**

**`GET /api/stream/<player_name>`** - SSE endpoint
- Returns Server-Sent Events stream
- Clients connect and receive real-time updates
- Sends keepalive pings every 30s
- Auto-reconnects on error

**`POST /api/stream/broadcast`** - Broadcast endpoint
- Receives events from AI Manager
- Pushes to player-specific queue
- Queue is non-blocking (max 1000 events)

**Event format:**
```json
{
  "type": "thought|text|function_call|done",
  "timestamp": "ISO-8601",
  "content": "...",
  "function_call": {...}
}
```

### 5. Dynamic Viewer UI (`viewer_dynamic.html`)

**New features:**

**Streaming Container** - Shows live updates:
- Appears at top of page when streaming active
- Shows player name with blinking indicator
- Auto-scrolls as new chunks arrive
- Fades out after completion

**Visual feedback:**
- 💭 Purple border for thoughts
- 🔹 Green border for text
- 🔧 Orange border for function calls
- ✅ Done status with green indicator

**JavaScript functions:**
- `initStreaming()` - Connect to SSE for all players
- `connectPlayerStream(player)` - Create EventSource
- `handleStreamChunk(player, chunk)` - Process incoming chunk
- `addStreamChunk(container, type, content)` - Display chunk

## Configuration

### Enable Streaming

In `config_dev.yaml`:
```yaml
llm:
  enable_streaming: true  # Enable real-time streaming
  enable_thinking: true   # Required for thought summaries
  thinking_budget: 8000   # Budget for thinking tokens
```

### Disable Streaming

Set `enable_streaming: false` to use traditional request-response mode.

## Usage

### 1. Start the Game

Run `play_ai_auto.bat` which starts:
- Web Viewer on port 5001 (with SSE support)
- Game with AI agents
- LLM Logger console

### 2. Watch Real-Time Updates

Open browser to `http://localhost:5001`:
- Streaming boxes appear when AI is thinking
- See thoughts, tool calls, and responses as they happen
- Boxes disappear when complete

### 3. Review History

Completed requests are logged normally:
- Full prompt/response saved
- Tool iterations recorded
- All metadata preserved

## Technical Details

### Why SSE (Server-Sent Events)?

- One-way: Server → Client (perfect for our use case)
- Built-in reconnection
- Simple HTTP (no WebSocket complexity)
- Works with existing Flask app

### Why HTTP POST for Broadcasting?

- Decoupled architecture
- AI Manager doesn't need to know about SSE
- Non-blocking (fire and forget)
- Web viewer can be offline without breaking AI

### Token Budgets with Streaming

Streaming works with thinking budgets:
```yaml
# Single budget for all iterations
thinking_budget: 8000
thinking_budgets: []

# OR: Dynamic budgets per iteration
thinking_budgets: [8000, 4000, 2000]  # 3 iterations
```

Each iteration streams its own thoughts and results.

## Benefits

### For Development
- **Immediate feedback** - See what AI is doing in real-time
- **Debug tool calls** - Watch function calling decisions
- **Monitor thinking** - Understand reasoning process
- **Better UX** - Know the system is working

### For Users
- **Transparency** - See AI decision-making
- **Engagement** - Watch the game unfold
- **Understanding** - Learn how AI plays Catan
- **Entertainment** - More interesting than waiting

## Future Enhancements

Possible additions:
- [ ] Stream to multiple viewers simultaneously
- [ ] Replay streaming for historical games
- [ ] Filter streams by type (thoughts only, tools only)
- [ ] Stream game state updates
- [ ] WebSocket option for bidirectional communication
- [ ] Stream compression for high-frequency updates

## Troubleshooting

**No streaming visible:**
- Check `enable_streaming: true` in config
- Verify web viewer is running on port 5001
- Check browser console for connection errors
- Ensure `enable_thinking: true` for thought summaries

**Connection drops:**
- SSE reconnects automatically after 5s
- Check network/firewall
- Verify Flask not blocking long connections

**Missing chunks:**
- Queue size is 1000 - may drop old events
- Increase queue size in `web_viewer.py` if needed

## API Reference

### StreamChunk
```python
chunk = StreamChunk(
    chunk_type='thought',  # or 'text', 'function_call', 'done'
    content='Analyzing situation...',
    is_complete=False
)
```

### SSE Event
```javascript
{
  type: 'thought',
  timestamp: '2026-01-10T12:34:56',
  content: 'I should build a settlement...'
}
```

### Broadcast API
```bash
POST http://localhost:5001/api/stream/broadcast
Content-Type: application/json

{
  "player_name": "Agent1",
  "chunk_type": "thought",
  "content": "Thinking..."
}
```

## Credits

Built on top of:
- **Google Gemini API** - Streaming support with thinking mode
- **Flask** - SSE server
- **Server-Sent Events** - Real-time browser updates
- **PyCatan** - Settlers of Catan implementation

---

**Happy Streaming! 🌊**
