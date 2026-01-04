"""
Prompt Templates for AI Agents

This module defines the structure and templates for prompts sent to LLM agents.
Based on the format defined in promt_format.text, prompts consist of:

1. Meta Data - Agent identity and role
2. Task Context - Current situation and instructions
3. Game State - World information from agent's perspective
4. Social Context - Chat messages and relationships
5. Memory - Agent's notes and observations
6. Constraints - Available actions and usage rules

The templates are flexible and can be customized per agent.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    """
    Base template structure for agent prompts.
    
    Each section can be customized and sections can be optionally included.
    """
    
    # Section templates
    meta_data_template: str = ""
    task_context_template: str = ""
    game_state_template: str = ""
    social_context_template: str = ""
    memory_template: str = ""
    constraints_template: str = ""
    
    # Which sections to include
    include_meta_data: bool = True
    include_task_context: bool = True
    include_game_state: bool = True
    include_social_context: bool = True
    include_memory: bool = True
    include_constraints: bool = True


class PromptBuilder:
    """
    Builds structured prompts for AI agents.
    
    Takes filtered game state and context, applies templates,
    and produces a complete prompt ready for LLM.
    """
    
    def __init__(self, template: Optional[PromptTemplate] = None):
        """
        Initialize prompt builder with a template.
        
        Args:
            template: Custom template (uses default if None)
        """
        self.template = template or self._create_default_template()
    
    def _create_default_template(self) -> PromptTemplate:
        """Create the default prompt template."""
        return PromptTemplate()
    
    def build_prompt(
        self,
        meta_data: Dict[str, Any],
        task_context: Dict[str, Any],
        game_state: Dict[str, Any],
        social_context: Optional[Dict[str, Any]] = None,
        memory: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a complete structured prompt with optimized game state.
        
        Args:
            meta_data: Agent identity and role
            task_context: What just happened and what to do
            game_state: Filtered game state (optimized format)
            social_context: Chat and relationships (optional)
            memory: Agent's notes (optional)
            constraints: Available actions (optional)
            custom_instructions: Additional instructions for this agent
            
        Returns:
            Complete structured prompt as dictionary
        """
        prompt = {}
        
        # Build each section in the correct order:
        # 1. meta_data (who am I?)
        # 2. game_state (current board state)
        # 3. memory (what did I remember?)
        # 4. task_context (what just happened and what to do?)
        # 5. social_context (chat/trades)
        # 6. constraints (allowed actions)
        
        if self.template.include_meta_data:
            prompt["meta_data"] = self._build_meta_data(meta_data, custom_instructions)
        
        if self.template.include_game_state:
            # Include optimized game state with legend embedded
            prompt["game_state"] = self._build_game_state_section(game_state)
        
        if self.template.include_memory and memory:
            prompt["memory"] = self._build_memory(memory)
        
        if self.template.include_task_context:
            prompt["task_context"] = self._build_task_context(task_context)
        
        if self.template.include_social_context and social_context:
            prompt["social_context"] = self._build_social_context(social_context)
        
        if self.template.include_constraints and constraints:
            prompt["constraints"] = self._build_constraints(constraints)
        
        return prompt
    
    def _build_game_state_section(self, game_state: Dict[str, Any]) -> str:
        """
        Build game state section with compact legend and single-line JSON.
        
        Args:
            game_state: Optimized game state
            
        Returns:
            Complete game state as formatted string with legend
        """
        legend = """
  1. LOOKUP TABLES:
   • "H" (Hexes): Array where Index = HexID. Value = Resource+Num.
     Example: H[1]="W12" -> Hex 1 is Wood 12.
   • "N" (Nodes): Array where Index = NodeID.
     Format: [ [Neighbors], [HexIDs], Port? ]
     Logic: To find yield of Node 10, check N[10]. Get HexIDs (e.g. [1,5]). Look up H[1] and H[5].

2. CODES: W=Wood, B=Brick, S=Sheep, Wh=Wheat, O=Ore, D=Desert.
          ?3=Any 3:1 port, X2=Specific Resource 2:1 port.

3. STATE: "bld"=[NodeID, Owner, Type], "rds"=[[From,To], Owner].

4. PLAYERS: "res"={Resource:Count}, "dev"={"h":[Hidden Cards], "r":[Revealed] (K=Knight)}, 
            "stat"=["LR" (Longest Road), "LA" (Largest Army)].

5. ROBBER: Located at HexID specified in "meta.robber". H[id] is blocked.

JSON:
"""
        # Convert game state to compact single-line JSON
        import json
        compact_json = json.dumps(game_state, ensure_ascii=False, separators=(',', ':'))
        return legend + compact_json
    
    def _build_meta_data(
        self, 
        meta_data: Dict[str, Any],
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build meta data section.
        
        Args:
            meta_data: Basic agent info
            custom_instructions: Custom role/instructions
            
        Returns:
            Formatted meta data
        """
        result = {
            "agent_name": meta_data.get("agent_name", "AI Agent"),
        }
        
        # Add role/instructions
        if custom_instructions:
            result["role"] = custom_instructions
        else:
            result["role"] = meta_data.get("role", "You are a Catan player.")
        
        return result
    
    def _build_task_context(self, task_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build task context section.
        
        Args:
            task_context: What happened and what to do
            
        Returns:
            Formatted task context
        """
        return {
            "what_just_happened": task_context.get("what_just_happened", ""),
            "instructions": task_context.get(
                "instructions",
                "Analyze the game state and select the optimal move from 'allowed_actions'."
            )
        }
    
    def _build_social_context(self, social_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build social context section with chat history.
        
        Args:
            social_context: Chat messages and summaries
            
        Returns:
            Formatted social context
        """
        result = {}
        
        # Recent chat messages
        if "recent_chat" in social_context:
            result["recent_chat"] = social_context["recent_chat"]
        
        # Chat summaries (if using summarization)
        if "last_summaries" in social_context:
            result["last_summaries"] = social_context["last_summaries"]
        
        # Trade offers/negotiations
        if "pending_trades" in social_context:
            result["pending_trades"] = social_context["pending_trades"]
        
        return result
    
    def _build_memory(self, memory: Any) -> Dict[str, Any]:
        """
        Build memory section with agent's notes.
        
        Args:
            memory: Agent's observations and plans (can be string, list or dict)
            
        Returns:
            Formatted memory
        """
        # Support string format (direct note_to_self from previous response)
        if isinstance(memory, str):
            return {
                "previous_note_to_self": memory
            }
        # Support dict format
        elif isinstance(memory, dict):
            return memory
        # Support list format
        elif isinstance(memory, list):
            return {
                "notes_for_myself": memory
            }
        else:
            return {}
    
    def _build_constraints(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build constraints section with available actions.
        # Support both dict format and list format
        if isinstance(memory, dict):
            notes = memory.get("notes", [])
        elif isinstance(memory, list):
            notes = memory
        else:
            notes = []
            
        return {
            "notes_for_myself": notes
        Returns:
            Formatted constraints
        """
        return {
            "usage_instructions": constraints.get(
                "usage_instructions",
                "Choose one action type from the list below. "
                "Populate the 'parameters' field according to the example structure."
            ),
            "allowed_actions": constraints.get("allowed_actions", [])
        }


class ActionTemplates:
    """
    Templates for different game actions.
    
    Provides structured definitions of all possible actions
    an agent can take, with examples and parameter structures.
    """
    
    @staticmethod
    def get_all_actions() -> List[Dict[str, Any]]:
        """
        Get all possible action templates.
        
        Returns:
            List of action definitions with examples
        """
        return [
            {
                "type": "BUILD_ROAD",
                "description": "Build a road on a specific edge ID.",
                "example_parameters": {"edge_id": 12}
            },
            {
                "type": "BUILD_SETTLEMENT",
                "description": "Build a settlement on a specific node ID.",
                "example_parameters": {"node_id": 45}
            },
            {
                "type": "BUILD_CITY",
                "description": "Upgrade an existing settlement to a city.",
                "example_parameters": {"node_id": 45}
            },
            {
                "type": "BUY_DEV_CARD",
                "description": "Purchase a development card.",
                "example_parameters": {}
            },
            {
                "type": "OFFER_TRADE",
                "description": "Propose a trade to all players or a specific one.",
                "example_parameters": {
                    "give": {"wood": 1, "sheep": 1},
                    "receive": {"ore": 1},
                    "target_player_color": "Red"  # Optional
                }
            },
            {
                "type": "ACCEPT_TRADE",
                "description": "Accept a trade offer from another player.",
                "example_parameters": {"trade_id": "trade_123"}
            },
            {
                "type": "DECLINE_TRADE",
                "description": "Decline a trade offer.",
                "example_parameters": {"trade_id": "trade_123"}
            },
            {
                "type": "PLAY_DEV_CARD",
                "description": "Play a development card. Specific params depend on the card.",
                "example_parameters": [
                    {"card": "KNIGHT", "robber_hex": 7, "target_victim": "Red"},
                    {"card": "MONOPOLY", "resource": "sheep"},
                    {"card": "YEAR_OF_PLENTY", "resources": ["wood", "brick"]},
                    {"card": "ROAD_BUILDING", "edges": [12, 13]}
                ]
            },
            {
                "type": "SEND_CHAT",
                "description": "Send a message to all players.",
                "example_parameters": {"message": "Anyone want to trade sheep for wheat?"}
            },
            {
                "type": "WAIT_FOR_RESPONSE",
                "description": "Do nothing on the board, just wait or chat.",
                "example_parameters": {}
            },
            {
                "type": "END_TURN",
                "description": "Pass the dice to the next player.",
                "example_parameters": {}
            }
        ]
    
    @staticmethod
    def get_actions_for_phase(phase: str) -> List[Dict[str, Any]]:
        """
        Get actions available in a specific game phase.
        
        Args:
            phase: Game phase (e.g., "setup", "main_turn", "robber")
            
        Returns:
            List of actions available in this phase
        """
        all_actions = ActionTemplates.get_all_actions()
        
        if phase == "setup":
            # During setup, only build settlements and roads
            return [a for a in all_actions if a["type"] in ["BUILD_SETTLEMENT", "BUILD_ROAD"]]
        
        elif phase == "robber":
            # When 7 is rolled and robber must be moved
            return [a for a in all_actions if a["type"] == "PLAY_DEV_CARD"]
        
        elif phase == "main_turn":
            # Normal turn - all actions except setup-specific
            return all_actions
        
        else:
            return all_actions
    
    @staticmethod
    def filter_by_resources(
        actions: List[Dict[str, Any]], 
        available_resources: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """
        Filter actions based on available resources.
        
        Args:
            actions: List of possible actions
            available_resources: Agent's current resources
            
        Returns:
            Actions the agent can afford
        """
        # Resource costs
        costs = {
            "BUILD_ROAD": {"wood": 1, "brick": 1},
            "BUILD_SETTLEMENT": {"wood": 1, "brick": 1, "sheep": 1, "wheat": 1},
            "BUILD_CITY": {"wheat": 2, "ore": 3},
            "BUY_DEV_CARD": {"sheep": 1, "wheat": 1, "ore": 1}
        }
        
        affordable = []
        for action in actions:
            action_type = action["type"]
            
            # Actions that don't require resources
            if action_type not in costs:
                affordable.append(action)
                continue
            
            # Check if agent can afford this action
            required = costs[action_type]
            can_afford = all(
                available_resources.get(resource, 0) >= amount
                for resource, amount in required.items()
            )
            
            if can_afford:
                affordable.append(action)
        
        return affordable


def get_response_schema() -> Dict[str, Any]:
    """
    Get the expected response schema for LLM output.
    Based on example_answer.md structure.
    OpenAPI-compliant (no 'examples' inside properties).
    
    Returns:
        JSON schema defining expected response format
    """
    return {
        "type": "object",
        "required": ["internal_thinking", "action"],
        "properties": {
            "internal_thinking": {
                "type": "string",
                "description": "Private strategy. What's your plan and why?",
                "minLength": 50
            },
            "note_to_self": {
                "type": "string",
                "description": "Important facts for when it's your turn. Use only if essential for clarity or direct user query. Omit otherwise.",
                "maxLength": 100
            },
            "say_outloud": {
                "type": "string",
                "description": "A short message to other players (max 100 chars). Use for negotiation, threats, or table talk. Keep in mind you pay for speak outload.",
                "maxLength": 100
            },
            "action": {
                "type": "object",
                "required": ["type", "parameters"],
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "The action type (must match one from allowed_actions in constraints)"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Action-specific parameters. If no parameters are needed, provide an empty object.",
                        "properties": {
                            "target": {"type": "string", "description": "The target of the action (if applicable)"},
                            "amount": {"type": "number", "description": "The amount (if applicable)"},
                            "location": {"type": "string", "description": "The location (if applicable)"}
                        },
                        "propertyOrdering": ["target", "amount", "location"]
                    }
                },
                "propertyOrdering": ["type", "parameters"]
            }
        },
        "propertyOrdering": ["internal_thinking", "note_to_self", "say_outloud", "action"]
    }


def get_spectator_response_schema() -> Dict[str, Any]:
    """
    Get the response schema for players who are NOT on their turn (spectators).
    They can only observe, think, and communicate - no game actions allowed.
    
    Returns:
        Simplified JSON schema for spectators
    """
    return {
        "type": "object",
        "required": ["internal_thinking"],
        "properties": {
            "internal_thinking": {
                "type": "string",
                "description": "Track what's happening. What are opponents doing? What's your strategy for next turn?",
                "minLength": 30
            },
            "note_to_self": {
                "type": "string",
                "description": "Important facts for when it's your turn. Use only if essential for clarity or direct user query. Omit otherwise.",
                "maxLength": 100
            },
            "say_outloud": {
                "type": "string",
                "description": "Optional message to other players (max 100 chars). Propose trades or negotiate. You pay for this.",
                "maxLength": 100
            }
        },
        "propertyOrdering": ["internal_thinking", "note_to_self", "say_outloud"]
    }


def create_default_prompt_builder() -> PromptBuilder:
    """
    Create a prompt builder with default settings.
    
    Returns:
        Configured PromptBuilder instance
    """
    return PromptBuilder()
