# 🎮 PyCatan AI - Quick Start Guide

## 🚀 How to Run

### Option 1: Play with AI Agents (Recommended)
```bash
python examples/ai_testing/play_with_ai.py
```

This will:
1. Let you configure players (human or AI)
2. Generate AI prompts for AI players
3. Allow you to manually enter AI actions
4. Log all prompts and responses for analysis

### Option 2: Quick Start - All AI Players
```bash
python examples/ai_testing/play_with_ai.py --players 3 --all-ai
```

### Option 3: Auto-LLM Mode (requires API key)
```bash
# First set your API key:
set GEMINI_API_KEY=your_api_key_here

# Then run:
python examples/ai_testing/play_with_ai.py --auto-llm
```

---

## 📁 Project Structure

```
pycatan/
├── ai/                          # 🤖 AI System (NEW)
│   ├── ai_manager.py            # Central AI coordinator
│   ├── ai_user.py               # AI player wrapper
│   ├── ai_logger.py             # Logging system
│   ├── agent_state.py           # Per-agent state
│   ├── prompt_manager.py        # Prompt construction
│   ├── response_parser.py       # Response parsing
│   ├── llm_client.py            # Gemini API client
│   ├── config.py                # Configuration
│   └── schemas.py               # JSON schemas
│
├── management/
│   └── game_manager.py          # Game coordination
│
├── players/
│   ├── user.py                  # Abstract user class
│   └── human_user.py            # Human player CLI
│
└── core/                        # Game logic
    ├── game.py
    ├── board.py
    └── ...

examples/
└── ai_testing/
    ├── play_with_ai.py          # 🆕 Main entry point
    ├── play_and_capture.py      # State capture utility
    ├── web_viewer.py            # Prompt visualization
    ├── my_games/                # Session storage
    └── _deprecated/             # Old files (for reference)
```

---

## 🎯 Manual Mode Commands

When playing in manual mode, use these commands for AI players:

### Basic Actions
| Command | Description |
|---------|-------------|
| `roll_dice` or `r` | Roll the dice |
| `end_turn` or `e` | End turn |

### Building
| Command | Example |
|---------|---------|
| `build_settlement` | `build_settlement {"node": 14}` |
| `build_city` | `build_city {"node": 14}` |
| `build_road` | `build_road {"from": 14, "to": 15}` |

### Shortcuts (Setup Phase)
| Command | Meaning |
|---------|---------|
| `s 14` | Place settlement at node 14 |
| `rd 14 15` | Place road from 14 to 15 |

### Other Actions
| Command | Example |
|---------|---------|
| `buy_dev_card` | Buy a development card |
| `robber_move` | `robber_move {"hex": 5}` |
| `steal_card` | `steal_card {"target_player": "Bob"}` |
| `trade_bank` | `trade_bank {"give": "wheat", "receive": "ore"}` |

Type `help` at any prompt for more details.

---

## 📊 Logs and Sessions

Each game session creates a folder in `examples/ai_testing/my_games/`:

```
session_20260108_143022/
├── session_metadata.json        # Session info
├── chat_history.json            # Chat messages
├── session_summary.json         # Final stats
│
├── AI_1/                        # Per-player folder
│   ├── prompts/
│   │   ├── prompt_1.json        # Full prompt
│   │   ├── prompt_1.txt         # Human-readable
│   │   └── ...
│   ├── responses/
│   │   ├── response_1.json      # LLM response
│   │   └── ...
│   └── AI_1.md                  # Log file
│
└── AI_2/
    └── ...
```

---

## 🔧 Configuration

### AI Config (Optional)
Create `config_dev.yaml` in `pycatan/ai/`:

```yaml
llm:
  provider: "gemini"
  model_name: "gemini-2.0-flash-exp"
  temperature: 0.7
  api_key_env_var: "GEMINI_API_KEY"

memory:
  chat_history_size: 10
```

### Environment Variables
```bash
# Windows
set GEMINI_API_KEY=your_api_key

# Linux/Mac
export GEMINI_API_KEY=your_api_key
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Game Flow                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   GameManager                          AIManager                │
│       │                                    │                    │
│       │ "What action?"                     │ Creates prompts    │
│       ▼                                    │ Manages memory     │
│   ┌─────────┐                              │ Logs everything    │
│   │ AIUser  │◄──── delegates to ──────────►│                    │
│   │(Wrapper)│                              │                    │
│   └─────────┘                              ▼                    │
│       │                            ┌─────────────┐              │
│       │ Returns Action             │  AILogger   │              │
│       ▼                            │  (Files)    │              │
│   GameManager                      └─────────────┘              │
│   executes action                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📚 Documentation

- [AI_REFACTOR_PLAN.md](.github/instructions/AI_REFACTOR_PLAN.md) - Detailed refactoring plan
- [AI_ARCHITECTURE.md](.github/instructions/AI_ARCHITECTURE.md) - System architecture
- [AI_AGENT_PRINCIPLES.md](.github/instructions/AI_AGENT_PRINCIPLES.md) - Design principles

---

## ❓ Troubleshooting

### "API key not found"
Make sure to set the environment variable:
```bash
set GEMINI_API_KEY=your_key_here
```

### "Module not found"
Run from the project root directory:
```bash
cd C:\GIT_new\PyCatan_AI
python examples/ai_testing/play_with_ai.py
```

### "Action not allowed"
Check the `allowed_actions` list shown in the prompt. The action must be one of those.

---

## 🎉 Have Fun!

Start a game and experiment with AI prompts. Check the generated logs to understand how the AI "thinks" about the game state.

```bash
python examples/ai_testing/play_with_ai.py
```
