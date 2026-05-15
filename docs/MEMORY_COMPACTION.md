# AI Memory Compaction

This document explains how AI agent memory compaction works, how to inspect it,
what happened in the latest checked session, and what can be improved next.

## Goal

Each AI agent writes a `note_to_self` after decisions. If we keep every note in
the prompt forever, memory grows quickly and wastes tokens. Memory compaction
keeps a short long-term summary and preserves only the newest notes verbatim.

Expected behavior:

- When an agent reaches 10 entries in `memory_history`, compaction is triggered.
- The newest 2 notes are kept exactly as they are.
- Older notes are summarized together with relevant recent chat.
- The summary is stored as `long_term_summary`.
- Future prompts include `long_term_summary`, `note_from_last_turn`, and the
  remaining `recent_notes`.

## Configuration

The settings live in `pycatan/ai/config.py` and `pycatan/ai/config_dev.yaml`:

```yaml
memory:
  enable_memory_compaction: true
  memory_compaction_threshold: 10
  memory_compaction_keep_recent: 2
  memory_compaction_chat_messages: 20
  memory_compaction_max_tokens: 800
```

`play_ai_auto.bat` runs `examples/ai_testing/play_with_ai.py --auto`, which
loads `pycatan/ai/config_dev.yaml` by default. In normal auto mode, compaction is
enabled.

Compaction is skipped when LLM calls are disabled, for example in `--no-llm` or
watch-only replay mode.

## Code Flow

The main flow is:

1. The model returns a response with `note_to_self`.
2. `AgentState.update_memory()` appends the note to `memory_history`.
3. `AIManager._maybe_compact_agent_memory()` checks the threshold.
4. `AIManager._normalize_compaction_game_state()` ensures the state is in the
   compact prompt format.
5. `MemoryCompactor` builds and sends a compaction prompt.
6. The same active `llm_client` and model are used, without tools.
7. On success:
   - `AgentState.apply_memory_compaction()` stores `compacted_memory`.
   - `memory_history` is reduced to the newest 2 notes.
   - `agent_memories.json` is updated.
   - before/after inspection artifacts are written.

Important files:

- `pycatan/ai/agent_state.py`
- `pycatan/ai/ai_manager.py`
- `pycatan/ai/memory_compactor.py`
- `pycatan/ai/ai_logger.py`

## Board Format

Compaction uses the same compact board format as normal decision prompts. It
does not use a separate prose board summary.

The compaction prompt receives:

- `H`: hex lookup array by HexID.
- `N`: node lookup array by NodeID.
- `state.bld`: current settlements/cities.
- `state.rds`: current roads.
- `players`: compact player data.
- `meta`: current player, phase, robber, dice.

This keeps compaction aligned with the prompt format the model already uses for
game decisions, and it keeps token usage lower.

## Inspecting Before And After

When compaction succeeds, artifacts are written under the player directory:

```text
examples/ai_testing/my_games/session_YYYYMMDD_HHMMSS/<Player>/memory_compactions/
```

Files:

```text
compaction_1.txt
compaction_1.json
```

The text artifact is easiest to read. It contains:

- `BEFORE: Existing Long-Term Summary`
- `BEFORE: Old Notes Compacted`
- `BEFORE: Recent Notes Kept Verbatim`
- `BEFORE: Relevant Chat Considered`
- `AFTER: New Long-Term Summary`
- `AFTER: Discarded As Irrelevant`

The JSON artifact also includes the full compaction prompt.

You can also inspect:

```text
examples/ai_testing/my_games/session_YYYYMMDD_HHMMSS/agent_memories.json
```

Healthy output should look like:

```json
{
  "long_term_summary": "...",
  "recent_notes": [
    {"note": "..."},
    {"note": "..."}
  ],
  "compaction_count": 1
}
```

The communication log should include:

```text
[MEMORY] Compacting memory for ...
[MEMORY] Memory compacted for ...
```

## Latest Session Check

Checked session:

```text
examples/ai_testing/my_games/session_20260516_020509
```

Compaction did trigger, but it did not work as expected in that run.

Example from `llm_communication.log`:

```text
[02:05:12] [MEMORY] Compacting memory for Hadar (10 notes)
[02:05:15] [ERROR] Memory compaction failed for Hadar: Object of type GameState is not JSON serializable
```

Later attempts reached the model but still did not produce usable summaries:

```text
[MEMORY] Compacting memory for Ziv (26 notes)
[WARNING] Memory compaction produced no usable summary for Ziv
```

The final `agent_memories.json` confirmed that no compaction was applied:

```text
Hadar: compaction_count=0, long_term_summary=null, recent_notes=40
Shon:  compaction_count=0, long_term_summary=null, recent_notes=39
Ziv:   compaction_count=0, long_term_summary=null, recent_notes=34
```

That is unhealthy: after successful compaction, `recent_notes` should drop back
to about 2 and `long_term_summary` should be populated.

## Fix Applied After This Check

The main bug was in replay memory handling. In that path, compaction received a
raw `GameState` object instead of the compact dict used by normal prompts. That
made JSON serialization fail.

The fix:

- `AIManager._normalize_compaction_game_state()` now normalizes any state before
  compaction.
- If the state already has `H/N/state/players/meta`, it is used as-is.
- Otherwise it is converted through `game_state_to_dict()` and
  `optimize_state_for_ai()`.

The compaction response parser was also made more tolerant:

- Plain JSON is accepted.
- JSON wrapped in a fenced code block is accepted.
- If needed, the parser attempts to extract the first JSON object from the text.

## Example Of Healthy Compaction

Before compaction:

```text
memory_history = [note1, note2, ..., note10]
```

After compaction:

```text
long_term_summary = "Hadar leads with 4 VP and strong wood/brick access. Shon needs wood+brick for node 18. Ziv needs to clear the robber from Ore 5..."
recent_notes = [note9, note10]
compaction_count = 1
```

The next prompt should include:

```json
"memory": {
  "note_from_last_turn": "...",
  "recent_notes": ["...", "..."],
  "long_term_summary": "..."
}
```

## Improvement Ideas

1. Add cooldown/backoff after compaction failure so the system does not retry on
   every new note.
2. Write failure artifacts too, including the compaction prompt and raw model
   response.
3. Add an integration test that creates 10 notes and asserts:
   - `compaction_count` increments.
   - `long_term_summary` is populated.
   - `memory_history` shrinks to 2 entries.
4. Add an explicit character budget to the compaction prompt, not only "about
   50%".
5. Show compaction status in the web viewer: last success/failure, count, and
   long-term summary.
6. Include pending trades and recent trade history in compaction input, not only
   chat and notes.

## Health Checklist

Healthy:

- `compaction_count` increases.
- `long_term_summary` is not null.
- `recent_notes` stays near 2 after compaction.
- `memory_compactions/compaction_N.txt` exists.
- `llm_communication.log` includes `Memory compacted for ...`.

Unhealthy:

- `compaction_count=0` despite more than 10 notes.
- `recent_notes` grows into dozens of entries.
- No `memory_compactions` directory exists.
- `llm_communication.log` shows repeated `ERROR` or `WARNING` entries for
  compaction.
