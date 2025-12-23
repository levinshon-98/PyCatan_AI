# 🤖 AI Agent Architecture

**Date:** December 23, 2025  
**Status:** 📋 In Planning

## 🎯 Goal

Build an LLM-based AI agent that can play Settlers of Catan autonomously and intelligently.

## 🏗️ Overall Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        GameManager                          │
│                (Game coordination & decisions)               │
├─────────────────────────────────────────────────────────────┤
│  • game_loop() - Main game loop                             │
│  • handle_turn_rules() - Turn management                    │
│  • coordinate_interactions() - Player coordination          │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │  Game   │  │  Users  │  │  Viz    │
   │ (Core)  │  │(Players)│  │(Display)│
   └─────────┘  └────┬────┘  └─────────┘
                     │
              ┌──────┴──────┐
              │             │
              ▼             ▼
        ┌──────────┐  ┌──────────┐
        │  Human   │  │ AI Agent │ ← NEW!
        │   User   │  │   (LLM)  │
        └──────────┘  └──────────┘
             ✅            🚧
```

## 📦 Existing Components

### 1️⃣ Core - The Game (game.py)
**What exists:**
- Complete and tested game rules
- Board, player, and resource management
- Action validation

**Status:** ✅ Ready and stable

### 2️⃣ GameManager - Game Manager (management/game_manager.py)
**What exists:**
- Turn and phase management
- Player coordination
- Rule enforcement

**Status:** ✅ Ready and stable

### 3️⃣ Actions - Action System (management/actions.py)
**What exists:**
- Definition of all possible game actions
- Unified data structure for each action
- Validation and permissions

**Example:**
```python
class Action:
    def __init__(self, action_type, player_num, **kwargs):
        self.action_type = action_type  # BUILD_SETTLEMENT, BUILD_ROAD, etc.
        self.player_num = player_num
        self.details = kwargs  # point, edge, resources, etc.
```

**Status:** ✅ Ready and stable

### 4️⃣ HumanUser - Human User (players/human_user.py)
**What exists:**
- CLI interaction
- Getting decisions from user
- Executing actions through GameManager

**Status:** ✅ Ready and tested
