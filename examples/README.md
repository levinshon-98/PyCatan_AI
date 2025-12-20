# PyCatan Examples

This directory contains example code, demos, and utility scripts for the PyCatan project.

## Directory Structure

### 🎮 demos/
**Game Demonstrations** - Complete playable examples showing how to use PyCatan.

- **play_catan.py** - Main interactive game with CLI and web visualization
- **demo_point_system.py** - Demonstration of the point numbering system

Run a demo:
```bash
python examples/demos/play_catan.py
```

### 🛠️ scripts/
**Utility Scripts** - Helper tools for development and debugging.

- **check_steal_tiles.py** - Verify robber tile stealing mechanics
- **print_game_logic.py** - Print game state and logic for debugging

Run a script:
```bash
python examples/scripts/check_steal_tiles.py
```

### 📊 board_renderer.py
Visual board rendering utility (legacy file in root of examples/).

## Usage

### Running the Interactive Game

The main demo provides a full interactive Catan game experience:

```bash
cd examples/demos
python play_catan.py
```

This will:
- Start a game with configurable number of players
- Provide CLI interface for actions
- Launch web visualization in browser
- Support all game mechanics (building, trading, development cards)

### Understanding the Point System

To understand how board points are numbered:

```bash
python examples/demos/demo_point_system.py
```

## Creating Your Own Game

Use these examples as templates for your own games:

```python
from pycatan import Game, GameManager, HumanUser
from pycatan import ConsoleVisualization, WebVisualization

# Create users
users = [HumanUser("Alice"), HumanUser("Bob")]

# Create visualizations
visualizations = [
    ConsoleVisualization(),
    WebVisualization()
]

# Start game
manager = GameManager(users, visualizations)
manager.start_game()
```
