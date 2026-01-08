# 🧠 Thinking Mode Setup Guide

## Overview

Gemini 2.0 Flash introduces **thinking mode** - the model explicitly "thinks" through problems before responding. This generates higher quality responses for complex tasks like game strategy.

---

## 🚀 Quick Start

### 1. Switch to Thinking Model

**Option A: Edit config.yaml** (Recommended)
```yaml
llm:
  model_name: "gemini-2.0-flash-thinking-exp"
  enable_thinking: true
  thinking_budget: 16000  # Max tokens for thinking (8k-32k)
```

**Option B: Edit config.py** (For default settings)
```python
@dataclass
class LLMConfig:
    model_name: str = "gemini-2.0-flash-thinking-exp"
    enable_thinking: bool = True
    thinking_budget: int = 16000
```

### 2. Run Your Game

```bash
python play_catan.py
```

The AI will now use thinking mode automatically!

---

## 📊 How to Monitor Thinking

### In Console Logs

Look for thinking token counts:
```
✅ Response received: 450 tokens (+1200 thinking), 3.5s
```

### In Log Files

**JSON logs** (`examples/ai_testing/my_games/AI_Agent_1/prompt_1.json`):
```json
{
  "tokens": {
    "prompt": 1523,
    "completion": 450,
    "thinking": 1200,
    "total": 3173
  }
}
```

**TXT logs** (`examples/ai_testing/my_games/AI_Agent_1/prompt_1.txt`):
```
Tokens: prompt=1523, completion=450, thinking=1200, total=3173
```

### In Web Viewer

Visit: http://localhost:5001

The viewer will show:
- 📊 Token breakdown including thinking tokens
- 💰 Cost calculation (thinking tokens = input cost)
- 📈 Thinking usage trends

---

## ⚙️ Configuration Options

### Model Selection

| Model | Thinking | Speed | Quality |
|-------|----------|-------|---------|
| `gemini-2.0-flash-exp` | ❌ | ⚡ Fast | Good |
| `gemini-2.0-flash-thinking-exp` | ✅ | 🐢 Slower | Better |

### Thinking Budget

Controls max tokens the model can use for thinking:

```yaml
thinking_budget: 16000  # Recommended: 8000-32000
```

- **Lower (8k)**: Faster, less thorough
- **Medium (16k)**: Balanced (default)
- **Higher (32k)**: Slower, more thorough

### Enable/Disable

```yaml
enable_thinking: true   # Turn on thinking mode
enable_thinking: false  # Turn off (faster, cheaper)
```

---

## 💰 Cost Impact

**Thinking tokens are charged as input tokens:**

Example (16k thinking budget):
- Standard mode: ~450 output tokens = $0.000034
- Thinking mode: ~1200 thinking + 450 output = $0.000056

**~1.6x cost increase for better decisions** 🎯

---

## 🔍 Viewing the Schema

The **response schema** is logged in TXT files for debugging:

```
=== Prompt #1 (Active Turn) ===

--- Response Schema ---
{
  "type": "object",
  "properties": {
    "internal_thinking": {
      "type": "string",
      "description": "Your reasoning process...",
      "minLength": 200
    },
    ...
  }
}

--- Prompt Content ---
{
  "meta_data": { ... }
}
```

Location: `examples/ai_testing/my_games/AI_Agent_1/prompt_N.txt`

---

## ✅ Testing Thinking Mode

### Quick Test

1. Edit `pycatan/ai/config.py`:
   ```python
   model_name: str = "gemini-2.0-flash-thinking-exp"
   enable_thinking: bool = True
   ```

2. Run a game:
   ```bash
   python play_catan.py
   ```

3. Check console output for thinking tokens:
   ```
   ✅ Response received: 450 tokens (+1200 thinking), 3.5s
   ```

4. View logs:
   ```bash
   # Check TXT file
   cat examples/ai_testing/my_games/AI_Agent_1/prompt_1.txt
   
   # Or JSON
   cat examples/ai_testing/my_games/AI_Agent_1/prompt_1.json
   ```

### Web Viewer

```bash
cd examples/ai_testing
python web_viewer.py
```

Visit http://localhost:5001 to see:
- Token breakdowns with thinking
- Cost calculations
- Response quality metrics

---

## 🐛 Troubleshooting

### Not Seeing Thinking Tokens?

1. **Check model name**: Must be `gemini-2.0-flash-thinking-exp`
2. **Check enable_thinking**: Must be `true` in config
3. **Check logs**: Look for "enable_thinking" in debug output

### Error: "thinking_config not supported"

- Your model doesn't support thinking mode
- Switch to: `gemini-2.0-flash-thinking-exp`

### High Costs?

- Reduce `thinking_budget` (e.g., 8000)
- Or disable thinking: `enable_thinking: false`

---

## 📚 Configuration Files

### Location

- **Active config**: `pycatan/ai/config_dev.yaml`
- **Example**: `pycatan/ai/config_example.yaml`
- **Defaults**: `pycatan/ai/config.py`

### Priority

1. Config YAML file (if exists)
2. Default values in `config.py`

---

## 🎯 Summary

**To enable thinking mode:**

1. Set `model_name: "gemini-2.0-flash-thinking-exp"`
2. Set `enable_thinking: true`
3. Set `thinking_budget: 16000` (optional)
4. Run your game
5. Check logs for thinking token counts

**Benefits:**
- ✅ Better strategic decisions
- ✅ More thorough reasoning
- ✅ Higher quality play

**Trade-offs:**
- ⏱️ Slower responses (~2-5s)
- 💰 Higher costs (~1.5-2x)

