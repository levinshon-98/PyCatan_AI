"""
Configuration Management for AI Agents

This module provides centralized configuration management for AI agents,
including LLM settings, API credentials, agent parameters, and performance settings.

Features:
- Load configuration from YAML files
- Environment variable support for sensitive data
- Configuration validation
- Default values with override capability
- Multiple LLM provider support

Usage:
    from pycatan.ai.config import AIConfig
    
    # Load from file
    config = AIConfig.from_file('my_agent_config.yaml')
    
    # Or create with defaults
    config = AIConfig()
    
    # Access settings
    model = config.llm.model_name
    temperature = config.llm.temperature
    api_key = config.get_api_key()
"""

import os
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class LLMConfig:
    """Configuration for LLM provider and model settings."""
    
    # Provider settings
    provider: str = "gemini"  # "gemini", "openai", "anthropic", "azure"
    model_name: str = "gemini-2.0-flash-exp"
    
    # Generation parameters
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.95
    top_k: int = 40
    
    # API settings
    api_key_env_var: str = "GEMINI_API_KEY"  # Environment variable name
    api_base_url: Optional[str] = None  # For custom endpoints
    
    # Performance
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    
    # Cost tracking
    track_usage: bool = True
    log_requests: bool = True


@dataclass
class AgentConfig:
    """Configuration for agent personality and behavior."""
    
    # Agent identity
    personality: str = "balanced"  # "aggressive", "defensive", "balanced", "trading"
    risk_tolerance: float = 0.5  # 0.0 (conservative) to 1.0 (risky)
    
    # Strategic preferences
    focus_on_settlements: float = 0.6  # Relative priority
    focus_on_cities: float = 0.7
    focus_on_roads: float = 0.5
    focus_on_dev_cards: float = 0.6
    
    # Trading behavior
    trade_willingness: float = 0.5  # 0.0 (never trades) to 1.0 (trades often)
    trade_fairness: float = 0.7  # How fair are trade offers
    
    # Social behavior
    chat_frequency: float = 0.3  # How often to send chat messages
    use_emojis: bool = True
    chattiness: str = "medium"  # "quiet", "medium", "chatty"
    
    # Custom instructions
    custom_instructions: Optional[str] = None  # Additional instructions for this agent


@dataclass
class MemoryConfig:
    """Configuration for agent memory system."""
    
    # Short-term memory
    short_term_turns: int = 5  # Remember last N turns
    
    # Chat history
    chat_history_size: int = 10  # Keep last N messages
    enable_chat_summarization: bool = True
    chat_summary_threshold: int = 10  # Summarize when reaching N messages
    
    # Summarization settings
    summarization_provider: str = "gemini"
    summarization_model: str = "gemini-2.0-flash-exp"
    summarization_max_tokens: int = 500
    
    # Memory persistence
    save_memory_to_file: bool = True
    memory_file_path: str = "agent_memory.json"
    
    # Memory limits
    max_strategic_notes: int = 20
    max_observations: int = 50


@dataclass
class DebugConfig:
    """Configuration for debugging and logging."""
    
    # Logging levels
    debug_mode: bool = False
    log_prompts: bool = True
    log_responses: bool = True
    log_decisions: bool = True
    
    # Log file settings
    log_to_file: bool = True
    log_directory: str = "logs/ai_agents"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Performance monitoring
    track_decision_time: bool = True
    track_token_usage: bool = True
    
    # Development helpers
    save_game_states: bool = False  # Save game states for analysis
    game_states_directory: str = "logs/game_states"


@dataclass
class AIConfig:
    """
    Main configuration class for AI agents.
    
    This class aggregates all configuration sections and provides
    methods for loading, saving, and accessing configuration values.
    """
    
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    
    # Metadata
    config_version: str = "1.0"
    agent_name: str = "AI Agent"
    
    @classmethod
    def from_file(cls, file_path: str) -> "AIConfig":
        """
        Load configuration from a YAML file.
        
        Args:
            file_path: Path to the YAML configuration file
            
        Returns:
            AIConfig instance with loaded settings
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid
        """
        config_path = Path(file_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIConfig":
        """
        Create configuration from a dictionary.
        
        Args:
            data: Dictionary with configuration values
            
        Returns:
            AIConfig instance
        """
        # Extract nested configs
        llm_data = data.get('llm', {})
        agent_data = data.get('agent', {})
        memory_data = data.get('memory', {})
        debug_data = data.get('debug', {})
        
        return cls(
            llm=LLMConfig(**llm_data),
            agent=AgentConfig(**agent_data),
            memory=MemoryConfig(**memory_data),
            debug=DebugConfig(**debug_data),
            config_version=data.get('config_version', '1.0'),
            agent_name=data.get('agent_name', 'AI Agent')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            'config_version': self.config_version,
            'agent_name': self.agent_name,
            'llm': asdict(self.llm),
            'agent': asdict(self.agent),
            'memory': asdict(self.memory),
            'debug': asdict(self.debug)
        }
    
    def to_file(self, file_path: str):
        """
        Save configuration to a YAML file.
        
        Args:
            file_path: Path where to save the configuration
        """
        config_path = Path(file_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
    
    def get_api_key(self, provider: Optional[str] = None) -> str:
        """
        Get API key from environment variable.
        
        Args:
            provider: Provider name (uses llm.provider if None)
            
        Returns:
            API key string
            
        Raises:
            ValueError: If API key environment variable is not set
        """
        if provider is None:
            provider = self.llm.provider
        
        # Determine environment variable name
        if provider == "gemini":
            env_var = self.llm.api_key_env_var or "GEMINI_API_KEY"
        elif provider == "openai":
            env_var = "OPENAI_API_KEY"
        elif provider == "anthropic":
            env_var = "ANTHROPIC_API_KEY"
        elif provider == "azure":
            env_var = "AZURE_OPENAI_KEY"
        else:
            env_var = self.llm.api_key_env_var or f"{provider.upper()}_API_KEY"
        
        api_key = os.getenv(env_var)
        
        if not api_key:
            raise ValueError(
                f"API key not found. Please set the {env_var} environment variable."
            )
        
        return api_key
    
    def validate(self) -> bool:
        """
        Validate configuration values.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration contains invalid values
        """
        # Validate temperature
        if not 0.0 <= self.llm.temperature <= 2.0:
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {self.llm.temperature}")
        
        # Validate token limits
        if self.llm.max_tokens < 100:
            raise ValueError(f"max_tokens must be at least 100, got {self.llm.max_tokens}")
        
        # Validate risk tolerance
        if not 0.0 <= self.agent.risk_tolerance <= 1.0:
            raise ValueError(f"risk_tolerance must be between 0.0 and 1.0, got {self.agent.risk_tolerance}")
        
        # Validate timeouts
        if self.llm.timeout_seconds < 1:
            raise ValueError(f"timeout_seconds must be at least 1, got {self.llm.timeout_seconds}")
        
        # Validate memory settings
        if self.memory.short_term_turns < 1:
            raise ValueError(f"short_term_turns must be at least 1, got {self.memory.short_term_turns}")
        
        # Check API key is available (warning, not error)
        try:
            self.get_api_key()
        except ValueError as e:
            print(f"Warning: {e}")
        
        return True
    
    def __repr__(self) -> str:
        """String representation of configuration."""
        return (
            f"AIConfig(\n"
            f"  agent_name='{self.agent_name}',\n"
            f"  provider='{self.llm.provider}',\n"
            f"  model='{self.llm.model_name}',\n"
            f"  personality='{self.agent.personality}',\n"
            f"  debug={self.debug.debug_mode}\n"
            f")"
        )


# Convenience function for quick config loading
def load_config(file_path: Optional[str] = None) -> AIConfig:
    """
    Load AI configuration from file or create default.
    
    Args:
        file_path: Path to config file (optional)
        
    Returns:
        AIConfig instance
    """
    if file_path and Path(file_path).exists():
        return AIConfig.from_file(file_path)
    else:
        return AIConfig()
