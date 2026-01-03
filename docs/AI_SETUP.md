# 🤖 AI Agent Setup Guide

This guide explains how to set up and configure AI agents for PyCatan.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [API Key Setup](#api-key-setup)
3. [Configuration System](#configuration-system)
4. [Security Best Practices](#security-best-practices)
5. [Development Workflow](#development-workflow)

---

## 🚀 Quick Start

### Step 1: Get an API Key

You need an API key from an LLM provider. We recommend **Google Gemini** for development:

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Create API Key"
3. Copy your API key

**Other providers:**
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/settings/keys

### Step 2: Setup Environment Variables

```bash
# Copy the template file
cp .env.example .env

# Edit .env and paste your API key
# (Use any text editor)
```

Example `.env` file:
```bash
GEMINI_API_KEY=AIzaSyC_your_actual_api_key_here
```

### Step 3: Install Dependencies

```bash
pip install pyyaml
```

### Step 4: Test the Configuration

```bash
python examples/test_ai_config.py
```

You should see:
```
🎉 All tests passed!
```

---

## 🔑 API Key Setup

### Where API Keys Are Stored

**API keys are stored in the `.env` file**, which is:
- ✅ **NOT** committed to Git (protected by `.gitignore`)
- ✅ Stored locally on your machine only
- ✅ Easy to update without changing code

### `.env` File Structure

```bash
# .env - YOUR PRIVATE FILE (never commit this!)
GEMINI_API_KEY=your_actual_key_here
OPENAI_API_KEY=your_openai_key_here      # Optional
ANTHROPIC_API_KEY=your_anthropic_key      # Optional
```

### `.env.example` File

The **`.env.example`** file is a template that:
- ✅ **IS** committed to Git
- ✅ Shows what variables are needed
- ✅ Contains NO actual secrets
- ✅ Helps other developers know what to set up

**Never put real API keys in `.env.example`!**

---

## ⚙️ Configuration System

### Overview

PyCatan uses a **two-file configuration system**:

```
📁 Project Root
├── .env                          # ❌ NOT in Git - API keys
├── .env.example                  # ✅ IN Git - Template
├── pycatan/ai/
│   ├── config_example.yaml       # ✅ IN Git - Documentation
│   ├── config_dev.yaml           # ✅ IN Git - Dev defaults
│   └── my_agent_config.yaml      # ❌ NOT in Git - Your custom config
```

### File Types Explained

#### 1. `.env` - Environment Variables (API Keys)
- **Purpose:** Store sensitive API keys
- **Git:** ❌ **NEVER** committed
- **Contains:** `GEMINI_API_KEY=actual_secret_key`
- **Who creates it:** Each developer on their machine

#### 2. `.env.example` - Environment Template
- **Purpose:** Template showing what variables are needed
- **Git:** ✅ Committed to Git
- **Contains:** `GEMINI_API_KEY=` (empty)
- **Who creates it:** Already created in the project

#### 3. `config_dev.yaml` - Development Defaults
- **Purpose:** Default configuration for development
- **Git:** ✅ Committed to Git
- **Contains:** All settings EXCEPT API keys
- **Who uses it:** Everyone, automatically

#### 4. `config_example.yaml` - Configuration Documentation
- **Purpose:** Complete documentation of all options
- **Git:** ✅ Committed to Git
- **Contains:** All possible settings with explanations
- **Who uses it:** Reference when creating custom configs

#### 5. Your Custom Config (e.g., `my_agent_config.yaml`)
- **Purpose:** Your personal agent configuration
- **Git:** ❌ NOT committed (optional)
- **Contains:** Custom personality, strategies, etc.
- **Who uses it:** You, when you want special behavior

---

## 🔒 Security Best Practices

### ✅ DO:
- Keep your `.env` file local only
- Use different API keys for development and production
- Rotate your API keys regularly
- Review `.gitignore` to ensure `.env` is excluded
- Use `.env.example` as a template for team members

### ❌ DON'T:
- Never commit `.env` to Git
- Never put API keys in configuration YAML files
- Never share your `.env` file
- Never hardcode API keys in Python code
- Never put API keys in commit messages or PR descriptions

### Checking Security

```bash
# Make sure .env is ignored by Git
git status

# .env should NOT appear in the list
# If it does, remove it:
git rm --cached .env
```

---

## 🛠️ Development Workflow

### Using the Default Development Config

The simplest way - just use `config_dev.yaml`:

```python
from pycatan.ai.config import AIConfig

# Loads config_dev.yaml by default
config = AIConfig.from_file('pycatan/ai/config_dev.yaml')

# API key is automatically loaded from .env
api_key = config.get_api_key()  # Reads GEMINI_API_KEY from .env
```

### Creating a Custom Agent

1. **Copy the example config:**
```bash
cp pycatan/ai/config_example.yaml my_aggressive_agent.yaml
```

2. **Edit your config:**
```yaml
agent_name: "Aggressive Trader"
agent:
  personality: "aggressive"
  risk_tolerance: 0.8
  trade_willingness: 0.9
```

3. **Use it in your code:**
```python
config = AIConfig.from_file('my_aggressive_agent.yaml')
```

4. **The API key is still loaded from `.env`** - you don't need to specify it!

### Multiple Agents with Different Personalities

```python
# Agent 1: Aggressive
config1 = AIConfig.from_file('configs/aggressive.yaml')

# Agent 2: Defensive
config2 = AIConfig.from_file('configs/defensive.yaml')

# Agent 3: Balanced (default)
config3 = AIConfig.from_file('pycatan/ai/config_dev.yaml')

# All three use the same API key from .env
```

---

## 📝 Configuration Options

### LLM Settings

```yaml
llm:
  provider: "gemini"              # or "openai", "anthropic"
  model_name: "gemini-2.0-flash-exp"
  temperature: 0.7                # 0.0 = deterministic, 1.0 = creative
  max_tokens: 4096
```

### Agent Personality

```yaml
agent:
  personality: "balanced"         # aggressive, defensive, balanced, trading
  risk_tolerance: 0.5            # 0.0 = safe, 1.0 = risky
  
  # Strategic focus (0.0 to 1.0)
  focus_on_settlements: 0.6
  focus_on_cities: 0.7
  focus_on_roads: 0.5
  focus_on_dev_cards: 0.6
  
  # Trading behavior
  trade_willingness: 0.5         # 0.0 = never, 1.0 = always
  trade_fairness: 0.7            # How fair are trades
```

### Debug Settings

```yaml
debug:
  debug_mode: true               # Enable detailed logging
  log_prompts: true              # Log prompts sent to LLM
  log_responses: true            # Log LLM responses
  save_game_states: true         # Save states for analysis
```

---

## 🧪 Testing Your Setup

### Test 1: Check API Key

```python
from pycatan.ai.config import AIConfig

config = AIConfig()
try:
    api_key = config.get_api_key()
    print("✓ API key loaded successfully")
except ValueError as e:
    print(f"✗ Error: {e}")
```

### Test 2: Load Configuration

```python
config = AIConfig.from_file('pycatan/ai/config_dev.yaml')
print(f"✓ Loaded config for: {config.agent_name}")
print(f"  Provider: {config.llm.provider}")
print(f"  Model: {config.llm.model_name}")
```

### Test 3: Run Full Test Suite

```bash
python examples/test_ai_config.py
```

---

## 🎯 Common Scenarios

### Scenario 1: "I just cloned the repo"

1. Create `.env`: `cp .env.example .env`
2. Add your API key to `.env`
3. Run tests: `python examples/test_ai_config.py`

### Scenario 2: "I want to test different personalities"

Use the existing configs:
- `config_dev.yaml` - Balanced agent
- Or create custom configs based on `config_example.yaml`

### Scenario 3: "I want to switch LLM providers"

Edit your config file:
```yaml
llm:
  provider: "openai"
  model_name: "gpt-4-turbo-preview"
  api_key_env_var: "OPENAI_API_KEY"
```

Add the key to `.env`:
```bash
OPENAI_API_KEY=sk-your-key-here
```

### Scenario 4: "My API key changed"

Just edit `.env` - no code changes needed!

---

## 📚 Next Steps

- Read [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) for system design
- Read [WORK_PLAN.md](WORK_PLAN.md) for development roadmap
- See [config_example.yaml](../pycatan/ai/config_example.yaml) for all options

---

## 🆘 Troubleshooting

### "ModuleNotFoundError: No module named 'yaml'"
```bash
pip install pyyaml
```

### "API key not found"
1. Check `.env` exists in project root
2. Check the API key variable name matches
3. Try: `cat .env` to verify content

### "Configuration file not found"
- Use absolute paths or run from project root
- Check file extension (`.yaml` not `.yml`)

### "Still stuck?"
- Check [GitHub Issues](your-repo-url/issues)
- Review the test output: `python examples/test_ai_config.py`

---

**Last Updated:** January 3, 2026
