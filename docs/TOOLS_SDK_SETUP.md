# 🔧 Tool Calling Setup - SDK Requirements

## ⚠️ Important: SDK Installation Required

The tool calling feature requires the **new Google GenAI SDK** to be installed.

### 📦 Installation

```bash
pip install google-genai
```

### 🔍 Verification

Check if installed correctly:
```bash
python -c "from google import genai; print('✅ SDK installed successfully')"
```

### 📋 Current Status

Without the SDK installed, the system will:
- ✅ Run normally without tool calling
- ⚠️ Display warning: "Tools will be disabled. Install google-genai SDK..."
- ❌ Function calling will not work

### 🚀 After Installation

Once installed, the AI will be able to:
1. Call `inspect_node()` to get node information
2. Call `find_best_nodes()` to search for optimal positions
3. Call `analyze_path_potential()` to plan road building
4. Use dynamic thinking budgets per iteration

### 🔗 More Information

- **SDK Documentation:** https://github.com/googleapis/python-genai
- **Tool Integration Docs:** [docs/TOOLS_INTEGRATION.md](../../docs/TOOLS_INTEGRATION.md)
- **Test Tools:** `python examples/ai_testing/test_tools_integration.py`

---

## 📝 Notes

- The old `google-generativeai` package is different and won't work
- Use the new `google-genai` package (note the hyphen!)
- Tool calling works with Gemini 2.0+ models
- Thinking mode requires `gemini-2.0-flash-thinking-exp` model
