# PyCatan AI Coding Instructions

## Project Overview
PyCatan is a Python library for simulating Settlers of Catan games. 

**🚀 NEW: Active Development Phase**  
This project is being actively expanded with a complete simulation framework including GameManager, AI players, and multiple visualization interfaces.

**📚 Additional Documentation:**
- **[Architecture Overview](instructions/ARCHITECTURE.md)** - Project vision, architecture design, and component responsibilities
- **[Build Plan](instructions/BUILD_PLAN.md)** - Development roadmap, tasks, and progress tracking
- **[API Reference](instructions/STEP_BY_STEP_GUIDE.md)** - הסבר לאיך לתקשר עם המשתמש שאתה עובד איתו
## Legacy Note
The original core game logic is stable and functional. New development focuses on building a complete simulation layer on top of the existing foundation.

## Core Architecture

### Game Flow Model
- **Game** (`pycatan/game.py`) orchestrates everything - manages players, board, development cards, and win conditions
- **Board** (`pycatan/board.py`) is abstract base class; **DefaultBoard** (`pycatan/default_board.py`) implements hexagonal tile layout
- **Player** (`pycatan/player.py`) manages individual state: cards, buildings, victory points, longest road calculation
- **Point** and **Tile** objects form the geometric foundation with bidirectional relationships

### Key Patterns

#### Coordinate System
- Board uses `[row, index]` coordinates throughout (not x,y)
- Points are intersections where settlements/cities go; tiles are hexes that produce resources
- Example: `game.add_settlement(player=0, point=board.points[0][0], is_starting=True)`

#### Status-Based Error Handling
All game actions return `Statuses` enum values instead of throwing exceptions:
```python
from pycatan.statuses import Statuses
result = game.add_settlement(player, point)
if result == Statuses.ERR_BLOCKED:
    # Handle blocked building location
```

#### Starting vs Normal Phase
Most building actions have `is_starting` parameter - starting phase bypasses card costs and connectivity rules:
```python
game.add_settlement(player, point, is_starting=True)  # Free during setup
game.add_road(player, start, end, is_starting=True)   # No cards required
```

## Development Workflows

### Testing
- Use pytest: `python -m pytest tests/` (not the bash script on Windows)
- Tests in `tests/` follow class-based pattern: `class TestGame:` with `test_*` methods
- Mock game state by directly manipulating player cards: `player.add_cards([ResCard.Wood, ResCard.Brick])`

### Building/Distribution
- Package managed via setuptools (`setup.py`)
- Published to PyPI as `pycatan` package
- Version number in `setup.py` (currently 0.13)

## Critical Implementation Details

### Longest Road Calculation
Complex recursive algorithm in `Player.get_longest_road()` - avoid modifying without understanding the connected road traversal logic.

### Card Management
- Resources use `ResCard` enum, development cards use `DevCard` enum
- Player card checking with `has_cards()` handles duplicates correctly by creating temporary lists
- Bank trading supports both 4:1 and harbor-specific rates (2:1 or 3:1)

### Development Card Usage
Different dev cards require different `args` dictionaries in `use_dev_card()`:
- Knight: `{'robber_pos': [r, i], 'victim': player_num}`
- Road Building: `{'road_one': {'start': point, 'end': point}, 'road_two': {...}}`
- Monopoly: `{'card_type': ResCard.Wood}`

### Import Structure
Main module exports through `pycatan/__init__.py`:
- Import as: `from pycatan import Game, Player, ResCard, Statuses`
- Avoid importing submodules directly unless extending core classes

## Testing Conventions
- Create game instances with explicit player counts: `Game(num_of_players=4)`
- Use board coordinate system: `board.points[row][index]` for settlements
- Test error conditions by checking returned status codes, not exceptions
- Starting phase tests should verify cards aren't consumed: `assert len(player.cards) == original_count`