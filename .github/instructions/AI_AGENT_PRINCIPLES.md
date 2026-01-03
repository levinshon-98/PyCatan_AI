# 🎮 AI Agent Design Principles

**Date:** January 3, 2026  
**Status:** 📋 In Planning

## 🎯 Core Philosophy: "Give Tools and Let Go"

The AI agent architecture follows a **tool-based autonomy approach** where we provide the agent with:
- Rich game state context
- Available tools and actions
- Clear constraints and rules
- Memory management capabilities

Then we **let the agent play** - making its own decisions based on the context and available options.

---

## 🏗️ Architecture Principles

### 1️⃣ Event-Driven LLM Invocation

The agent calls the LLM under specific scenarios:
- **Game Events**: Something happened in the game that affects the agent
- **Action Required**: The agent must make a decision (build, trade, play card, etc.)
- **Social Interaction**: Another player sent a message or made an offer
- **Turn Changes**: Beginning or end of turn phases

The agent doesn't continuously "think" - it responds to events and prompts.

### 2️⃣ Self-Managed Memory

The agent maintains its own memory in a simple, accessible format:
- **Short-term memory**: Recent events and observations
- **Strategic notes**: Things to remember for future decisions
- **Social tracking**: Observations about other players' behavior
- **Game insights**: Patterns noticed during play

The memory structure is minimal but effective, allowing the agent to maintain context across turns.

### 3️⃣ Generic and Configurable Design

The agent implementation should be:
- **Modular**: Easy to swap components or strategies
- **Configurable**: Support different play styles and behaviors
- **Extensible**: Simple to add new capabilities or tools
- **Reusable**: Same base agent class for different AI personalities

This allows experimentation with different AI approaches without rewriting core logic.

### 4️⃣ Centralized Configuration

All critical parameters are managed in one place:
- **LLM Configuration**: Model selection, temperature, max tokens
- **API Credentials**: Keys and endpoints for LLM services
- **Agent Parameters**: Personality traits, risk tolerance, strategy preferences
- **Performance Settings**: Timeout limits, retry policies, caching options

This centralization simplifies tuning and experimentation.

---

## 📨 Prompt Processing Pipeline

### Context Filtering and Preparation

Before sending prompts to the agent, game state undergoes processing:

1. **Information Hiding**: Remove data the player shouldn't know
   - Other players' cards and resources (unless revealed)
   - Hidden development cards
   - Future planned moves by other players

2. **Perspective Adaptation**: Present information from agent's viewpoint
   - "You received 1 Wood" instead of "Player Blue received 1 Wood"
   - "Your resources" vs "Player resources"
   - Relative positioning and strategic context

3. **Custom Instructions**: Tailor prompts per agent instance
   - Different personality instructions
   - Unique strategic guidance
   - Role-specific context

4. **Context Enrichment**: Add relevant computed information
   - Tile probabilities (based on dice numbers)
   - Resource scarcity analysis
   - Build opportunity assessment

### Management Layer

A **prompt management layer** sits between GameManager and AI agents to:
- Transform raw game state into agent-specific context
- Filter and format information appropriately
- Handle simultaneous different messages to different agents
- Manage conversation history and memory updates

---

## 📋 Prompt Structure Principles

Based on the format in `promt_format.text`, prompts follow this structure:

### Core Components:

1. **Meta Data**: Agent identity and role
   - Agent name/identifier
   - Player color
   - Personality or role description

2. **Task Context**: Current situation
   - What just happened in the game
   - What action is now required
   - Instructions for decision-making

3. **Game State**: World information from agent perspective
   - Agent's private information (resources, cards, points)
   - Visible board state
   - Other players' public information

4. **Social Context**: Communication and relationships
   - Recent chat messages
   - Trade offers and negotiations
   - Historical summaries of interactions

5. **Memory**: Agent's self-maintained notes
   - Strategic observations
   - Plans and intentions
   - Social dynamics tracking

6. **Constraints**: Available actions and rules
   - List of allowed actions at this moment
   - Parameter structure for each action
   - Usage instructions and examples

### Flexibility Note:
While this structure provides a solid foundation, it should remain **adaptable**. Specific fields and formats may evolve as we test and refine the agent's performance.

---

## 🔄 Structured Response Format

The LLM response is **strictly structured** to enable programmatic processing:

### Response Components:

1. **Reasoning**: Agent's thought process (for debugging/logging)
   - Current situation analysis
   - Strategic considerations
   - Decision rationale

2. **Selected Action**: The chosen action with parameters
   - Action type (BUILD_ROAD, OFFER_TRADE, etc.)
   - Required parameters for that action
   - Validation-ready format

3. **Communication**: Optional message to other players
   - Chat message content
   - Target audience (all or specific player)

4. **Memory Update**: What to remember for next time
   - New notes to add
   - Observations to store
   - Strategy adjustments

### Example Response Structure:
```json
{
  "reasoning": "I have enough resources for a settlement and node 23 gives me access to wheat...",
  "action": {
    "type": "BUILD_SETTLEMENT",
    "parameters": {
      "node_id": 23
    }
  },
  "chat_message": "Building near the wheat fields!",
  "memory_update": {
    "add_note": "Focused on wheat production for development cards"
  }
}
```

This structured format allows the game loop to:
- Parse and validate the agent's decision
- Execute the action through GameManager
- Update agent memory automatically
- Continue the game flow seamlessly

---

## 🔧 Tool Integration

Agents have access to computational tools for enhanced decision-making:

- **Probability Calculator**: Dice roll probabilities for tiles
- **Resource Tracker**: Historical resource generation analysis  
- **Path Finder**: Optimal road placement calculations
- **Trade Evaluator**: Fair trade assessment

**Tool Usage Limits**: To prevent excessive computation, agents are limited in tool calls per decision (e.g., maximum 3 tool executions).

---

## 🎭 Multi-Agent Considerations

When multiple AI agents play simultaneously:
- Each receives their own filtered game state
- Agents can negotiate with each other
- Social dynamics emerge naturally from LLM interactions
- No direct agent-to-agent communication (all goes through game system)

This creates emergent gameplay where AI strategies adapt to each other's behavior.
