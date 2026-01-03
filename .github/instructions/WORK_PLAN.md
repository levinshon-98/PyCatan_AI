# 🗺️ AI Agent Development Work Plan

**Date:** January 3, 2026  
**Status:** ✅ Phase 1 - Foundation & Infrastructure (100% Complete)
**Current Task:** Phase 3 - Core AI Agent (3.1) - **NEXT**

## 🎯 Project Goal

Build a fully functional LLM-based AI agent that can play Settlers of Catan autonomously, making intelligent strategic decisions and interacting naturally with other players.

---

## 📊 Development Phases

> **Note:** Phase 4 (Monitoring & Debugging) should be developed **early and in parallel** with Phase 3.  
> The web dashboard and logging are **critical** for observing agent behavior during development!

### Phase 1: Foundation & Infrastructure 🏗️
**Goal:** Build the core infrastructure needed to support AI agents

#### 1.1 Configuration Management ✅ **COMPLETED**
- [x] Create centralized configuration system
  - [x] LLM settings (model, temperature, max_tokens, etc.)
  - [x] API credentials management
  - [x] Agent parameters (custom instructions only)
  - [x] Performance settings (timeouts, retries, caching)
- [x] Create config file format (YAML)
- [x] Build configuration loader and validator
- [x] Add environment variable support for sensitive data

**Files created:**
- ✅ `pycatan/ai/config.py` - Configuration management
- ✅ `pycatan/ai/config_example.yaml` - Example configuration file
- ✅ `pycatan/ai/config_dev.yaml` - Default dev configuration
- ✅ `.env.example` - Environment variables template

---

#### 1.2 Prompt Management Layer ✅ **COMPLETED**
- [x] Design prompt processing pipeline
- [x] Implement game state filtering
  - [x] Hide opponent's private information
  - [x] Filter development cards
  - [x] Remove non-visible game elements
- [x] Build perspective transformation
  - [x] Convert game state to agent's viewpoint
  - [x] Format resources and points
  - [x] Present relative positioning
- [x] Create prompt template system
  - [x] Meta data section
  - [x] Task context section
  - [x] Game state section
  - [x] Social context section
  - [x] Memory section
  - [x] Constraints section
- [x] Build custom instruction injection per agent

**Files created:**
- ✅ `pycatan/ai/prompt_manager.py` - Main prompt processing
- ✅ `pycatan/ai/state_filter.py` - Game state filtering logic
- ✅ `pycatan/ai/prompt_templates.py` - Template definitions

---

#### 1.2.5 Game State Optimization ✅ **COMPLETED**
**Goal:** Optimize the game state capture and representation for better LLM consumption

- [x] Review current game state structure from `play_and_capture.py`
- [x] Design improved game state format
  - [x] Compress player information structure
  - [x] Improve board representation (lookup tables H & N)
  - [x] Add resource/harbor code mappings
  - [x] Reduce redundancy and token usage (removed pixel_coords, board_graph)
  - [x] Add status flags (Longest Road, Largest Army)
- [x] Create optimized state format with legend
- [x] Update game state capture to save both formats (.json + .txt)
- [x] Fix timing: capture state at turn START (not just after actions)
- [x] Test with real game scenarios

**Files modified:**
- ✅ `examples/ai_testing/play_and_capture.py` - Optimized state capture
- ✅ `pycatan/management/game_manager.py` - Added state capture at turn start

**Key achievements:**
- 🎯 State representation optimized by ~60% (removed redundant fields)
- 📊 Compressed format with lookup tables (H=hexes, N=nodes)
- 🔄 Real-time state updates at `current_state_optimized.txt`
- 📝 Clear legend/documentation included in output
- ✅ Captures state at decision point (turn start)

---

#### 1.3 Response Parser ✅ **COMPLETED**
- [x] Define structured response format (JSON schema)
- [x] Build response parser and validator
- [x] Implement error handling for malformed responses
- [x] Create fallback mechanisms for parsing failures
- [x] Add response logging for debugging

**Files created:**
- ✅ `pycatan/ai/response_parser.py` - Parse and validate LLM responses
- ✅ `pycatan/ai/schemas.py` - JSON schemas for requests/responses

**Key features:**
- 🎯 Dual schema support: Active turn (with action) & Observing (no action)
- 🛡️ Error handling: Invalid JSON, missing fields, type validation
- 🔧 Fallback mechanisms: JSON repair, structure repair, default values
- 📊 Parse statistics tracking
- 🔍 Flexible parsing: Handles markdown code blocks, extra text
- ✅ Action parameter validation against expected schemas

---

### Phase 2: Memory System 🧠
**Goal:** Enable agents to maintain context and learning across turns

#### 2.1 Memory Structure
- [ ] Design memory data model
  - [ ] Short-term observations (last N turns)
  - [ ] Strategic notes (persistent)
  - [ ] Social tracking (player relationships)
  - [ ] Game insights (patterns observed)
- [ ] Implement memory storage (in-memory for now)
- [ ] Build memory retrieval and formatting

**Files to create:**
- `pycatan/ai/memory.py` - Memory management system

---

#### 2.2 Memory Operations
- [ ] Add note creation and updates
- [ ] Implement memory pruning (keep relevant, remove old)
- [ ] Build memory summarization for context limits
- [ ] Create memory persistence (save/load between games)

---

#### 2.3 Chat History Summarization ⚡
- [ ] Implement automatic chat summarization
  - [ ] Configure separate smaller LLM for summarization (cost-effective)
  - [ ] Monitor chat history length (e.g., last 10 messages)
  - [ ] Trigger summarization when threshold reached
  - [ ] Create summarization prompt template
- [ ] Build chat memory management
  - [ ] Keep only most recent message after summarization
  - [ ] Store summary in agent's memory
  - [ ] Maintain summary history for context
- [ ] Add configuration for summarization settings
  - [ ] Summarization model selection
  - [ ] Message threshold for triggering
  - [ ] Summary format and length

**Files to update:**
- `pycatan/ai/memory.py` - Add chat summarization logic
- `pycatan/ai/config.py` - Add summarization configuration
- `pycatan/ai/llm_client.py` - Support multiple models (main + summarization)

---

### Phase 3: Core AI Agent 🤖
**Goal:** Implement the main AI agent class

#### 3.1 Base Agent Implementation
- [ ] Create `AIAgent` class inheriting from `User`
- [ ] Implement required User interface methods
  - [ ] `get_choice()` for decision-making
  - [ ] Other interaction methods as needed
- [ ] Integrate with prompt manager
- [ ] Integrate with memory system
- [ ] Add agent state management

**Files to create:**
- `pycatan/players/ai_agent.py` - Main AI agent implementation (update existing stub)

---

#### 3.2 LLM Integration
- [ ] Create LLM client abstraction
  - [ ] Support for OpenAI API
  - [ ] Support for Anthropic Claude
  - [ ] Support for other providers (Azure, etc.)
- [ ] Implement API call handling
  - [ ] Request formatting
  - [ ] Response parsing
  - [ ] Error handling and retries
  - [ ] Rate limiting
- [ ] Add logging for all LLM interactions
- [ ] Implement cost tracking

**Files to create:**
- `pycatan/ai/llm_client.py` - LLM API abstraction
- `pycatan/ai/providers/` - Provider-specific implementations
  - `openai_provider.py`
  - `anthropic_provider.py`

---

#### 3.3 Decision Pipeline
- [ ] Build event-to-prompt conversion
- [ ] Implement action extraction from responses
- [ ] Create action validation before execution
- [ ] Add decision logging and debugging
- [ ] Implement decision timeout handling

---

### Phase 4: Monitoring & Debugging Infrastructure 🔍
**Goal:** Build essential tools for observing and debugging agent behavior

**⚠️ CRITICAL: These tools are essential for development and must be built early!**

---

#### 4.1 Web Dashboard for Real-Time Monitoring 🌐
**Priority: HIGH - Required before agent testing**

- [ ] Design web dashboard UI
  - [ ] Multi-agent view (tabs or split screen per agent)
  - [ ] Live prompt display with syntax highlighting
  - [ ] Agent reasoning/thinking display
  - [ ] Action selection visualization
  - [ ] Chat window with all messages
  - [ ] Game state summary panel
- [ ] Build backend API for dashboard
  - [ ] WebSocket connection for live updates
  - [ ] Endpoints for prompt/response history
  - [ ] Agent state endpoints
  - [ ] Chat history endpoint
- [ ] Implement prompt logging and streaming
  - [ ] Capture all prompts sent to LLM
  - [ ] Capture all responses from LLM
  - [ ] Stream to dashboard in real-time
  - [ ] Format for readability
- [ ] Build agent reasoning viewer
  - [ ] Display internal_thinking/reasoning
  - [ ] Show action selection process
  - [ ] Highlight tool usage
  - [ ] Show memory updates

**Files to create:**
- `pycatan/monitoring/` - NEW monitoring package
  - `dashboard_server.py` - Flask/FastAPI server for dashboard
  - `event_logger.py` - Captures and broadcasts events
  - `prompt_tracker.py` - Tracks all LLM interactions
- `pycatan/monitoring/web/` - Dashboard frontend
  - `index.html` - Main dashboard page
  - `dashboard.js` - Dashboard functionality
  - `dashboard.css` - Dashboard styling

---

#### 4.2 Local Documentation & Logging 📁
**Priority: HIGH - Required for debugging**

- [ ] Design local documentation structure
  - [ ] One folder per game session
  - [ ] One file per agent with structured log
  - [ ] Timestamp-based organization
- [ ] Implement per-agent documentation
  - [ ] Agent configuration snapshot
  - [ ] All prompts sent (formatted)
  - [ ] All responses received (formatted)
  - [ ] Decision timeline with reasoning
  - [ ] Memory state snapshots
  - [ ] Tool usage log
  - [ ] Errors and warnings
- [ ] Build structured logging format
  - [ ] JSON-based for easy parsing
  - [ ] Markdown reports for human reading
  - [ ] Searchable and filterable
- [ ] Add game session documentation
  - [ ] Game state at each turn
  - [ ] All chat messages with timestamps
  - [ ] Final game results and statistics

**Files to create:**
- `pycatan/monitoring/local_logger.py` - Local file logging
- `pycatan/monitoring/session_recorder.py` - Game session recording
- `pycatan/monitoring/report_generator.py` - Generate readable reports

**Output structure:**
```
logs/
└── game_sessions/
    └── 2026-01-03_15-30-45/
        ├── game_summary.json
        ├── chat_log.txt
        ├── agent_blue/
        │   ├── config.json
        │   ├── prompts.log
        │   ├── decisions.log
        │   └── memory_snapshots.json
        ├── agent_red/
        │   └── ...
        └── agent_white/
            └── ...
```

---

#### 4.3 Chat Management System 💬
**Priority: HIGH - Core game feature**

- [ ] Design chat system architecture
  - [ ] Centralized chat manager
  - [ ] Message routing between players
  - [ ] Chat history per game
  - [ ] Public vs private messages
- [ ] Implement chat manager component
  - [ ] Message queue/buffer
  - [ ] Broadcast to all players
  - [ ] Direct messages between players
  - [ ] Integration with GameManager
- [ ] Build chat observation interface
  - [ ] Real-time chat display in web dashboard
  - [ ] Chat log export
  - [ ] Filter by sender/time
- [ ] Define chat protocol
  - [ ] Message format (sender, content, timestamp, type)
  - [ ] Chat commands (if any)
  - [ ] Trade negotiation messages

**Files to create:**
- `pycatan/management/chat_manager.py` - Central chat management
- `pycatan/management/message.py` - Message data structure

**Integration points:**
- GameManager receives messages from players
- ChatManager distributes to other players and dashboard
- AI agents see messages in their prompt context
- Web dashboard shows live chat
- Local logs record all messages

---

### Phase 5: Tool System 🔧
**Goal:** Provide computational tools for agent decision-making

#### 5.1 Core Tools
- [ ] **Probability Calculator**
  - [ ] Dice roll probabilities for tiles
  - [ ] Expected resource generation rates
  - [ ] Statistical analysis helpers
- [ ] **Resource Tracker**
  - [ ] Historical resource generation
  - [ ] Resource scarcity analysis
  - [ ] Production trend analysis
- [ ] **Path Finder**
  - [ ] Optimal road placement
  - [ ] Longest road calculation
  - [ ] Connectivity analysis
- [ ] **Trade Evaluator**
  - [ ] Fair trade assessment
  - [ ] Trade benefit calculation
  - [ ] Market value estimation

**Files to create:**
- `pycatan/ai/tools/` - Tool implementations
  - `probability_tool.py`
  - `resource_tool.py`
  - `pathfinding_tool.py`
  - `trade_tool.py`
  - `tool_manager.py` - Tool orchestration

---

#### 5.2 Tool Integration
- [ ] Define tool interface/protocol
- [ ] Implement tool calling from prompts
- [ ] Add tool usage limits per decision
- [ ] Create tool result formatting
- [ ] Build tool usage logging

---

### Phase 6: Testing & Validation ✅
**Goal:** Ensure agent works correctly and plays reasonably

#### 6.1 Unit Tests
- [ ] Test prompt manager filtering
- [ ] Test response parser with various inputs
- [ ] Test memory operations
- [ ] Test each tool independently
- [ ] Test configuration loading

**Files to create:**
- `tests/unit/test_ai_agent.py`
- `tests/unit/test_prompt_manager.py`
- `tests/unit/test_memory.py`
- `tests/unit/test_tools.py`

---

#### 6.2 Integration Tests
- [ ] Test agent in complete game loop
- [ ] Test agent vs human player
- [ ] Test multiple AI agents playing together
- [ ] Test edge cases and error scenarios
- [ ] Test long-running games (memory management)

**Files to create:**
- `tests/integration/test_ai_gameplay.py`
- `tests/integration/test_multi_agent.py`

---

#### 6.3 Gameplay Validation
- [ ] Verify legal moves only
- [ ] Check strategic decision quality
- [ ] Evaluate social interaction naturalness
- [ ] Monitor LLM costs and performance
- [ ] Collect agent behavior metrics

---

### Phase 7: Optimization & Enhancement 🚀
**Goal:** Improve agent performance and capabilities

#### 7.1 Performance Optimization
- [ ] Reduce prompt token usage
- [ ] Implement response caching for similar situations
- [ ] Optimize tool execution
- [ ] Improve decision speed

---

#### 7.2 Strategy Enhancement
- [ ] Tune agent personalities
- [ ] Improve opening game strategy
- [ ] Enhance mid-game adaptation
- [ ] Refine end-game tactics
- [ ] Better negotiation and trading

---

#### 7.3 Advanced Features
- [ ] Multi-turn planning capability
- [ ] Opponent modeling
- [ ] Meta-strategy learning
- [ ] Tournament play support
- [ ] Statistical performance tracking

---

## 📁 Project Structure (Proposed)

```
pycatan/
├── ai/                          # NEW: AI agent infrastructure
│   ├── __init__.py
│   ├── config.py                # Configuration management
│   ├── prompt_manager.py        # Prompt processing pipeline
│   ├── state_filter.py          # Game state filtering
│   ├── prompt_templates.py      # Prompt templates
│   ├── response_parser.py       # Response parsing
│   ├── schemas.py               # JSON schemas
│   ├── memory.py                # Memory system + chat summarization
│   ├── llm_client.py            # LLM abstraction (multi-model)
│   ├── providers/               # LLM provider implementations
│   │   ├── __init__.py
│   │   ├── openai_provider.py
│   │   └── anthropic_provider.py
│   └── tools/                   # Agent tools
│       ├── __init__.py
│       ├── tool_manager.py
│       ├── probability_tool.py
│       ├── resource_tool.py
│       ├── pathfinding_tool.py
│       └── trade_tool.py
├── monitoring/                  # NEW: Monitoring & debugging
│   ├── __init__.py
│   ├── dashboard_server.py      # Web dashboard backend
│   ├── event_logger.py          # Event capture and broadcast
│   ├── prompt_tracker.py        # LLM interaction tracking
│   ├── local_logger.py          # Local file logging
│   ├── session_recorder.py      # Game session recording
│   ├── report_generator.py      # Report generation
│   └── web/                     # Dashboard frontend
│       ├── index.html
│       ├── dashboard.js
│       └── dashboard.css
├── management/
│   ├── actions.py               # Existing
│   ├── game_manager.py          # Existing
│   ├── log_events.py            # Existing
│   ├── chat_manager.py          # NEW: Chat management
│   └── message.py               # NEW: Message data structure
├── players/
│   ├── ai_agent.py              # UPDATE: Full AI agent implementation
│   ├── human_user.py            # Existing
│   └── user.py                  # Existing
└── ...                          # Existing structure

logs/                            # NEW: Local documentation
└── game_sessions/
    └── YYYY-MM-DD_HH-MM-SS/
        ├── game_summary.json
        ├── chat_log.txt
        └── agent_<color>/
            ├── config.json
            ├── prompts.log
            ├── decisions.log
            └── memory_snapshots.json

examples/
├── ai_testing/
│   ├── config_example.yaml      # NEW: Example configuration
│   ├── test_single_agent.py     # NEW: Test script
│   └── test_multi_agent.py      # NEW: Multi-agent test
└── ...

tests/
├── unit/
│   ├── test_ai_agent.py         # NEW
│   ├── test_prompt_manager.py   # NEW
│   ├── test_memory.py           # NEW
│   └── test_tools.py            # NEW
├── integration/
│   ├── test_ai_gameplay.py      # NEW
│   └── test_multi_agent.py      # NEW
└── ...
```
