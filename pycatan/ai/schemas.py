"""
JSON Schema definitions for AI agent requests and responses.

This module contains all schema definitions used for:
1. Validating LLM responses
2. Generating prompts with schema documentation
3. Type checking and validation

Schema Versions:
- SCHEMA_V1: Original schema with technical descriptions
- SCHEMA_V2: Improved schema with natural language prompts (DEFAULT)
"""

from typing import Dict, Any, List, Optional
from enum import Enum


class ResponseType(Enum):
    """Types of responses expected from AI agents."""
    ACTIVE_TURN = "active_turn"  # When it's the agent's turn to act
    OBSERVING = "observing"       # When agent is observing other players


class SchemaVersion(Enum):
    """Available schema versions."""
    V1 = "v1"  # Original technical schema
    V2 = "v2"  # Natural language schema (DEFAULT)


# Default schema version
DEFAULT_SCHEMA_VERSION = SchemaVersion.V2


# ============================================================================
# SCHEMA V1 - Original Technical Schema
# ============================================================================

ACTIVE_TURN_RESPONSE_SCHEMA_V1 = {
    "type": "object",
    "required": ["internal_thinking", "action"],
    "properties": {
        "internal_thinking": {
            "type": "string",
            "description": "Private strategy. What's your plan and why? Do not invent resources. Verify indices in Array N carefully. Write a detailed analysis (600+ chars) only AFTER verifying the node data",
            "minLength": 1000
        },
        "note_to_self": {
            "type": "string",
            "description": "Save important observations and plans for future turns. Examples: opponent strategies, key nodes to claim, resource priorities, or threats to watch. This helps maintain continuity between turns.",
            "maxLength": 100
        },
        "say_outloud": {
            "type": "string",
            "description": "Communicate with other players! Use for: trade proposals, warnings, bluffs, alliance hints, or strategic banter. Makes the game more interesting and can influence opponents.",
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

OBSERVING_RESPONSE_SCHEMA_V1 = {
    "type": "object",
    "required": ["internal_thinking"],
    "properties": {
        "internal_thinking": {
            "type": "string",
            "description": "Track what's happening. Analyze opponent moves by verifying their positions in Array N and resources from Array H. What patterns do you see? What's your strategy for next turn? Be specific about locations and threats.",
            "minLength": 30
        },
        "note_to_self": {
            "type": "string",
            "description": "Track key developments! Note opponent positions, resource imbalances, or strategic opportunities you noticed. This memory persists between turns.",
            "maxLength": 100
        },
        "say_outloud": {
            "type": "string",
            "description": "Even when observing, you can negotiate! Propose trades, form alliances, or send strategic messages. Example: 'I'll trade ore for wheat next turn' or 'Nice move!'",
            "maxLength": 100
        }
    },
    "propertyOrdering": [
        "internal_thinking",
        "note_to_self",
        "say_outloud"
    ]
}


# ============================================================================
# SCHEMA V2 - Natural Language Schema (DEFAULT)
# ============================================================================

ACTIVE_TURN_RESPONSE_SCHEMA_V2 = {
    "type": "object",
    "required": ["internal_thinking", "action"],
    "properties": {
        "internal_thinking": {
            "type": "string",
            "description": "Private strategy. Plan your move logically here. Analyze the board, probabilities, and opponents. NOTE: Keep your logic HERE. Do not leak technical explanations into 'say_outloud'.",
            "minLength": 1000
        },
        "note_to_self": {
            "type": "string",
            "description": "Save important observations for future turns (e.g., 'Player 3 is hoarding ore').",
            "maxLength": 100
        },
        "say_outloud": {
            "type": "string",
            "description": "Table talk. Must be natural. If nothing interesting happened, leave empty. If frustrated or happy, express it briefly. mimic real chat: no capitalization sometimes, slang allowed but not forced.",
            "maxLength": 120
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
                    "description": "Action parameters as JSON string. Example: {\"node\": 14} or {}"
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

OBSERVING_RESPONSE_SCHEMA_V2 = {
    "type": "object",
    "required": ["internal_thinking"],
    "properties": {
        "internal_thinking": {
            "type": "string",
            "description": "Private thoughts while watching. What are opponents doing? Any threats? What's your plan for your next turn?",
            "minLength": 30
        },
        "note_to_self": {
            "type": "string",
            "description": "Save important observations (e.g., 'Blue is going for longest road').",
            "maxLength": 100
        },
        "say_outloud": {
            "type": "string",
            "description": "React naturally to what's happening. Can be empty if nothing notable. Keep it casual.",
            "maxLength": 120
        }
    },
    "propertyOrdering": [
        "internal_thinking",
        "note_to_self",
        "say_outloud"
    ]
}


# ============================================================================
# Current Active Schemas (aliases to selected version)
# ============================================================================

# These are the schemas used by the system - update to switch versions
ACTIVE_TURN_RESPONSE_SCHEMA = ACTIVE_TURN_RESPONSE_SCHEMA_V2
OBSERVING_RESPONSE_SCHEMA = OBSERVING_RESPONSE_SCHEMA_V2


def get_schema_for_response_type(
    response_type: ResponseType, 
    version: SchemaVersion = None
) -> Dict[str, Any]:
    """
    Get the appropriate schema based on response type and version.
    
    Args:
        response_type: Type of response expected (active turn or observing)
        version: Schema version to use (defaults to DEFAULT_SCHEMA_VERSION)
        
    Returns:
        JSON schema dictionary
    """
    if version is None:
        version = DEFAULT_SCHEMA_VERSION
    
    if version == SchemaVersion.V1:
        if response_type == ResponseType.ACTIVE_TURN:
            return ACTIVE_TURN_RESPONSE_SCHEMA_V1
        elif response_type == ResponseType.OBSERVING:
            return OBSERVING_RESPONSE_SCHEMA_V1
    elif version == SchemaVersion.V2:
        if response_type == ResponseType.ACTIVE_TURN:
            return ACTIVE_TURN_RESPONSE_SCHEMA_V2
        elif response_type == ResponseType.OBSERVING:
            return OBSERVING_RESPONSE_SCHEMA_V2
    
    raise ValueError(f"Unknown response type: {response_type} or version: {version}")


def get_schema_description(response_type: ResponseType, version: SchemaVersion = None) -> str:
    """
    Get a human-readable description of what the schema expects.
    
    Args:
        response_type: Type of response expected
        version: Schema version (defaults to DEFAULT_SCHEMA_VERSION)
        
    Returns:
        Description string
    """
    if version is None:
        version = DEFAULT_SCHEMA_VERSION
        
    if response_type == ResponseType.ACTIVE_TURN:
        if version == SchemaVersion.V1:
            return (
                "Response must include:\n"
                "- internal_thinking: VERIFY data from Arrays N/H first, then write 1000+ char analysis\n"
                "- action: {type: action_name, parameters: {...}}\n"
                "Encouraged (use frequently!):\n"
                "- note_to_self: Save key observations for future turns (max 100 chars)\n"
                "- say_outloud: Communicate with other players (max 100 chars)"
            )
        else:  # V2
            return (
                "Response must include:\n"
                "- internal_thinking: Plan your move logically (1000+ chars). Keep technical analysis HERE.\n"
                "- action: {type: action_name, parameters: {...}}\n"
                "Optional:\n"
                "- note_to_self: Save observations for later (max 100 chars)\n"
                "- say_outloud: Natural table talk - casual, not technical (max 120 chars)"
            )
    elif response_type == ResponseType.OBSERVING:
        if version == SchemaVersion.V1:
            return (
                "Response must include:\n"
                "- internal_thinking: Track opponent moves, verify positions in Arrays N/H (min 30 chars)\n"
                "Encouraged (use frequently!):\n"
                "- note_to_self: Track key developments for later (max 100 chars)\n"
                "- say_outloud: Negotiate or send messages (max 100 chars)"
            )
        else:  # V2
            return (
                "Response must include:\n"
                "- internal_thinking: Private thoughts while watching (min 30 chars)\n"
                "Optional:\n"
                "- note_to_self: Save important observations (max 100 chars)\n"
                "- say_outloud: React naturally - keep it casual (max 120 chars)"
            )
    else:
        return "Unknown response type"


def set_default_schema_version(version: SchemaVersion) -> None:
    """
    Set the default schema version used by the system.
    
    Args:
        version: SchemaVersion.V1 or SchemaVersion.V2
    """
    global DEFAULT_SCHEMA_VERSION, ACTIVE_TURN_RESPONSE_SCHEMA, OBSERVING_RESPONSE_SCHEMA
    
    DEFAULT_SCHEMA_VERSION = version
    
    if version == SchemaVersion.V1:
        ACTIVE_TURN_RESPONSE_SCHEMA = ACTIVE_TURN_RESPONSE_SCHEMA_V1
        OBSERVING_RESPONSE_SCHEMA = OBSERVING_RESPONSE_SCHEMA_V1
    else:
        ACTIVE_TURN_RESPONSE_SCHEMA = ACTIVE_TURN_RESPONSE_SCHEMA_V2
        OBSERVING_RESPONSE_SCHEMA = OBSERVING_RESPONSE_SCHEMA_V2


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
