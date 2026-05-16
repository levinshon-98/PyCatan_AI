# 🎲 PyCatan AI

A Python library for simulating and playing **The Settlers of Catan** with support for multiple interfaces and AI players.

> 🚀 **Active Development**: This project extends the original [PyCatan](https://github.com/josefwaller/PyCatan) with a complete simulation framework including GameManager, AI players, and multiple visualization interfaces.

## ✨ Features

- **Complete Game Logic** - Full implementation of Settlers of Catan rules
- **Multiple Interfaces**:
  - 🖥️ Console/Terminal interface with colored output
  - 🌐 Web browser interface with interactive board
- **Game Management** - Turn management, phases, and game flow control
- **Extensible Architecture** - Easy to add AI players and custom visualizations
- **Human & AI Players** - Support for multiple player types

## 📦 Installation

### From Source
```bash
git clone https://github.com/levinshon-98/PyCatan_AI.git
cd PyCatan_AI
pip install -e .
```

### Dependencies
```bash
pip install flask  # For web visualization
```

## 🚀 Quick Start

### Play a Full Game
```python
from pycatan import RealGame

# Start an interactive game with console and web interfaces
game = RealGame()
game.run()
```

### Basic Game Setup
```python
from pycatan import Game, Statuses

# Create a new game with 3 players
game = Game(num_of_players=3)

# Access the board
board = game.board

# Build a settlement (during setup phase)
point = board.points[0][0]
result = game.add_settlement(player=0, point=point, is_starting=True)

if result == Statuses.ALL_GOOD:
    print("Settlement built successfully!")
```

### Using the Game Manager
```python
from pycatan import GameManager, HumanUser, ConsoleVisualization

# Create players
users = [
    HumanUser("Alice", player_num=0),
    HumanUser("Bob", player_num=1),
    HumanUser("Charlie", player_num=2)
]

# Create game manager
game_manager = GameManager(users)

# Add visualization
console_viz = ConsoleVisualization()
game_manager.visualization_manager.add_visualization(console_viz)

# Start the game loop
game_manager.start_game()
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│              GameManager                │  ← Manages turns and flow
├─────────────────────────────────────────┤
│ • game_loop()                           │
│ • handle_turn_rules()                   │
│ • coordinate_interactions()             │
└───────────────┬─────────────────────────┘
                │
    ┌───────────┼───────────┐
    │           │           │
    ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────────┐
│  Game   │ │  Users  │ │Visualizations│
│ (Core)  │ │(Players)│ │  (Display)   │
└─────────┘ └─────────┘ └─────────────┘
```

### Core Components

| Component | Description |
|-----------|-------------|
| `Game` | Core game logic - rules, validation, state management |
| `GameManager` | Turn management, game flow, user coordination |
| `User` | Abstract base class for players (Human/AI) |
| `HumanUser` | Human player with CLI input |
| `Visualization` | Base class for display interfaces |
| `ConsoleVisualization` | Terminal-based game display |
| `WebVisualization` | Browser-based interactive board |

## 📖 Game Actions

### Building
```python
# Build settlement
game.add_settlement(player=0, point=point, is_starting=False)

# Build road  
game.add_road(player=0, start=point1, end=point2, is_starting=False)

# Build city (upgrade settlement)
game.add_city(player=0, point=point)
```

### Trading
```python
# Trade with bank (4:1)
game.trade_to_bank(player=0, give=ResCard.Wood, get=ResCard.Brick)

# Trade with harbor (3:1 or 2:1)
game.trade_to_bank(player=0, give=ResCard.Wheat, get=ResCard.Ore)
```

### Development Cards
```python
from pycatan import DevCard

# Buy development card
game.build_dev(player=0)

# Use Knight card
game.use_dev_card(player=0, card=DevCard.Knight, args={
    'robber_pos': [2, 1],
    'victim': 1
})
```

## 🎮 Status-Based Error Handling

All game actions return `Statuses` enum values instead of exceptions:

```python
from pycatan import Statuses

result = game.add_settlement(player=0, point=point)

match result:
    case Statuses.ALL_GOOD:
        print("Success!")
    case Statuses.ERR_BLOCKED:
        print("Location blocked by another building")
    case Statuses.ERR_NOT_ENOUGH_RES:
        print("Not enough resources")
    case Statuses.ERR_BAD_LOCATION:
        print("Invalid building location")
```

## 🗂️ Project Structure

```
PyCatan_AI/
├── pycatan/                    # 📦 Main library code
│   ├── game.py                 # Core game logic
│   ├── game_manager.py         # Turn and flow management
│   ├── board.py                # Board base class
│   ├── default_board.py        # Standard Catan board
│   ├── player.py               # Player state management
│   ├── card.py                 # Resource and development cards
│   ├── actions.py              # Action types and results
│   ├── log_events.py           # Event logging system
│   ├── user.py                 # User base class
│   ├── human_user.py           # Human player implementation
│   ├── visualization.py        # Visualization base class
│   ├── console_visualization.py # Console display
│   ├── web_visualization.py    # Web interface
│   ├── real_game.py            # Complete game orchestration
│   └── statuses.py             # Status codes for actions
│
├── tests/                      # 🧪 Test suite
│   ├── unit/                   # Unit tests for individual modules
│   ├── integration/            # Integration tests for game scenarios
│   └── manual/                 # Manual/interactive tests
│
├── examples/                   # 📚 Examples and demos
│   ├── demos/                  # Playable game demonstrations
│   └── scripts/                # Utility scripts for development
│
├── בלוג/                       # 📝 Hebrew blog posts
└── [Configuration files]       # setup.py, README.md, etc.
```

## 🧪 Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run only unit tests
python -m pytest tests/unit/

# Run only integration tests
python -m pytest tests/integration/

# Run specific test file
python -m pytest tests/unit/test_game.py

# Run with verbose output
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov=pycatan
```

See [tests/README.md](tests/README.md) for detailed information about the test structure.

## 🌐 Web Visualization

The web visualization provides an interactive board in your browser:

```python
from pycatan import WebVisualization, create_web_visualization

# Create web visualization
web_viz = create_web_visualization(port=5000)

# Start server (opens browser automatically)
web_viz.start()

# Update with game state
web_viz.update_full_state(game_state)
```

**Features:**
- 🗺️ Interactive hexagonal board
- 🔄 Real-time updates via Server-Sent Events
- 📊 Player info panel with resources and points
- 📜 Action log with timestamped events

## 📚 Documentation

- [Architecture Overview](.github/instructions/ARCHITECTURE.md) - Project design and components
- [Build Plan](.github/instructions/BUILD_PLAN.md) - Development roadmap and progress
- [Coding Instructions](.github/copilot-instructions.md) - Development guidelines

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE.txt](LICENSE.txt) file for details.

## 🙏 Acknowledgments

- Original [PyCatan](https://github.com/josefwaller/PyCatan) by Josef Waller
- The Settlers of Catan® is a trademark of Catan GmbH

---

**Made with ❤️ for Catan enthusiasts and AI developers**
---
title: PyCatan AI
sdk: docker
app_port: 7860
pinned: false
license: mit
---
