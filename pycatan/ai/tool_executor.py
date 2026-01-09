"""
Tool Executor - Manages LLM Tool/Function Calling

This module handles:
1. Tool execution with proper logging
2. Token counting for tool inputs/outputs
3. Support for multiple tool calls
4. Detailed execution traces

The ToolExecutor bridges between LLM responses with tool calls
and the actual AgentTools implementation.
"""

import json
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from pycatan.ai.agent_tools import AgentTools

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Represents a single tool call from LLM."""
    id: str  # Unique ID for this call (from LLM response)
    name: str  # Tool name (e.g., "inspect_node")
    parameters: Dict[str, Any]  # Tool parameters
    
    # Execution results (filled after execution)
    result: Optional[Dict[str, Any]] = None
    success: bool = False
    error: Optional[str] = None
    execution_time: float = 0.0
    
    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "id": self.id,
            "name": self.name,
            "parameters": self.parameters,
            "result": self.result,
            "success": self.success,
            "error": self.error,
            "execution_time_ms": round(self.execution_time * 1000, 2),
            "tokens": {
                "input": self.input_tokens,
                "output": self.output_tokens,
                "total": self.input_tokens + self.output_tokens
            }
        }


@dataclass
class ToolExecutionBatch:
    """Represents a batch of tool calls (can be multiple in one turn)."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tool_calls: List[ToolCall] = field(default_factory=list)
    total_time: float = 0.0
    
    @property
    def total_input_tokens(self) -> int:
        """Sum of all input tokens."""
        return sum(call.input_tokens for call in self.tool_calls)
    
    @property
    def total_output_tokens(self) -> int:
        """Sum of all output tokens."""
        return sum(call.output_tokens for call in self.tool_calls)
    
    @property
    def total_tokens(self) -> int:
        """Sum of all tokens."""
        return self.total_input_tokens + self.total_output_tokens
    
    @property
    def success_count(self) -> int:
        """Number of successful calls."""
        return sum(1 for call in self.tool_calls if call.success)
    
    @property
    def failure_count(self) -> int:
        """Number of failed calls."""
        return sum(1 for call in self.tool_calls if not call.success)
    
    @property
    def total_calls(self) -> int:
        """Total number of tool calls in this batch."""
        return len(self.tool_calls)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "timestamp": self.timestamp,
            "total_calls": len(self.tool_calls),
            "successful": self.success_count,
            "failed": self.failure_count,
            "total_time_ms": round(self.total_time * 1000, 2),
            "tokens": {
                "input": self.total_input_tokens,
                "output": self.total_output_tokens,
                "total": self.total_tokens
            },
            "calls": [call.to_dict() for call in self.tool_calls]
        }


class ToolExecutor:
    """
    Executor for AI agent tools with full logging and token tracking.
    
    Features:
    - Executes tool calls from LLM responses
    - Supports multiple tool calls in parallel
    - Tracks tokens for input (parameters) and output (results)
    - Logs detailed execution traces
    - Handles errors gracefully
    """
    
    def __init__(self, agent_tools: AgentTools):
        """
        Initialize the tool executor.
        
        Args:
            agent_tools: AgentTools instance with game state
        """
        self.agent_tools = agent_tools
        self.execution_history: List[ToolExecutionBatch] = []
    
    def execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        call_id_prefix: str = "call"
    ) -> ToolExecutionBatch:
        """
        Execute a batch of tool calls.
        
        Args:
            tool_calls: List of tool call dictionaries from LLM
                       Each should have: {id, name, parameters}
            call_id_prefix: Prefix for generating call IDs if missing
            
        Returns:
            ToolExecutionBatch with all results
        """
        batch_start = time.time()
        batch = ToolExecutionBatch()
        
        logger.info(f"🔧 Executing {len(tool_calls)} tool call(s)...")
        
        for idx, tool_call_data in enumerate(tool_calls):
            # Parse tool call
            call_id = tool_call_data.get("id", f"{call_id_prefix}_{idx+1}")
            tool_name = tool_call_data.get("name", tool_call_data.get("function", ""))
            parameters = tool_call_data.get("parameters", tool_call_data.get("arguments", {}))
            
            # Handle parameters as JSON string
            if isinstance(parameters, str):
                try:
                    parameters = json.loads(parameters)
                except json.JSONDecodeError:
                    parameters = {}
            
            tool_call = ToolCall(
                id=call_id,
                name=tool_name,
                parameters=parameters
            )
            
            # Execute single tool
            self._execute_single_tool(tool_call)
            
            batch.tool_calls.append(tool_call)
        
        batch.total_time = time.time() - batch_start
        
        # Log summary
        logger.info(
            f"✅ Tool execution complete: {batch.success_count}/{len(tool_calls)} successful, "
            f"{batch.total_tokens} tokens, {batch.total_time:.2f}s"
        )
        
        # Add to history
        self.execution_history.append(batch)
        
        return batch
    
    def _execute_single_tool(self, tool_call: ToolCall) -> None:
        """
        Execute a single tool call and populate results.
        
        Args:
            tool_call: ToolCall object to execute (modified in place)
        """
        start_time = time.time()
        
        logger.info(f"  🔧 {tool_call.name}({tool_call.parameters})")
        
        try:
            # Count input tokens (parameters as JSON)
            param_json = json.dumps(tool_call.parameters)
            tool_call.input_tokens = self._estimate_tokens(param_json)
            
            # Execute the tool
            result = self.agent_tools.execute_tool(
                tool_name=tool_call.name,
                parameters=tool_call.parameters
            )
            
            # Count output tokens (result as JSON)
            result_json = json.dumps(result)
            tool_call.output_tokens = self._estimate_tokens(result_json)
            
            # Store result
            tool_call.result = result
            tool_call.success = True
            tool_call.execution_time = time.time() - start_time
            
            logger.info(
                f"     ✓ Success: {tool_call.output_tokens} tokens, "
                f"{tool_call.execution_time*1000:.1f}ms"
            )
            logger.debug(f"     Result preview: {str(result)[:100]}...")
            
        except Exception as e:
            tool_call.success = False
            tool_call.error = str(e)
            tool_call.execution_time = time.time() - start_time
            
            logger.error(f"     ✗ Failed: {e}")
    
    def format_tool_results_for_llm(self, batch: ToolExecutionBatch) -> str:
        """
        Format tool results for sending back to LLM.
        
        Creates a formatted text response that includes:
        - Each tool call with its result
        - Clear separation between calls
        - Error handling
        
        Args:
            batch: ToolExecutionBatch with executed calls
            
        Returns:
            Formatted string for LLM context
        """
        lines = ["=== Tool Results ===\n"]
        
        for call in batch.tool_calls:
            lines.append(f"Tool: {call.name}")
            lines.append(f"Parameters: {json.dumps(call.parameters, indent=2)}")
            
            if call.success:
                lines.append(f"Result:")
                lines.append(json.dumps(call.result, indent=2))
            else:
                lines.append(f"Error: {call.error}")
            
            lines.append("---\n")
        
        return "\n".join(lines)
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of all tool executions.
        
        Returns:
            Dictionary with summary stats
        """
        if not self.execution_history:
            return {
                "total_batches": 0,
                "total_calls": 0,
                "total_tokens": 0
            }
        
        total_calls = sum(len(batch.tool_calls) for batch in self.execution_history)
        total_tokens = sum(batch.total_tokens for batch in self.execution_history)
        successful_calls = sum(batch.success_count for batch in self.execution_history)
        failed_calls = sum(batch.failure_count for batch in self.execution_history)
        
        # Count by tool name
        tool_usage: Dict[str, int] = {}
        for batch in self.execution_history:
            for call in batch.tool_calls:
                tool_usage[call.name] = tool_usage.get(call.name, 0) + 1
        
        return {
            "total_batches": len(self.execution_history),
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "success_rate": f"{successful_calls / total_calls * 100:.1f}%" if total_calls > 0 else "0%",
            "total_tokens": total_tokens,
            "tool_usage": tool_usage,
            "recent_batches": [batch.to_dict() for batch in self.execution_history[-5:]]
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Uses rough approximation: 1 token ≈ 4 characters.
        This is the same method used in llm_client.py for consistency.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
