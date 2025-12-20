# PyCatan Tests

This directory contains all test files for the PyCatan project, organized by test type.

## Directory Structure

### 📦 unit/
**Unit Tests** - Testing individual modules and components in isolation.

Files: `test_actions.py`, `test_board.py`, `test_game.py`, etc.

Run with: `pytest tests/unit/`

### 🔗 integration/
**Integration Tests** - Testing complete game scenarios and interactions between components.

Includes comprehensive tests for:
- Knight card functionality
- City building mechanics
- Robber interactions
- Trade systems
- Game flow scenarios

Files: `test_knight_*.py`, `test_city_building.py`, etc.

Run with: `pytest tests/integration/`

### 🎮 manual/
**Manual Tests** - Tests requiring user interaction or visual verification.

Currently empty - reserved for interactive tests.

## Running Tests

```bash
# Run all tests
pytest tests/

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run specific test file
pytest tests/integration/test_knight_card.py

# Run with verbose output
pytest tests/ -v
```

## Test Coverage

The tests cover:
- Core game logic (Game, Player, Board)
- Building mechanics (settlements, cities, roads)
- Card systems (resource cards, development cards)
- Game flow (turns, dice rolling, robber)
- User interactions (HumanUser, GameManager)
- Visualizations (Console, Web)
