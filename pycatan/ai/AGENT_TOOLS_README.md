# Agent Tools - Helper Functions for LLM AI Agents

## 📋 Overview

This module provides **3 powerful tools** that help the LLM AI agent make better decisions in Catan:

1. **calculate_building_costs** - Check resource requirements and affordability
2. **evaluate_node_value** - Rate settlement positions by resource value
3. **check_winning_path** - Analyze strategies to reach 10 victory points

These tools are designed to be:
- ✅ **Easy to use** - Simple function calls with clear outputs
- ✅ **LLM-friendly** - Return structured data that LLMs can understand
- ✅ **Strategic** - Help agent reason about game decisions
- ✅ **Extensible** - Easy to add more tools in the future

---

## 🛠️ The 3 Tools

### Tool 1: Calculate Building Costs

**Purpose:** Help the agent understand what resources it needs to build something.

**Use cases:**
- "Can I afford to build a city?"
- "What resources am I missing for a settlement?"
- "Should I trade for brick to complete a road?"

**Example:**
```python
from pycatan.ai.agent_tools import AgentTools

tools = AgentTools()
result = tools.calculate_building_costs(
    building_type="settlement",
    current_resources={"wood": 1, "brick": 0, "wheat": 1, "sheep": 1}
)

print(result)
# Output:
# {
#     "can_afford": False,
#     "required": {"wood": 1, "brick": 1, "wheat": 1, "sheep": 1},
#     "missing": {"brick": 1},
#     "excess": {}
# }
```

**Building types:**
- `settlement` - Requires: wood, brick, wheat, sheep (1 each)
- `city` - Requires: wheat (2), ore (3)
- `road` - Requires: wood, brick (1 each)
- `development_card` - Requires: wheat, sheep, ore (1 each)

---

### Tool 2: Evaluate Node Value

**Purpose:** Rate how valuable a settlement position is based on surrounding tiles.

**Use cases:**
- "Which of these 3 positions should I choose for my starting settlement?"
- "Is this position with a harbor better than one with high-value tiles?"
- "What resources will I get from this location?"

**Example:**
```python
from pycatan.ai.agent_tools import AgentTools

tools = AgentTools()
result = tools.evaluate_node_value(
    node_tiles=[
        {"resource": "wheat", "number": 6},  # High probability (5 pips)
        {"resource": "wood", "number": 8},   # High probability (5 pips)
        {"resource": "brick", "number": 5}   # Good probability (4 pips)
    ],
    include_harbor=False
)

print(result)
# Output:
# {
#     "total_pip_value": 14,          # Sum of probability dots
#     "resource_diversity": 3,        # 3 different resources
#     "resources": {                  # Resources weighted by probability
#         "wheat": 5,
#         "wood": 5, 
#         "brick": 4
#     },
#     "best_number": 6,               # Best dice number here
#     "overall_score": 15.5           # Overall value rating
# }
```

**Scoring system:**
- **Pip values** (probability): 6/8 = 5 pips, 5/9 = 4 pips, 4/10 = 3 pips, 3/11 = 2 pips, 2/12 = 1 pip
- **Diversity bonus**: +0.5 per unique resource type
- **Harbor bonus**: +2.0 for any harbor, +0.5 extra for specialized harbor (e.g., ore harbor)
- **Overall score**: Combines all factors into single rating

**Interpretation:**
- 15+ = Excellent position (build here!)
- 10-14 = Good position
- 7-9 = Mediocre position
- <7 = Poor position (avoid if possible)

---

### Tool 3: Check Winning Path

**Purpose:** Analyze what the agent needs to do to reach 10 victory points and win.

**Use cases:**
- "How close am I to winning?"
- "Should I focus on cities or development cards?"
- "What's the fastest path to victory?"

**Example:**
```python
from pycatan.ai.agent_tools import AgentTools

tools = AgentTools()
result = tools.check_winning_path(
    current_vp=7,
    settlements=3,
    cities=1,
    longest_road_owned=True,
    largest_army_owned=False
)

print(result)
# Output:
# {
#     "current_vp": 7,
#     "vp_needed": 3,
#     "paths_to_victory": [
#         "Build 2 more cities (3 VP needed, 2 cities = 4 VP gain)",
#         "Build 3 settlements (if space available on board)",
#         "Get Largest Army card (2 VP) - need 3+ knights played",
#         ...
#     ],
#     "recommendations": [
#         "Cities are efficient! You need 2 more.",
#         "Buy development cards to try for knights"
#     ],
#     "breakdown": {
#         "settlements": 3,
#         "cities": 1,
#         "longest_road": true,
#         "largest_army": false
#     }
# }
```

**Victory point sources:**
- Settlement = 1 VP (max 5)
- City = 2 VP (max 5, built on settlements)
- Longest Road = 2 VP (need 5+ connected roads)
- Largest Army = 2 VP (need 3+ knights played)
- Development cards = 1 VP each (University, Library, etc.)

---

## 🔌 Integration with LLM

### Option 1: Function Calling / Tool Use

Modern LLMs (GPT-4, Claude, Gemini) support function calling. You can pass the tool schemas directly:

```python
from pycatan.ai.agent_tools import AgentTools

tools = AgentTools()

# Get schemas for LLM
tool_schemas = tools.get_tools_schema()

# Send to LLM (example with OpenAI)
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Should I build at position 14?"}],
    functions=tool_schemas,
    function_call="auto"
)

# If LLM calls a tool
if response.get("function_call"):
    tool_name = response["function_call"]["name"]
    parameters = json.loads(response["function_call"]["arguments"])
    
    # Execute the tool
    result = tools.execute_tool(tool_name, parameters)
    print(result)
```

### Option 2: Include in Prompt

You can also describe the tools in the system prompt and have the LLM "call" them by outputting JSON:

```python
system_prompt = """
You have access to 3 helper tools:

1. calculate_building_costs(building_type, current_resources)
   - Returns whether you can afford to build and what's missing
   
2. evaluate_node_value(node_tiles, include_harbor, harbor_type)
   - Rates a settlement position by resource value
   
3. check_winning_path(current_vp, settlements, cities, ...)
   - Shows paths to reach 10 VP and win

To use a tool, output: TOOL: tool_name(parameters)
"""
```

### Option 3: Pre-calculate and Include in State

For simpler integration, you can run the tools beforehand and include results in the game state:

```python
# Before sending state to LLM
game_state["tool_results"] = {
    "can_afford_settlement": tools.calculate_building_costs(
        "settlement", player.resources
    ),
    "best_available_position": max(
        available_positions,
        key=lambda pos: tools.evaluate_node_value(pos["tiles"])["overall_score"]
    ),
    "winning_strategy": tools.check_winning_path(
        player.vp, player.settlements, player.cities
    )
}
```

---

## 📊 Testing

Run the test suite to see all tools in action:

```bash
python examples/test_agent_tools.py
```

This will show:
- ✅ All 3 tools working with various scenarios
- ✅ Tool schema generation for LLM integration
- ✅ Tool dispatcher/executor functionality

---

## 🚀 Next Steps

### Immediate:
1. Integrate tools with `AIManager.process_agent_turn()`
2. Update prompts to mention available tools
3. Parse tool calls from LLM responses

### Future enhancements:
4. Add more tools:
   - `analyze_trade_offer(give, receive)` - Evaluate trade fairness
   - `predict_opponent_move(opponent_state)` - Anticipate opponent strategy
   - `find_best_road_path(from_node, to_node)` - Pathfinding for Longest Road
   - `calculate_robber_impact(tile)` - Evaluate where to place robber
5. Add tool usage to agent state/memory
6. Log which tools agent uses and why

---

## 🏗️ Architecture

```
┌─────────────────┐
│   AIManager     │  <- Coordinates everything
└────────┬────────┘
         │
         ├──> PromptManager     (creates prompts)
         ├──> LLMClient         (sends to LLM)
         ├──> ResponseParser    (parses responses)
         └──> AgentTools  ✨    (helper tools - NEW!)
                  │
                  ├─> calculate_building_costs()
                  ├─> evaluate_node_value()
                  └─> check_winning_path()
```

**Design principles:**
- **Stateless tools** - Each tool call is independent
- **Pure functions** - No side effects, just calculations
- **Clear outputs** - Structured data the LLM can easily use
- **Extensible** - Easy to add new tools without breaking existing ones

---

## 📝 Notes

- Tools are **read-only** - They don't modify game state, only provide information
- Tools are **fast** - All calculations are lightweight (no AI calls)
- Tools are **accurate** - Use exact Catan rules for costs and scoring
- Tools provide **context** - Help LLM understand "why" not just "what"

---

## 🤝 Contributing

To add a new tool:

1. Add the function to `AgentTools` class
2. Add comprehensive docstring with examples
3. Add to `get_tools_schema()` for LLM integration
4. Add to `execute_tool()` dispatcher
5. Add tests in `examples/test_agent_tools.py`

**Tool naming convention:**
- Use verbs: `calculate_`, `evaluate_`, `check_`, `analyze_`, `find_`
- Be specific: `calculate_building_costs` not `get_costs`
- Stay focused: One clear purpose per tool
