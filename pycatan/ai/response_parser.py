"""
Response parser for AI agent LLM responses.

This module handles:
1. Parsing JSON responses from LLM
2. Validating response structure against schemas
3. Error handling and recovery
4. Fallback mechanisms for malformed responses
5. Logging all parsing attempts
"""

import json
import logging
import re
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from pycatan.ai.schemas import (
    ResponseType,
    get_schema_for_response_type,
    validate_action_parameters,
    ACTIVE_TURN_RESPONSE_SCHEMA,
    OBSERVING_RESPONSE_SCHEMA
)


# Set up logging
logger = logging.getLogger(__name__)


class ParseError(Enum):
    """Types of parsing errors."""
    INVALID_JSON = "invalid_json"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_FIELD_TYPE = "invalid_field_type"
    INVALID_ACTION = "invalid_action"
    VALIDATION_ERROR = "validation_error"


@dataclass
class ParseResult:
    """Result of parsing an LLM response."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_type: Optional[ParseError] = None
    error_message: Optional[str] = None
    raw_response: Optional[str] = None
    fallback_used: bool = False


class ResponseParser:
    """
    Parser for AI agent LLM responses with error handling and fallback mechanisms.
    """
    
    def __init__(self, enable_fallbacks: bool = True, strict_mode: bool = False):
        """
        Initialize the response parser.
        
        Args:
            enable_fallbacks: Whether to use fallback mechanisms for parsing errors
            strict_mode: If True, fail on any validation error. If False, be lenient.
        """
        self.enable_fallbacks = enable_fallbacks
        self.strict_mode = strict_mode
        self.parse_attempts = 0
        self.successful_parses = 0
        self.failed_parses = 0
    
    def parse(self, 
              raw_response: str, 
              response_type: ResponseType,
              allowed_actions: Optional[list] = None) -> ParseResult:
        """
        Parse and validate an LLM response.
        
        Args:
            raw_response: Raw string response from LLM
            response_type: Expected response type (active turn or observing)
            allowed_actions: List of allowed action types (for validation)
            
        Returns:
            ParseResult with success status and parsed data or error info
        """
        self.parse_attempts += 1
        
        logger.info(f"Parsing response (attempt #{self.parse_attempts})")
        logger.debug(f"Raw response: {raw_response[:200]}...")
        
        # Step 1: Extract JSON from response
        json_str = self._extract_json(raw_response)
        if json_str is None:
            self.failed_parses += 1
            return ParseResult(
                success=False,
                error_type=ParseError.INVALID_JSON,
                error_message="Could not find valid JSON in response",
                raw_response=raw_response
            )
        
        # Step 2: Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            
            if self.enable_fallbacks:
                # Try to fix common JSON errors
                fixed_data = self._try_fix_json(json_str)
                if fixed_data is not None:
                    logger.warning("Used fallback JSON repair mechanism")
                    data = fixed_data
                else:
                    self.failed_parses += 1
                    return ParseResult(
                        success=False,
                        error_type=ParseError.INVALID_JSON,
                        error_message=f"JSON parse error: {str(e)}",
                        raw_response=raw_response
                    )
            else:
                self.failed_parses += 1
                return ParseResult(
                    success=False,
                    error_type=ParseError.INVALID_JSON,
                    error_message=f"JSON parse error: {str(e)}",
                    raw_response=raw_response
                )
        
        # Step 3: Validate structure
        validation_result = self._validate_structure(data, response_type)
        if not validation_result[0]:
            print(f"\n🔍 DEBUG - Validation failed: {validation_result[1]}")
            print(f"📋 Data: {json.dumps(data, indent=2)}")
            print(f"📋 Response Type: {response_type}")
            print(f"📋 Schema required fields: {get_schema_for_response_type(response_type).get('required')}\n")
            if self.enable_fallbacks and not self.strict_mode:
                # Try to repair structure
                data = self._try_repair_structure(data, response_type)
                if data is None:
                    self.failed_parses += 1
                    return ParseResult(
                        success=False,
                        error_type=ParseError.VALIDATION_ERROR,
                        error_message=validation_result[1],
                        raw_response=raw_response,
                        data=data
                    )
                logger.warning("Used fallback structure repair mechanism")
            else:
                self.failed_parses += 1
                return ParseResult(
                    success=False,
                    error_type=ParseError.VALIDATION_ERROR,
                    error_message=validation_result[1],
                    raw_response=raw_response,
                    data=data
                )
        
        # Step 4: Validate action if present
        if response_type == ResponseType.ACTIVE_TURN and "action" in data:
            action_validation = self._validate_action(data["action"], allowed_actions)
            if not action_validation[0]:
                if self.strict_mode:
                    self.failed_parses += 1
                    return ParseResult(
                        success=False,
                        error_type=ParseError.INVALID_ACTION,
                        error_message=action_validation[1],
                        raw_response=raw_response,
                        data=data
                    )
                else:
                    logger.warning(f"Action validation warning: {action_validation[1]}")
        
        # Success!
        self.successful_parses += 1
        logger.info("Successfully parsed and validated response")
        
        return ParseResult(
            success=True,
            data=data,
            raw_response=raw_response
        )
    
    def _extract_json(self, text: str) -> Optional[str]:
        """
        Extract JSON from text that may contain additional content.
        
        Handles cases where LLM returns JSON wrapped in markdown code blocks
        or with additional text before/after.
        """
        # Try to find JSON in code blocks first
        code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(code_block_pattern, text, re.DOTALL)
        if matches:
            return matches[0]
        
        # If text looks like pure JSON, return as is
        stripped = text.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            return stripped
        
        # Try to find the first '{' and last '}' - simple but effective
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1]
        
        return None
    
    def _try_fix_json(self, json_str: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to fix common JSON errors.
        
        Common issues:
        - Missing closing quotes
        - Trailing commas
        - Single quotes instead of double quotes
        """
        fixes = [
            # Replace single quotes with double quotes (careful with apostrophes)
            lambda s: s.replace("'", '"'),
            # Remove trailing commas
            lambda s: re.sub(r',\s*}', '}', s),
            lambda s: re.sub(r',\s*]', ']', s),
        ]
        
        for fix in fixes:
            try:
                fixed = fix(json_str)
                return json.loads(fixed)
            except (json.JSONDecodeError, Exception):
                continue
        
        return None
    
    def _validate_structure(self, data: Dict[str, Any], response_type: ResponseType) -> Tuple[bool, Optional[str]]:
        """
        Validate response structure against schema.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        schema = get_schema_for_response_type(response_type)
        
        # Check required fields
        for field in schema.get("required", []):
            if field not in data:
                return False, f"Missing required field: '{field}'"
        
        # Validate field types and constraints
        for field, value in data.items():
            if field in schema["properties"]:
                field_schema = schema["properties"][field]
                
                # Check type
                expected_type = field_schema.get("type")
                if expected_type == "string" and not isinstance(value, str):
                    return False, f"Field '{field}' must be a string"
                elif expected_type == "object" and not isinstance(value, dict):
                    return False, f"Field '{field}' must be an object"
                
                # Check string constraints
                if isinstance(value, str):
                    min_length = field_schema.get("minLength")
                    max_length = field_schema.get("maxLength")
                    if min_length and len(value) < min_length:
                        return False, f"Field '{field}' must be at least {min_length} characters"
                    if max_length and len(value) > max_length:
                        return False, f"Field '{field}' must be at most {max_length} characters"
        
        return True, None
    
    def _validate_action(self, action: Dict[str, Any], allowed_actions: Optional[list]) -> Tuple[bool, Optional[str]]:
        """
        Validate action structure and parameters.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(action, dict):
            return False, "Action must be an object"
        
        if "type" not in action:
            return False, "Action missing 'type' field"
        
        if "parameters" not in action:
            return False, "Action missing 'parameters' field"
        
        action_type = action["type"]
        
        # Check if action is in allowed list
        if allowed_actions:
            if action_type not in allowed_actions:
                return False, f"Action type '{action_type}' not in allowed actions: {allowed_actions}"
        
        # Validate parameters
        parameters = action["parameters"]
        if not isinstance(parameters, dict):
            return False, "Action parameters must be an object"
        
        # Validate parameter schema
        param_valid, param_error = validate_action_parameters(action_type, parameters)
        if not param_valid:
            return False, param_error
        
        return True, None
    
    def _try_repair_structure(self, data: Dict[str, Any], response_type: ResponseType) -> Optional[Dict[str, Any]]:
        """
        Attempt to repair missing or invalid fields.
        
        Strategies:
        - Add default values for missing optional fields
        - Convert types if possible
        - Use empty objects/strings as fallbacks
        """
        schema = get_schema_for_response_type(response_type)
        repaired = data.copy()
        
        # Add missing required fields with defaults
        for field in schema.get("required", []):
            if field not in repaired:
                if field == "internal_thinking":
                    repaired[field] = "[No reasoning provided]"
                elif field == "action":
                    repaired[field] = {"type": "wait_for_response", "parameters": {}}
                else:
                    return None  # Can't repair
        
        # Try to fix internal_thinking if too short
        if "internal_thinking" in repaired:
            min_length = schema["properties"]["internal_thinking"].get("minLength", 0)
            if len(repaired["internal_thinking"]) < min_length:
                repaired["internal_thinking"] += " [Response was too brief]"
        
        return repaired
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get parser statistics."""
        return {
            "total_attempts": self.parse_attempts,
            "successful": self.successful_parses,
            "failed": self.failed_parses,
            "success_rate": (
                self.successful_parses / self.parse_attempts 
                if self.parse_attempts > 0 
                else 0.0
            )
        }
