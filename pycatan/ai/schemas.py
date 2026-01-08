"""
JSON Schema definitions for AI agent requests and responses.

This module contains all schema definitions used for:
1. Validating LLM responses
2. Generating prompts with schema documentation
3. Type checking and validation
"""

from typing import Dict, Any, List, Optional
from enum import Enum


class ResponseType(Enum):
    """Types of responses expected from AI agents."""
    ACTIVE_TURN = "active_turn"  # When it's the agent's turn to act
    OBSERVING = "observing"       # When agent is observing other players


# Schema for when it's the agent's turn (must take action)
ACTIVE_TURN_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["internal_thinking", "action"],
    "properties": {
        "internal_thinking": {
            "type": "string",
            "description": "Private strategy. What's your plan and why?",
            "minLength": 1000
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
            "required": ["type"],
            "properties": {
                "type": {
                    "type": "string",
                    "description": "The action type (must match one from allowed_actions in constraints)"
                },
                "parameters": {
                    "type": "string",
                    "description": "Action parameters as JSON string. Example: {\"node\": 14} or {} if no parameters needed"
                }
            },
            "propertyOrdering": ["type", "parameters"]
        }
    },
    "propertyOrdering": [
        "internal_thinking",
        "note_to_self", 
        "say_outloud",
        "action"
    ]
}


# Schema for when agent is observing (not their turn)
OBSERVING_RESPONSE_SCHEMA = {
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
    "propertyOrdering": [
        "internal_thinking",
        "note_to_self",
        "say_outloud"
    ]
}


def get_schema_for_response_type(response_type: ResponseType) -> Dict[str, Any]:
    """
    Get the appropriate schema based on response type.
    
    Args:
        response_type: Type of response expected (active turn or observing)
        
    Returns:
        JSON schema dictionary
    """
    if response_type == ResponseType.ACTIVE_TURN:
        return ACTIVE_TURN_RESPONSE_SCHEMA
    elif response_type == ResponseType.OBSERVING:
        return OBSERVING_RESPONSE_SCHEMA
    else:
        raise ValueError(f"Unknown response type: {response_type}")


def get_schema_description(response_type: ResponseType) -> str:
    """
    Get a human-readable description of what the schema expects.
    
    Args:
        response_type: Type of response expected
        
    Returns:
        Description string
    """
    if response_type == ResponseType.ACTIVE_TURN:
        return (
            "Response must include:\n"
            "- internal_thinking: Your strategy (min 50 chars)\n"
            "- action: {type: action_name, parameters: {...}}\n"
            "Optional:\n"
            "- note_to_self: Important reminder (max 100 chars)\n"
            "- say_outloud: Message to other players (max 100 chars)"
        )
    elif response_type == ResponseType.OBSERVING:
        return (
            "Response must include:\n"
            "- internal_thinking: What you observed (min 30 chars)\n"
            "Optional:\n"
            "- note_to_self: Important reminder (max 100 chars)\n"
            "- say_outloud: Message to other players (max 100 chars)"
        )
    else:
        return "Unknown response type"


# Common action parameter schemas for validation
ACTION_PARAMETER_SCHEMAS = {
    "build_road": {
        "required": ["from", "to"],
        "properties": {
            "from": {"type": "string", "description": "Starting node ID"},
            "to": {"type": "string", "description": "Ending node ID"}
        }
    },
    "build_settlement": {
        "required": ["node"],
        "properties": {
            "node": {"type": "string", "description": "Node ID where to build"}
        }
    },
    "build_city": {
        "required": ["node"],
        "properties": {
            "node": {"type": "string", "description": "Node ID where settlement exists"}
        }
    },
    "buy_dev_card": {
        "required": [],
        "properties": {}
    },
    "play_knight": {
        "required": ["hex", "victim"],
        "properties": {
            "hex": {"type": "string", "description": "Hex ID to move robber"},
            "victim": {"type": "string", "description": "Player to steal from (or 'none')"}
        }
    },
    "trade_with_bank": {
        "required": ["give", "receive"],
        "properties": {
            "give": {"type": "string", "description": "Resource to give"},
            "receive": {"type": "string", "description": "Resource to receive"}
        }
    },
    "propose_trade": {
        "required": ["offer", "request"],
        "properties": {
            "offer": {"type": "object", "description": "Resources offered"},
            "request": {"type": "object", "description": "Resources requested"}
        }
    },
    "wait_for_response": {
        "required": [],
        "properties": {}
    },
    "end_turn": {
        "required": [],
        "properties": {}
    }
}


def validate_action_parameters(action_type: str, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate that action parameters match expected schema.
    
    Args:
        action_type: Type of action (e.g., "build_road")
        parameters: Parameters provided by the agent
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if action_type not in ACTION_PARAMETER_SCHEMAS:
        # Unknown action type - let game manager handle validation
        return True, None
    
    schema = ACTION_PARAMETER_SCHEMAS[action_type]
    
    # Check required parameters
    for required_param in schema["required"]:
        if required_param not in parameters:
            return False, f"Missing required parameter '{required_param}' for action '{action_type}'"
    
    # Check parameter types if defined
    for param_name, param_value in parameters.items():
        if param_name in schema["properties"]:
            expected_type = schema["properties"][param_name].get("type")
            if expected_type == "string" and not isinstance(param_value, str):
                return False, f"Parameter '{param_name}' should be a string"
            elif expected_type == "number" and not isinstance(param_value, (int, float)):
                return False, f"Parameter '{param_name}' should be a number"
            elif expected_type == "object" and not isinstance(param_value, dict):
                return False, f"Parameter '{param_name}' should be an object"
    
    return True, None
