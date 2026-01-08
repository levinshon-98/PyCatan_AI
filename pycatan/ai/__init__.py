"""
AI Agent Infrastructure for PyCatan

This package contains the infrastructure for building LLM-based AI agents
that can play Settlers of Catan autonomously.

Main Components:
- AIManager: Central coordinator for all AI agents
- AIUser: User interface wrapper for AI agents
- AILogger: Logging and session management
- AgentState: Per-agent state tracking

Supporting Components:
- config: Configuration management for AI agents
- prompt_manager: Prompt construction and game state filtering
- state_filter: Game state filtering and perspective transformation
- prompt_templates: Prompt structure and action templates
- response_parser: LLM response parsing and validation
- llm_client: LLM API abstraction and client
- schemas: JSON schemas for LLM responses

Architecture Overview:
┌─────────────────────────────────────────────────────────────────────┐
│                        AI System Architecture                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   GameManager                          AIManager                     │
│       │                                    │                         │
│       │ get_input()                        │ Creates prompts         │
│       ▼                                    │ Sends to LLM            │
│   ┌─────────┐                              │ Parses responses        │
│   │ AIUser  │◄──────── delegates to ──────►│                         │
│   │(Wrapper)│                              │                         │
│   └─────────┘                              ▼                         │
│                                    ┌─────────────┐                   │
│                                    │  AILogger   │                   │
│                                    │  (Logging)  │                   │
│                                    └─────────────┘                   │
│                                                                      │
│   Components:                                                        │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│   │   Config     │  │    Prompt    │  │   Response   │             │
│   │  Management  │  │   Manager    │  │    Parser    │             │
│   └──────────────┘  └──────────────┘  └──────────────┘             │
│          ✅               ✅                  ✅                     │
│                                                                      │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│   │ Agent State  │  │  LLM Client  │  │   Schemas    │             │
│   │   Tracking   │  │   (Gemini)   │  │   (JSON)     │             │
│   └──────────────┘  └──────────────┘  └──────────────┘             │
│          ✅               ✅                  ✅                     │
└─────────────────────────────────────────────────────────────────────┘

Status: ✅ Complete | 🚧 In Development | ❌ Not Started
"""

__version__ = "2.0.0"

# Main classes
from pycatan.ai.ai_manager import AIManager
from pycatan.ai.ai_user import AIUser
from pycatan.ai.ai_logger import AILogger
from pycatan.ai.agent_state import AgentState, compute_state_hash

# Supporting classes
from pycatan.ai.config import AIConfig
from pycatan.ai.prompt_manager import PromptManager
from pycatan.ai.response_parser import ResponseParser
from pycatan.ai.llm_client import LLMResponse, GeminiClient, create_llm_client
from pycatan.ai.schemas import ResponseType, ACTIVE_TURN_RESPONSE_SCHEMA, OBSERVING_RESPONSE_SCHEMA

__all__ = [
    # Main classes
    "AIManager",
    "AIUser", 
    "AILogger",
    "AgentState",
    "compute_state_hash",
    
    # Configuration
    "AIConfig",
    
    # Prompt handling
    "PromptManager",
    "ResponseParser",
    
    # LLM
    "LLMResponse",
    "GeminiClient",
    "create_llm_client",
    
    # Schemas
    "ResponseType",
    "ACTIVE_TURN_RESPONSE_SCHEMA",
    "OBSERVING_RESPONSE_SCHEMA",
]
