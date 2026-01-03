# AI Game Web Viewer

Real-time web interface for monitoring AI agents playing Catan.

## 🌐 Features

- **Real-time updates** - Refreshes every second
- **Player logs** - View each AI agent's thinking and responses
- **Chat history** - See all player communications
- **Agent memories** - Monitor what each AI remembers
- **Session management** - Track multiple game sessions
- **Clean UI** - Dark theme, easy navigation

## 🚀 Quick Start

### Automatic (Recommended)
```bash
start.bat
```
This will automatically open:
1. AI Tester window
2. Web Viewer at http://localhost:5000
3. Game console

### Manual
```bash
# Terminal 1: Start web viewer
python examples/ai_testing/web_viewer.py

# Terminal 2: Start AI tester
python examples/ai_testing/test_ai_live.py

# Terminal 3: Start game
python examples/ai_testing/play_with_prompts.py
```

Then open http://localhost:5000 in your browser.

## 📦 Requirements

```bash
pip install flask markdown
```

## 🎨 Interface

### Sidebar Navigation
- **Players** - Click to view individual AI agent logs
- **Chat History** - See all player messages
- **Agent Memories** - View saved notes
- **Session Info** - Current session details

### Main Content Area
- Updates automatically every second
- Shows player logs in formatted markdown
- Chat messages with timestamps
- Agent memories organized by player

## 🔄 How It Works

1. `web_viewer.py` reads from the current session directory
2. Loads `chat_history.json`, `agent_memories.json`, and `player_*.md` files
3. Updates the web interface every second via AJAX
4. No need to refresh - everything updates automatically

## 📁 Data Sources

All data is read from:
```
examples/ai_testing/my_games/ai_logs/session_YYYYMMDD_HHMMSS/
├── player_a.md          # AI logs
├── player_b.md
├── player_c.md
├── chat_history.json    # Chat messages
└── agent_memories.json  # AI memories
```

## 🎯 Tips

- Leave the viewer open while playing
- Switch between players to see different strategies
- Monitor chat for negotiations
- Check memories to understand AI planning
