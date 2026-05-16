# Light OpenRouter Probe

| Model | Request | Tool calls | JSON | Action | Finish | Latency | Tokens | Error |
|---|---:|---:|---:|---:|---|---:|---:|---|
| openai/gpt-5.4-mini | fail | 0 | - | - | None | 1.014s | 0 | {"error":{"message":"No endpoints found that can handle the requested parameters. To learn more abou |
| anthropic/claude-haiku-4.5 | ok | 3 | - | - | tool_calls | 5.34s | 6208 |  |
| google/gemini-3.1-flash-lite | ok | 1 | - | - | tool_calls | 2.489s | 4602 |  |
| google/gemini-3-flash-preview | ok | 1 | - | - | tool_calls | 2.016s | 4590 |  |
| openai/gpt-4o-mini | ok | 2 | - | - | tool_calls | 2.341s | 4071 |  |
