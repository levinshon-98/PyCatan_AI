# Intermediate Responses Logging

## 📋 Overview

The system now saves **all intermediate LLM responses** - including raw content when the LLM requests tools instead of providing a final answer.

## 🗂️ Directory Structure

```
session_YYYYMMDD_HHMMSS/
├── Alice/
│   ├── prompts/
│   │   ├── prompt_1.json           # Initial prompt
│   │   └── iterations/
│   │       └── prompt_1_iter2.json # Follow-up with tool results
│   └── responses/
│       ├── response_1.json         # Final response (type: "final")
│       └── intermediate/
│           └── response_1_iter1.json  # NEW! Intermediate response with tool_calls
├── tool_executions.json
└── llm_communication.log
```

## 📝 What Gets Saved

### Intermediate Response Format
Location: `responses/intermediate/response_X_iterY.json`

```json
{
  "request_number": 1,
  "iteration": 1,
  "timestamp": "2026-01-09T16:07:34.123456",
  "player_name": "Alice",
  "type": "intermediate",
  "success": true,
  "raw_content": "...",  // Raw LLM response content
  "has_tool_calls": true,
  "tool_calls": [        // Full tool_calls array from LLM
    {
      "name": "find_best_nodes",
      "parameters": {
        "reasoning": "Looking for high-yield nodes...",
        "min_pips": 10
      }
    }
  ],
  "model": "gemini-2.0-flash-exp",
  "tokens": {
    "prompt": 2172,
    "completion": 79,
    "thinking": 0,
    "total": 2251
  },
  "latency_seconds": 16.234,
  "error": null
}
```

### Final Response Format
Location: `responses/response_X.json`

```json
{
  "request_number": 1,
  "timestamp": "2026-01-09T16:09:24.617751",
  "player_name": "Alice",
  "type": "final",       // Marked as final
  "success": true,
  "raw_content": "...",  // Final structured response
  "parsed": {            // Parsed action
    "action_type": "place_starting_settlement",
    "parameters": {"node": 43}
  },
  "model": "gemini-2.0-flash-exp",
  "tokens": {
    "prompt": 3538,      // Accumulated tokens
    "completion": 355,
    "thinking": 5366,
    "total": 13070       // Total including all iterations + tools
  },
  "latency_seconds": 26.136,
  "error": null
}
```

## 🔄 Complete Flow Example

1. **Initial Prompt** → `prompts/prompt_1.json`
2. **LLM Response (requests tools)** → `responses/intermediate/response_1_iter1.json` ✨ **NEW!**
3. **Tool Execution** → `tool_executions.json`
4. **Follow-up Prompt** → `prompts/iterations/prompt_1_iter2.json`
5. **Final Response** → `responses/response_1.json`

## 🎯 Benefits

1. **Complete Audit Trail** - Every LLM interaction is saved
2. **Debug Tool Requests** - See exactly what the LLM asked for
3. **Analyze Reasoning** - Understand why tools were requested
4. **Replay Capability** - Can reconstruct entire conversation
5. **Cost Tracking** - Token counts for each iteration

## 📊 Usage

The intermediate responses are automatically saved by `AILogger.log_intermediate_response()` whenever the LLM returns `tool_calls` instead of a final answer.

No changes needed to your code - it happens automatically!

## 🔍 Finding Intermediate Responses

```python
from pathlib import Path

session_dir = Path("examples/ai_testing/my_games/session_20260109_160732")

# Find all intermediate responses for Alice
intermediate_dir = session_dir / "Alice" / "responses" / "intermediate"
for response_file in intermediate_dir.glob("*.json"):
    print(f"Found: {response_file.name}")
```

## 💡 Why This Matters

Previously, when the LLM requested tools, we only saved:
- That tools were requested (in logs)
- Which tools (in `tool_executions.json`)
- The follow-up prompt (in `iterations/`)

Now we **also save**:
- ✅ The raw LLM response content
- ✅ Full tool_calls structure
- ✅ Token counts for this specific iteration
- ✅ Timing information
- ✅ Any error messages

This gives complete visibility into the AI agent's decision-making process!
