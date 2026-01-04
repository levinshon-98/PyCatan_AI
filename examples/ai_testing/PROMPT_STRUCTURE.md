# 📨 Prompt Management Structure

## Overview
This document explains how AI prompts are organized and managed in the PyCatan AI system.

## Directory Structure

```
examples/ai_testing/my_games/ai_logs/
└── session_YYYYMMDD_HHMMSS/          # Game session folder
    ├── NH/                            # Player NH
    │   ├── prompts/                   # All prompts for this player
    │   │   ├── prompt_1.json          # First prompt
    │   │   ├── prompt_1.txt           # Human-readable version
    │   │   ├── prompt_2.json          # Second prompt
    │   │   ├── prompt_2.txt
    │   │   └── ...                    # More prompts as game progresses
    │   └── responses/                 # AI responses (to be implemented)
    │       ├── response_1.json
    │       └── ...
    ├── Alex/                          # Player Alex
    │   ├── prompts/
    │   │   ├── prompt_1.json
    │   │   └── ...
    │   └── responses/
    └── Sarah/                         # Player Sarah
        ├── prompts/
        └── responses/
```

## How It Works

### 1. **Prompt Generation**
Every time the game state changes and it's a player's turn, the system generates a new prompt:

```python
from examples.ai_testing.generate_prompts_from_state import main as generate_prompts

# This creates numbered prompts for each player
generate_prompts()
```

### 2. **Prompt Numbering**
- Each new prompt gets a sequential number: `prompt_1.json`, `prompt_2.json`, etc.
- **Always use the highest numbered prompt** - it's the most recent one
- Old prompts are kept for debugging and analysis

### 3. **Prompt Format**
Each `.json` file contains:
- `response_schema`: The expected format for LLM response
- `system_instruction`: Instructions for the LLM
- `prompt`: The actual game state and context

### 4. **Getting the Latest Prompt**

```python
from examples.ai_testing.generate_prompts_from_state import get_latest_prompt

# Get the most recent prompt for a player
prompt_file, prompt_data = get_latest_prompt("NH")

if prompt_file:
    print(f"Latest prompt: {prompt_file}")
    # Use prompt_data to send to LLM
```

Or use the example script:
```bash
python examples/ai_testing/example_get_latest_prompt.py NH
```

## File Types

### JSON Files (`prompt_N.json`)
**Send this to the LLM**
- Complete request ready for API
- Includes response schema
- Machine-readable format

### TXT Files (`prompt_N.txt`)
**For human inspection**
- Formatted for readability
- Includes headers and sections
- Helpful for debugging

## Benefits of This Structure

✅ **No Overwrites** - Each prompt is saved with unique number
✅ **Easy to Track** - Can see full history of prompts
✅ **Simple to Use** - Always use the highest number
✅ **Player-Specific** - Each player has their own folder
✅ **Session-Based** - Each game session is separate
✅ **Debugging** - Can compare prompts across turns

## Example Usage

### Basic Usage
```python
import json
from pathlib import Path
from examples.ai_testing.generate_prompts_from_state import get_latest_prompt

# 1. Get latest prompt for player
prompt_file, prompt_data = get_latest_prompt("NH")

# 2. Extract the prompt
if prompt_data:
    llm_request = prompt_data  # Already in correct format
    
    # 3. Send to LLM (pseudo-code)
    response = llm_client.send(
        system=llm_request["system_instruction"],
        prompt=llm_request["prompt"],
        response_format=llm_request["response_schema"]
    )
```

### Finding All Prompts for a Player
```python
from pathlib import Path

player_name = "NH"
session_dir = Path("examples/ai_testing/my_games/ai_logs/session_20260104_025733")
player_prompts = sorted((session_dir / player_name / "prompts").glob("prompt_*.json"))

print(f"Found {len(player_prompts)} prompts for {player_name}")
for prompt in player_prompts:
    print(f"  - {prompt.name}")
```

### Comparing Two Prompts
```python
import json

# Get two sequential prompts
prompt_1 = session_dir / "NH" / "prompts" / "prompt_1.json"
prompt_2 = session_dir / "NH" / "prompts" / "prompt_2.json"

with open(prompt_1) as f1, open(prompt_2) as f2:
    data1 = json.load(f1)
    data2 = json.load(f2)
    
    # Compare what changed
    turn1 = data1["prompt"]["game_state"]["meta"]["turn"]
    turn2 = data2["prompt"]["game_state"]["meta"]["turn"]
    
    print(f"Prompt 1 was for turn {turn1}")
    print(f"Prompt 2 was for turn {turn2}")
```

## Future Enhancements

- [ ] Add `responses/` directory for AI agent responses
- [ ] Create prompt-response pairs for training
- [ ] Add automatic cleanup of old sessions
- [ ] Add prompt compression for long games
- [ ] Add prompt diff tool to see what changed

## Related Files

- [generate_prompts_from_state.py](generate_prompts_from_state.py) - Main prompt generation logic
- [example_get_latest_prompt.py](example_get_latest_prompt.py) - Example usage
- [play_with_prompts.py](play_with_prompts.py) - Auto-generate prompts during gameplay
