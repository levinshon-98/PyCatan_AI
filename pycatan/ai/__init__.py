"""
AI Agent Infrastructure for PyCatan

This package contains the infrastructure for building LLM-based AI agents
that can play Settlers of Catan autonomously.

Components:
- config: Configuration management for AI agents
- prompt_manager: Prompt construction and game state filtering
- response_parser: LLM response parsing and validation
- memory: Agent memory and learning systems
- llm_client: LLM API abstraction and client

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
│                                                         │
│  ┌──────────────┐  ┌──────────────┐                   │
│  │    Memory    │  │  LLM Client  │                   │
│  │    System    │  │ (Multi-API)  │                   │
│  └──────────────┘  └──────────────┘                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
"""

__version__ = "0.1.0"
__all__ = ["config"]
