# Candidate OpenRouter probe

Prompt: `C:/GIT_new/PyCatan_AI/examples/ai_testing/my_games/session_20260516_032115/Shon/prompts/prompt_2.json`

| Model | OK | Latency | Finish | Tools | Price prompt | Price completion | Error |
|---|---:|---:|---|---:|---:|---:|---|
| `google/gemini-2.5-flash-lite` | True | 2.039 | stop | 0 | 0.0000001 | 0.0000004 |  |
| `google/gemini-2.5-flash` | True | 3.429 | stop | 0 | 0.0000003 | 0.0000025 |  |
| `google/gemini-2.0-flash-lite-001` | True | 2.033 | stop | 0 | 0.000000075 | 0.0000003 |  |
| `google/gemini-2.0-flash-001` | True | 1.967 | stop | 0 | 0.0000001 | 0.0000004 |  |
| `google/gemini-2.5-pro` | True | 12.908 | length | 0 | 0.00000125 | 0.00001 |  |
| `anthropic/claude-haiku-4.5` | False | 1.604 |  |  | 0.000001 | 0.000005 | {"error":{"message":"Provider returned error","code":400,"metadata":{"raw":"{\"message\":\"output_config.format.schema:  |
| `~anthropic/claude-haiku-latest` | False | 1.682 |  |  | 0.000001 | 0.000005 | {"error":{"message":"Provider returned error","code":400,"metadata":{"raw":"{\"message\":\"output_config.format.schema:  |
| `qwen/qwen3.6-flash` | True | 23.906 | stop | 0 | 0.0000001875 | 0.000001125 |  |
| `qwen/qwen3.5-flash-02-23` | True | 59.41 | stop | 0 | 0.000000065 | 0.00000026 |  |
| `deepseek/deepseek-v4-flash` | True | 14.486 | stop | 0 | 0.000000112 | 0.000000224 |  |
| `mistralai/mistral-small-2603` | True | 2.637 | stop | 0 | 0.00000015 | 0.0000006 |  |
| `mistralai/ministral-8b-2512` | True | 56.748 | stop | 0 | 0.00000015 | 0.00000015 |  |