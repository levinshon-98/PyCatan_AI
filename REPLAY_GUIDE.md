# AI Game Replay Guide

This guide explains how to resume an AI Catan run from a previous session by fast-replaying recorded actions, then continuing live with the current code.

## Quick Start

Run a previous session up to a point, then continue live:

```powershell
.\play_ai_auto.bat --replay-session session_20260515_211742 --replay-stop-before Alice:10
```

Or replay through an already-fixed action and continue after it:

```powershell
.\play_ai_auto.bat --replay-session session_20260515_211742 --replay-through Alice:10
```

Both commands create a new derived session. The source session is not modified.

Watch a previous session as a visual replay without waiting for the LLM:

```powershell
.\play_ai_auto.bat --watch-replay --replay-session session_20260515_211742 --replay-delay 2.5
```

This opens the normal board/unified view with video-like timeline controls:
play/pause, previous/next, jump to start/end, and a draggable slider. The replay
is rebuilt from recorded parsed actions, so board state, action log, resources,
and chat can be scrubbed backward and forward. Recorded `say_outloud` messages
are shown just before the related action. If TTS is enabled in `.env`, forward
playback speaks those messages before rendering the action; generated clips are
cached under the replayed session's `tts_cache/` folder by default and reused
on later runs of that same session. Use `--replay-text-lead 0.5` to make the
chat appear a little earlier before the game action.

## How Replay Works

Replay reads final parsed responses from:

```text
examples/ai_testing/my_games/<session>/<Player>/responses/response_N.json
```

Each parsed response becomes one replay decision. The replay feeds those decisions back through the normal `GameManager`, so board state, resources, roads, robber state, trades, chat, and memory are rebuilt by game logic instead of copied blindly.

When replayed decisions run out, the game continues with live AI calls.

## Finding The Right Replay Point

A replay marker is:

```text
PlayerName:request_number
```

Examples:

```text
Alice:10
Bob:3
Charlie:8
```

To find the marker:

1. Open the source session folder:

```text
examples/ai_testing/my_games/session_YYYYMMDD_HHMMSS/
```

2. Pick the relevant player folder, then inspect:

```text
<Player>/responses/response_N.json
<Player>/prompts/prompt_N.json
```

3. Use `request_number` from the response/prompt JSON as `N`.

For example, if the bug happened in:

```text
examples/ai_testing/my_games/session_20260515_211742/Alice/responses/response_10.json
```

then the marker is:

```text
Alice:10
```

## `--replay-stop-before` vs `--replay-through`

Use `--replay-stop-before Player:N` when the action at `Player:N` is suspicious or buggy.

```powershell
.\play_ai_auto.bat --replay-session session_20260515_211742 --replay-stop-before Alice:10
```

This replays everything before `Alice:10`, then asks the live AI to regenerate that action with the fixed code. Prefer this when the old action had bad reasoning, stale chat, wrong memory, or invalid parameters.

Use `--replay-through Player:N` when the action at `Player:N` is now known to replay correctly and you want to continue after it.

```powershell
.\play_ai_auto.bat --replay-session session_20260515_211742 --replay-through Alice:10
```

This replays `Alice:10` too. It also replays that action's recorded `say_outloud` and `note_to_self`, so avoid it when the old action contained misleading chat or memory.

## Useful Commands

Show the current active session:

```powershell
Get-Content examples\ai_testing\my_games\current_session.txt
```

List latest sessions:

```powershell
Get-ChildItem examples\ai_testing\my_games -Directory |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 10 Name,LastWriteTime
```

List a player's responses:

```powershell
Get-ChildItem examples\ai_testing\my_games\session_20260515_211742\Alice\responses -File |
  Sort-Object Name |
  Select-Object Name,LastWriteTime
```

Search for failures in a session:

```powershell
Select-String -Path examples\ai_testing\my_games\session_20260515_211742\**\*.json,examples\ai_testing\my_games\session_20260515_211742\llm_communication.log `
  -Pattern "ACTION_FAILED|Invalid|failed|Error|Traceback|not allowed" `
  -CaseSensitive:$false
```

## Reading Derived Session Metadata

Every replay run creates a new session with lineage in:

```text
examples/ai_testing/my_games/<new_session>/session_metadata.json
```

Look for:

```json
{
  "derived_from": "examples\\ai_testing\\my_games\\session_20260515_211742",
  "replay": {
    "source_session": "session_20260515_211742",
    "decisions_loaded": 28,
    "replay_through": "Alice:10",
    "replay_stop_before": null,
    "mode": "fast_action_replay_then_live_ai"
  }
}
```

## Extra Options

Replay only the first N decisions:

```powershell
.\play_ai_auto.bat --replay-session session_20260515_211742 --replay-max-decisions 12
```

Use the lower-level Python entrypoint:

```powershell
python examples\ai_testing\play_with_ai.py --auto --replay-session session_20260515_211742 --replay-stop-before Alice:10
```

`--resume-session` is an alias for `--replay-session`.

Visual replay options:

```powershell
.\play_ai_auto.bat --watch-replay --replay-session session_20260515_211742 --replay-delay 1.5
```

Use `--replay-skip-chat` to hide old table talk, or `--replay-speak` to force
speech during a non-watch replay. In watch replay, `--replay-text-lead 0.25`
controls how long chat is visible before the matching action appears. TTS cache
is per session by default and can be controlled with `AI_TTS_CACHE_ENABLED` and
`AI_TTS_CACHE_DIR` in `.env`.

## Recommended Debug Workflow

1. Run normally until a bug appears.
2. Stop the game.
3. Find the exact `Player:N` response where the bug happened.
4. Fix the code.
5. Run with `--replay-stop-before Player:N`.
6. Watch the new derived session continue from that point.
7. If the action now works, update `docs/AI_RUN_BACKLOG.md`.

For bug validation, prefer `--replay-stop-before`. For skipping already-verified history, use `--replay-through`.
