# 🎮 PyCatan AI Agent - Project Instructions

## 📋 Overview

This project implements a Settlers of Catan game in Python. **Our current goal** is to build an **LLM-based AI agent** that can play the game autonomously.

---

## 🎯 Current Mission: Build AI Agent

### 📖 Architecture Reference
See [AI_ARCHITECTURE.md](.github/instructions/AI_ARCHITECTURE.md) for the complete system architecture.

### 🤝 Agent-Game Manager Interaction

The AI agent will work in coordination with the GameManager:

**How it works:**
1. **GameManager asks:** "What action do you want to take?"
2. **GameManager provides:** List of valid options based on current game state
3. **AI Agent responds:** With a specific action choice

**Example interaction:**
```
GameManager: "Options: place starting settlement"
AI Agent: "s 14"
```

The GameManager handles:
- ✅ Game rules and validation
- ✅ Determining available actions
- ✅ Executing actions
- ✅ Managing turn flow

The AI Agent handles:
- 🤖 Analyzing current game state
- 🤖 Deciding which action to take
- 🤖 Returning action in correct format

---

## 🏗️ Development Approach

### Phase 1: Build the Agent Foundation
**Focus areas:**
- 🧠 **Memory & State Management** - Agent's ability to track and understand game state
- 📊 **State Representation** - Based on JSON format from `examples/ai_testing/play_and_capture.py`
- 🔄 **Feedback Loop** - How agent receives state and returns decisions
- 🎯 **Prompt Engineering** - Crafting effective prompts for decision-making
- 🐛 **Debugging Infrastructure** - Tools to understand agent's reasoning

### Core Principles
1. ✨ **Simple & Modular** - Easy to modify and extend
2. 🔍 **Easy to Debug** - Clear visibility into agent decisions
3. 🧩 **Flexible Design** - Can swap components easily

**⚠️ Important:** We will NOT dive into detailed agent architecture yet. Focus on establishing clean interfaces and simple implementations first.

---

## 📂 Key Files

### Game State Capture
- `examples/ai_testing/play_and_capture.py` - Captures game states during play
- `examples/ai_testing/my_games/current_state.json` - Real-time game state
- `examples/ai_testing/sample_states/captured_game.json` - Example game state

### Core Components (Already Built ✅)
- `pycatan/core/game.py` - Game logic
- `pycatan/management/game_manager.py` - Game coordination
- `pycatan/management/actions.py` - Action definitions
- `pycatan/players/human_user.py` - Human player interface

### AI Agent (To Be Built 🚧)
- `pycatan/players/ai_agent.py` - LLM-based AI player (coming soon)

---

## 💡 Working with Copilot

When helping with this project:
1. **Refer to AI_ARCHITECTURE.md** for system design
2. **Study game state JSON** from captured games to understand data structure
3. **Keep implementations simple** - favor clarity over cleverness
4. **Make debugging easy** - add logging, state inspection, decision traces
5. **Stay modular** - each component should have clear responsibilities

---

## 🚀 Next Steps

1. Design agent's state management system
2. Create prompt templates for decision-making
3. Build feedback loop between GameManager and AI Agent
4. Implement debugging and logging tools
5. Test with simple scenarios first
