"""
Prompt Management Layer

This module orchestrates the entire prompt processing pipeline:
1. Receives raw game state from GameManager
2. Filters state for specific agent's perspective
3. Builds structured prompt with all context
4. Returns prompt ready for LLM

This is the main interface between the game and the AI agents.

Usage:
    from pycatan.ai.prompt_manager import PromptManager
    
    manager = PromptManager(config)
    prompt = manager.create_prompt(
        player_num=1,
        game_state=raw_state,
        what_happened="Player Red rolled a 6",
        available_actions=actions
    )
"""

from typing import Dict, Any, List, Optional
from pycatan.ai.config import AIConfig
from pycatan.ai.state_filter import StateFilter, PlayerPerspective
from pycatan.ai.prompt_templates import PromptBuilder, ActionTemplates


class PromptManager:
    """
    Main prompt management orchestrator.
    
    Coordinates filtering, template application, and prompt generation
    for AI agents. Ensures each agent gets appropriate context in the
    right format.
    """
    
    def __init__(self, config: Optional[AIConfig] = None):
        """
        Initialize prompt manager.
        
        Args:
            config: AI configuration (uses default if None)
        """
        self.config = config or AIConfig()
        self.prompt_builder = PromptBuilder()
        
        # Cache filters for each player to avoid recreation
        self._filter_cache: Dict[int, StateFilter] = {}
    
    def create_prompt(
        self,
        player_num: int,
        player_name: str,
        player_color: str,
        game_state: Dict[str, Any],
        what_happened: str,
        available_actions: Optional[List[Dict[str, Any]]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        agent_memory: Optional[Dict[str, Any]] = None,
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a complete prompt for an AI agent.
        
        This is the main entry point for prompt creation.
        
        Args:
            player_num: Player number (1-4)
            player_name: Player's name
            player_color: Player's color
            game_state: Raw game state from game engine
            what_happened: Description of what just occurred
            available_actions: Actions agent can take (optional)
            chat_history: Recent chat messages (optional)
            agent_memory: Agent's memory/notes (optional)
            custom_instructions: Custom instructions for this agent
            
        Returns:
            Complete structured prompt ready for LLM
        """
        # Get or create state filter for this player
        state_filter = self._get_filter(player_num, player_name, player_color)
        
        # Filter game state for this agent's perspective
        filtered_state = state_filter.filter_game_state(game_state)
        
        # Build meta data section
        meta_data = {
            "agent_name": player_name,
            "my_color": player_color,
            "role": custom_instructions or self.config.agent.custom_instructions
        }
        
        # Build task context section
        task_context = {
            "what_just_happened": what_happened,
            "instructions": self._get_instructions(available_actions)
        }
        
        # Build social context section
        social_context = None
        if chat_history:
            social_context = {
                "recent_chat": chat_history[-self.config.memory.chat_history_size:]
            }
        
        # Build memory section
        memory = agent_memory if agent_memory else None
        
        # Build constraints section (available actions)
        constraints = None
        if available_actions:
            constraints = {
                "usage_instructions": (
                    "Choose one action type from the list below. "
                    "Populate the 'parameters' field in your response strictly "
                    "according to the 'example_parameters' structure provided."
                ),
                "allowed_actions": available_actions
            }
        
        # Build complete prompt
        prompt = self.prompt_builder.build_prompt(
            meta_data=meta_data,
            task_context=task_context,
            game_state=filtered_state,
            social_context=social_context,
            memory=memory,
            constraints=constraints,
            custom_instructions=custom_instructions
        )
        
        return prompt
    
    def create_action_prompt(
        self,
        player_num: int,
        player_name: str,
        player_color: str,
        game_state: Dict[str, Any],
        action_type: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a prompt for a specific action type.
        
        This is used when GameManager asks "What settlement do you want to build?"
        rather than "What do you want to do?"
        
        Args:
            player_num: Player number
            player_name: Player name
            player_color: Player color
            game_state: Current game state
            action_type: Specific action being requested (e.g., "BUILD_SETTLEMENT")
            context: Additional context about this action
            
        Returns:
            Structured prompt for this specific action
        """
        # Get state filter
        state_filter = self._get_filter(player_num, player_name, player_color)
        filtered_state = state_filter.filter_game_state(game_state)
        
        # Find the specific action template
        all_actions = ActionTemplates.get_all_actions()
        action_template = next(
            (a for a in all_actions if a["type"] == action_type),
            None
        )
        
        # Build task context
        what_happened = context or f"You need to make a decision: {action_type}"
        task_context = {
            "what_just_happened": what_happened,
            "instructions": f"Decide on the best {action_type} action based on the current game state."
        }
        
        # Build meta data
        meta_data = {
            "agent_name": player_name,
            "my_color": player_color,
            "role": self.config.agent.custom_instructions or "You are a Catan player."
        }
        
        # Constraints with just this action
        constraints = None
        if action_template:
            constraints = {
                "usage_instructions": f"Perform the {action_type} action.",
                "allowed_actions": [action_template]
            }
        
        # Build prompt
        return self.prompt_builder.build_prompt(
            meta_data=meta_data,
            task_context=task_context,
            game_state=filtered_state,
            constraints=constraints
        )
    
    def filter_actions_by_resources(
        self,
        actions: List[Dict[str, Any]],
        player_resources: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """
        Filter available actions based on player's resources.
        
        Args:
            actions: List of all possible actions
            player_resources: Player's current resources
            
        Returns:
            Actions the player can actually afford
        """
        return ActionTemplates.filter_by_resources(actions, player_resources)
    
    def get_actions_for_phase(self, phase: str) -> List[Dict[str, Any]]:
        """
        Get available actions for a specific game phase.
        
        Args:
            phase: Game phase name
            
        Returns:
            Actions available in this phase
        """
        return ActionTemplates.get_actions_for_phase(phase)
    
    def _get_filter(
        self, 
        player_num: int, 
        player_name: str, 
        player_color: str
    ) -> StateFilter:
        """
        Get or create state filter for a player.
        
        Uses caching to avoid recreating filters.
        
        Args:
            player_num: Player number
            player_name: Player name
            player_color: Player color
            
        Returns:
            StateFilter for this player
        """
        if player_num not in self._filter_cache:
            perspective = PlayerPerspective(
                player_num=player_num,
                player_name=player_name,
                player_color=player_color
            )
            self._filter_cache[player_num] = StateFilter(perspective)
        
        return self._filter_cache[player_num]
    
    def _get_instructions(self, available_actions: Optional[List[Dict]]) -> str:
        """
        Generate instructions based on available actions.
        
        Args:
            available_actions: Actions available to agent
            
        Returns:
            Instruction text
        """
        base_instructions = (
            "Analyze the game state and select the optimal move from 'allowed_actions'. "
        )
        
        if available_actions:
            num_actions = len(available_actions)
            if num_actions == 1:
                return base_instructions + "Only one action is currently available."
            else:
                return base_instructions + f"You have {num_actions} possible actions to choose from."
        
        return base_instructions + "Consider all strategic implications before deciding."
    
    def clear_cache(self):
        """Clear the filter cache. Useful when starting a new game."""
        self._filter_cache.clear()


# Convenience function
def create_prompt_manager(config: Optional[AIConfig] = None) -> PromptManager:
    """
    Create a prompt manager with optional configuration.
    
    Args:
        config: AI configuration (uses default if None)
        
    Returns:
        Configured PromptManager instance
    """
    return PromptManager(config)
