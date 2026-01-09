# 🔧 Tool Calling System for AI Agents

## 📋 Overview

The PyCatan AI system now supports **function calling** (tool use) for LLM agents. This allows the AI to query specific information about the game state instead of trying to interpret raw data, which **prevents hallucinations** and improves decision quality.

## 🎯 Key Features

### ✅ Complete Tool System
- **3 powerful tools** for game state analysis
- **Multiple tool calls** in a single turn
- **Automatic execution** and result formatting
- **Full logging** with token tracking

### ✅ Token Tracking
- Input tokens (tool parameters)
- Output tokens (tool results)
- Separate tracking from LLM tokens
- Cost calculation for tool usage

### ✅ Detailed Logging
- Every tool call logged with parameters
- Execution time per tool
- Success/failure status
- Results preview in logs
- Separate `tool_executions.json` file

### ✅ LLM Integration
- Works with Gemini function calling
- Supports multiple iterations
- Automatic tool result formatting
- Seamless conversation flow

---

## 🛠️ Available Tools

### 1. **inspect_node**
Get detailed information about a specific node.

**Use case:** "What resources does node 14 provide?"

**Parameters:**
- `node_id` (int): The node to inspect

**Returns:**
```json
{
  "node_id": 14,
  "exists": true,
  "resources": {"Wheat": 6, "Wood": 8, "Brick": 5},
  "total_pips": 14,
  "port": "3:1",
  "neighbors": [10, 11, 18],
  "occupied": false,
  "can_build_here": true
}
```

### 2. **find_best_nodes**
Search for the best available nodes matching criteria.

**Use case:** "Find the best spots with high ore production"

**Parameters:**
- `min_pips` (int): Minimum pip value (default: 0)
- `must_have_resource` (str): Required resource (optional)
- `exclude_blocked` (bool): Skip unbuildable nodes (default: true)
- `prefer_port` (bool): Prioritize ports (default: false)
- `limit` (int): Max results (default: 10)

**Returns:**
```json
{
  "query": {...},
  "total_found": 15,
  "nodes": [
    {
      "node_id": 18,
      "resources": {"Ore": 10, "Wheat": 6},
      "total_pips": 13,
      "port": null,
      "score": 15.0
    },
    ...
  ]
}
```

### 3. **analyze_path_potential**
Analyze where roads lead and what opportunities exist ahead.

**Use case:** "If I build a road from node 10, what can I reach?"

**Parameters:**
- `from_node` (int): Starting node
- `direction_node` (int): Specific direction (optional)
- `max_depth` (int): How far to look (1 or 2, default: 2)

**Returns:**
```json
{
  "from_node": 10,
  "total_directions": 3,
  "paths": [
    {
      "direction": 14,
      "depth_1": {
        "node_id": 14,
        "total_pips": 12,
        "port": "3:1"
      },
      "depth_2": {
        "best_node": 18,
        "best_pips": 13
      },
      "highlights": ["Port (3:1) at depth 1"],
      "score": 14.5
    },
    ...
  ]
}
```

---

## 🔄 How It Works

### Architecture Flow

```
┌─────────────┐
│ AI Manager  │
└──────┬──────┘
       │
       ├─────► Update AgentTools with game state
       │
       ├─────► Send prompt to LLM (with tool schemas)
       │
       ▼
┌─────────────────┐
│   LLM Client    │  ◄──── Tools available via function calling
└────────┬────────┘
         │
         ├──── Response with tool_calls?
         │
         ▼ YES
┌──────────────────┐
│  Tool Executor   │
└────────┬─────────┘
         │
         ├─────► Execute each tool call
         ├─────► Log execution (time, tokens)
         ├─────► Format results
         │
         ▼
     Back to LLM with results ──► Final answer
```

### Execution Loop

1. **Prompt sent** with tool schemas
2. **LLM decides** to call one or more tools
3. **Tools executed** in parallel
4. **Results logged** with full details
5. **Results sent back** to LLM
6. **LLM provides** final answer based on tool data

**Maximum iterations:** 5 (prevents infinite loops)

---

## 📊 Logging & Tracking

### Tool Execution Log
Every tool call is logged to `tool_executions.json`:

```json
[
  {
    "timestamp": "2026-01-09T12:34:56",
    "total_calls": 2,
    "successful": 2,
    "failed": 0,
    "total_time_ms": 45.2,
    "tokens": {
      "input": 15,
      "output": 127,
      "total": 142
    },
    "calls": [
      {
        "id": "call_1",
        "name": "inspect_node",
        "parameters": {"node_id": 14},
        "result": {...},
        "success": true,
        "execution_time_ms": 12.3,
        "tokens": {
          "input": 5,
          "output": 45,
          "total": 50
        }
      },
      ...
    ]
  }
]
```

### LLM Communication Log
Tool activity is logged to `llm_communication.log`:

```
[12:34:56] [TOOL_REQUEST] 🔧 LLM requested 2 tool(s) (iteration 1)
[12:34:56] [TOOL] === Tool Execution Batch (2 calls) ===
[12:34:56] [TOOL]   ✅ inspect_node({"node_id": 14})
[12:34:56] [TOOL]      Time: 12.3ms | Tokens: 5 in + 45 out = 50 total
[12:34:56] [TOOL]      Result: {"node_id": 14, "exists": true...
[12:34:56] [TOOL]   ✅ find_best_nodes({"min_pips": 10})
[12:34:56] [TOOL]      Time: 32.9ms | Tokens: 10 in + 82 out = 92 total
[12:34:56] [TOOL]   Total: 2/2 successful | 142 tokens | 45.2ms
[12:34:56] [TOOL_RESULTS] ✅ Tool results sent back to LLM (142 tokens)
```

### Token Statistics
The LLM stats now include tool tokens:

```python
{
  "total_requests": 5,
  "total_tokens": 15432,
  "tool_tokens": 1250,      # From tool inputs/outputs
  "llm_tokens": 14182,      # From prompts/completions
  "total_cost_usd": "$0.0145"
}
```

---

## 🧪 Testing

### Run the Test Suite
```bash
python examples/ai_testing/test_tools_integration.py
```

This tests:
1. ✅ Basic tool operations
2. ✅ Multiple tool calls in batch
3. ✅ Tool schema generation
4. ✅ Execution history and statistics

### Expected Output
```
🧪 Testing Tool Integration for AI Agents

============================================================
TEST 1: Basic Tool Operations
============================================================
✅ Initialized AgentTools with 54 nodes

🔧 Testing: inspect_node(10)
{
  "node_id": 10,
  "exists": true,
  "resources": {"Wheat": 6, "Wood": 8},
  "total_pips": 10,
  ...
}

...

============================================================
✅ All Tests Passed!
============================================================
```

---

## 💻 Usage Examples

### Example 1: Enable Tools in AI Manager
Tools are **automatically enabled** when you use AIManager:

```python
from pycatan.ai.ai_manager import AIManager

# Create AI manager
ai_manager = AIManager()

# Register agent
ai_manager.register_agent("Alice", player_id=0)

# Process turn (tools automatically available)
result = ai_manager.process_agent_turn(
    player_name="Alice",
    game_state=game_state,
    prompt_message="Your turn",
    allowed_actions=["build_settlement"]
)
```

### Example 2: Direct Tool Usage
You can also use tools directly:

```python
from pycatan.ai.agent_tools import AgentTools

# Initialize with game state
tools = AgentTools(game_state)

# Inspect a specific node
node_info = tools.inspect_node(14)
print(f"Node 14 has {node_info['total_pips']} pips")

# Find best locations
best_nodes = tools.find_best_nodes(min_pips=10, limit=5)
print(f"Found {len(best_nodes['nodes'])} great spots")

# Analyze road potential
paths = tools.analyze_path_potential(from_node=10, max_depth=2)
print(f"Best direction: {paths['paths'][0]['direction']}")
```

### Example 3: Get Tool Execution Summary
```python
# After game ends
summary = ai_manager.tool_executor.get_execution_summary()

print(f"Total tool calls: {summary['total_calls']}")
print(f"Success rate: {summary['success_rate']}")
print(f"Total tokens: {summary['total_tokens']}")

# Tool usage breakdown
for tool_name, count in summary['tool_usage'].items():
    print(f"  {tool_name}: {count} times")
```

---

## 🎮 Real Game Usage

### What the LLM Sees

When the LLM receives a prompt, it also gets tool schemas:

```json
{
  "tools": [
    {
      "name": "inspect_node",
      "description": "Get detailed information about a node. Prevents hallucinations!",
      "parameters": {
        "type": "object",
        "properties": {
          "node_id": {
            "type": "integer",
            "description": "The node ID to inspect"
          }
        },
        "required": ["node_id"]
      }
    },
    ...
  ]
}
```

### LLM Decision Process

1. **LLM thinks:** "I need to know about node 14 before deciding"
2. **LLM calls:** `inspect_node(node_id=14)`
3. **Tool executes:** Returns detailed node info
4. **LLM receives:** Complete accurate data
5. **LLM decides:** "Based on the data, I'll build there"

### Benefits Over Raw Data

**Without tools:**
```
"Looking at Array N, I think node 14 has wheat and wood..." ❌ (hallucination)
```

**With tools:**
```
*calls inspect_node(14)*
"The tool confirms node 14 has 12 pips with ore and wheat..." ✅ (accurate)
```

---

## 📁 File Structure

```
pycatan/ai/
├── agent_tools.py         # The 3 tools (inspect, find, analyze)
├── tool_executor.py       # Executes and logs tool calls
├── llm_client.py          # LLM with function calling support
├── ai_manager.py          # Integrates everything
└── ai_logger.py           # Logs tool executions

examples/ai_testing/
├── test_tools_integration.py  # Test suite
└── my_games/
    └── session_YYYYMMDD_HHMMSS/
        ├── tool_executions.json       # Detailed tool logs
        ├── llm_communication.log      # Real-time log
        └── [player_name]/
            ├── prompts/
            └── responses/
```

---

## 🚀 Future Enhancements

### Potential New Tools

1. **evaluate_trade** - Check if a trade is fair
2. **calculate_odds** - Probability of getting specific resources
3. **check_opponent_threats** - Identify threats from opponents
4. **plan_resource_path** - Plan how to get needed resources
5. **estimate_victory_points** - Calculate VP for different strategies

### Advanced Features

- **Tool chaining** - One tool's output feeds into another
- **Cached results** - Avoid re-executing identical calls
- **Parallel execution** - Run independent tools simultaneously
- **Tool suggestions** - AI Manager suggests which tools to use

---

## ⚙️ Configuration

Tools work out-of-the-box, but you can customize:

### Token Estimation
Tools estimate tokens at ~4 chars per token. Adjust in `tool_executor.py`:

```python
def _estimate_tokens(self, text: str) -> int:
    return len(text) // 4  # Adjust divisor for accuracy
```

### Max Tool Iterations
Prevent infinite loops by setting max iterations in `ai_manager.py`:

```python
max_tool_iterations = 5  # Increase if needed
```

### Tool Timeout
Add timeout per tool in `tool_executor.py`:

```python
# Add to _execute_single_tool:
import signal
signal.alarm(5)  # 5 second timeout
```

---

## 🐛 Troubleshooting

### Issue: Tools not called by LLM
**Check:**
- Is `tools` parameter passed to `llm_client.generate()`?
- Are tool schemas valid JSON?
- Does LLM support function calling? (Gemini 2.0+)

### Issue: Wrong tool results
**Check:**
- Is game state updated before calling tools?
- Are node IDs correct in the game state?
- Check `tool_executions.json` for actual parameters used

### Issue: Too many tool iterations
**Check:**
- Is LLM stuck in a loop?
- Are tool results clear enough for LLM to decide?
- Consider adding more context in tool descriptions

---

## 📚 Related Documentation

- [AI_ARCHITECTURE.md](../../.github/instructions/AI_ARCHITECTURE.md) - System architecture
- [AGENT_TOOLS_README.md](../../pycatan/ai/AGENT_TOOLS_README.md) - Tool documentation
- [AI_AGENT_PRINCIPLES.md](../../.github/instructions/AI_AGENT_PRINCIPLES.md) - Design principles

---

## ✅ Summary

The tool calling system provides:

1. **3 powerful tools** for game analysis
2. **Multiple calls** per turn supported
3. **Full logging** with execution details
4. **Token tracking** separate from LLM
5. **Automatic integration** in AIManager
6. **Easy to test** with provided test suite

**Result:** More accurate AI decisions, fewer hallucinations, better gameplay! 🎯

---

**Questions?** Check the test file or open an issue on GitHub.
