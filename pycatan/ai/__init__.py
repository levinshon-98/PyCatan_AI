"""
AI Agent Infrastructure for PyCatan

This package contains the infrastructure for building LLM-based AI agents
that can play Settlers of Catan autonomously.

Components:
- config: Configuration management for AI agents
- prompt_manager: Prompt construction and game state filtering
- state_filter: Game state filtering and perspective transformation
- prompt_templates: Prompt structure and action templates
- response_parser: LLM response parsing and validation (TODO)
- memory: Agent memory and learning systems (TODO)
- llm_client: LLM API abstraction and client (TODO)

Architecture Overview:
┌─────────────────────────────────────────────────────────┐
│                      AIAgent                            │
│           (Main AI player implementation)               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Config     │  │    Prompt    │  │   Response   │ │
│  │  Management  │  │   Manager    │  │    Parser    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│         ✅               ✅                  🚧        │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐                   │
│  │    Memory    │  │  LLM Client  │                   │
│  │    System    │  │ (Multi-API)  │                   │
│  └──────────────┘  └──────────────┘                   │
│         🚧               🚧                            │
└─────────────────────────────────────────────────────────┘

Status: ✅ Complete | 🚧 In Development | ❌ Not Started
"""

__version__ = "0.1.0"
__all__ = ["config", "prompt_manager", "state_filter", "prompt_templates"]
