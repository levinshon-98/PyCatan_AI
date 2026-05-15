"""
LLM Client for AI Agents.

This module provides abstraction for different LLM providers.
Currently supports:
- Google Gemini
"""

import logging
import time
import json
import os
import ssl
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime

# Fix SSL certificate verification on Windows
try:
    import certifi
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())
    os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())
except ImportError:
    pass

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """Single chunk from streaming response."""
    chunk_type: str  # 'thought', 'text', 'function_call', 'done'
    content: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    is_complete: bool = False


@dataclass
class LLMResponse:
    """Response from LLM API call."""
    success: bool
    content: Optional[str] = None
    raw_response: Optional[Any] = None
    error: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)  # Function calls from LLM
    
    # Metadata
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    thinking_tokens: int = 0  # For thinking mode
    total_tokens: int = 0
    latency_seconds: float = 0.0
    finish_reason: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        tokens_dict = {
            "prompt": self.prompt_tokens,
            "completion": self.completion_tokens,
            "total": self.total_tokens
        }
        if self.thinking_tokens > 0:
            tokens_dict["thinking"] = self.thinking_tokens
            
        result = {
            "success": self.success,
            "content": self.content[:200] + "..." if self.content and len(self.content) > 200 else self.content,
            "error": self.error,
            "model": self.model,
            "tokens": tokens_dict,
            "latency_seconds": round(self.latency_seconds, 2),
            "finish_reason": self.finish_reason,
            "timestamp": self.timestamp
        }
        
        # Add tool calls if present
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        
        return result


@dataclass
class LLMStats:
    """Statistics for LLM usage."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    tool_tokens: int = 0  # Tokens from tool inputs/outputs
    total_cost_usd: float = 0.0
    total_latency: float = 0.0
    
    def add_request(self, response: LLMResponse, cost: float = 0.0):
        """Add a request to statistics."""
        self.total_requests += 1
        if response.success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        self.total_tokens += response.total_tokens
        self.total_cost_usd += cost
        self.total_latency += response.latency_seconds
    
    def add_tool_tokens(self, tokens: int):
        """Add tokens from tool execution."""
        self.tool_tokens += tokens
        self.total_tokens += tokens
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful": self.successful_requests,
            "failed": self.failed_requests,
            "success_rate": f"{self.successful_requests / self.total_requests * 100:.1f}%" if self.total_requests > 0 else "0%",
            "total_tokens": self.total_tokens,
            "tool_tokens": self.tool_tokens,
            "llm_tokens": self.total_tokens - self.tool_tokens,
            "total_cost_usd": f"${self.total_cost_usd:.4f}",
            "avg_latency": f"{self.total_latency / self.total_requests:.2f}s" if self.total_requests > 0 else "0s"
        }


class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    def __init__(self, model: str, api_key: str, **kwargs):
        self.model = model
        self.api_key = api_key
        self.stats = LLMStats()
        self.config = kwargs
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate response from LLM."""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return self.stats.to_dict()


class GeminiClient(LLMClient):
    """
    Google Gemini LLM Client.
    
    Supports Gemini models through the new Google GenAI SDK.
    Includes support for thinking mode (Gemini 2.0+).
    """
    
    def __init__(self, 
                 model: str = "gemini-2.0-flash-exp",
                 api_key: str = "",
                 temperature: float = 0.7,
                 max_tokens: Optional[int] = None,
                 response_format: str = "json",
                 **kwargs):
        """
        Initialize Gemini client.
        
        Args:
            model: Model name (e.g., "gemini-2.0-flash-exp")
            api_key: Google API key
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            response_format: Response format ("json" or "text")
            **kwargs: Additional configuration
        """
        super().__init__(model, api_key, **kwargs)
        
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.response_format = response_format
        self.api_key = api_key
        
        # Initialize new GenAI client
        try:
            from google import genai
            from google.genai import types
            
            self.genai = genai
            self.types = types
            self.client = genai.Client(api_key=api_key)
            logger.info(f"Initialized Gemini client (new SDK) with model: {model}")
        except ImportError:
            logger.error("google-genai package not installed. Install with: pip install google-genai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
    
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate response from Gemini using new SDK.
        
        Args:
            prompt: Prompt text (can be JSON string or plain text)
            **kwargs: Override default generation parameters
                     - response_schema: JSON schema to enforce structure
                     - enable_thinking: Enable thinking mode
                     - thinking_budget: Max tokens for thinking
                     - tools: List of tool schemas for function calling
            
        Returns:
            LLMResponse object with result (may include tool_calls)
        """
        start_time = time.time()
        
        # Build generation config
        config_dict = {
            "temperature": kwargs.get("temperature", self.temperature),
        }
        
        if self.max_tokens:
            config_dict["max_output_tokens"] = kwargs.get("max_tokens", self.max_tokens)
        
        # Thinking mode (Gemini 2.0+)
        if kwargs.get("enable_thinking", False):
            thinking_budget = kwargs.get("thinking_budget", 16000)
            config_dict["thinking_config"] = self.types.ThinkingConfig(
                thinking_budget=thinking_budget
            )
            logger.info(f"Thinking mode enabled with budget: {thinking_budget}")
        
        # Add tools for function calling if provided
        # NOTE: Must be done BEFORE setting response format (they're mutually exclusive!)
        tools = kwargs.get("tools", [])
        has_tools = False
        if tools:
            # Convert tool schemas to Gemini Tool objects
            try:
                gemini_tools = []
                for tool_dict in tools:
                    # Create FunctionDeclaration for each tool
                    func_decl = self.types.FunctionDeclaration(
                        name=tool_dict.get("name", ""),
                        description=tool_dict.get("description", ""),
                        parameters=self._remove_unsupported_fields(tool_dict.get("parameters", {}))
                    )
                    gemini_tools.append(func_decl)
                
                # Wrap in Tool object
                config_dict["tools"] = [self.types.Tool(function_declarations=gemini_tools)]
                has_tools = True
                logger.info(f"Function calling enabled with {len(tools)} tool(s)")
            except Exception as e:
                logger.warning(f"Failed to create tool declarations: {e}")
                logger.warning("Tools will be disabled.")
                # Continue without tools if conversion fails
                pass
        
        # Set response format
        # NOTE: Gemini 3 supports tools + JSON schema together!
        # For older models (Gemini 2.x), this was incompatible
        response_format = kwargs.get("response_format", self.response_format)
        if response_format == "json":
            config_dict["response_mime_type"] = "application/json"
            
            # Add response_json_schema if provided (enforces structure)
            if "response_schema" in kwargs:
                schema = kwargs["response_schema"]
                cleaned_schema = self._remove_unsupported_fields(schema)
                config_dict["response_json_schema"] = cleaned_schema
        
        try:
            logger.info(f"Sending request to Gemini ({self.model})...")
            logger.debug(f"Prompt length: {len(prompt)} chars")
            
            # Create generation config
            generation_config = self.types.GenerateContentConfig(**config_dict)
            
            # Generate response using new SDK
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=generation_config
            )
            
            latency = time.time() - start_time
            
            # Extract content and tool calls
            content = response.text if hasattr(response, 'text') else ""
            tool_calls = []
            finish_reason = None
            
            # Check for function calls in response
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason is not None:
                    finish_reason = str(candidate.finish_reason)
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call'):
                            # Extract function call
                            func_call = part.function_call
                            # Guard: func_call or func_call.name can be None sometimes
                            if func_call is None:
                                logger.warning("Skipping None function_call in response")
                                continue
                            func_name = getattr(func_call, 'name', None)
                            if func_name is None:
                                logger.warning(f"Skipping function_call with None name: {func_call}")
                                continue
                            tool_calls.append({
                                "id": f"call_{len(tool_calls)+1}",
                                "name": func_name,
                                "parameters": dict(func_call.args) if hasattr(func_call, 'args') else {}
                            })
            
            # Token counting from usage metadata
            thinking_tokens = 0
            try:
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    prompt_tokens = response.usage_metadata.prompt_token_count or 0
                    completion_tokens = response.usage_metadata.candidates_token_count or 0
                    total_tokens = response.usage_metadata.total_token_count or 0
                    
                    # Extract thinking tokens if available
                    if hasattr(response.usage_metadata, 'thoughts_token_count'):
                        thinking_tokens = response.usage_metadata.thoughts_token_count or 0
                    
                    logger.debug(f"Token counts from API: prompt={prompt_tokens}, completion={completion_tokens}, thinking={thinking_tokens}, total={total_tokens}")
                else:
                    # Fallback to estimation
                    prompt_tokens = self._estimate_tokens(prompt)
                    completion_tokens = self._estimate_tokens(content)
                    total_tokens = prompt_tokens + completion_tokens
                    logger.debug(f"Token counts estimated: prompt={prompt_tokens}, completion={completion_tokens}")
            except Exception as e:
                logger.warning(f"Failed to get token counts: {e}, using estimation")
                prompt_tokens = self._estimate_tokens(prompt)
                completion_tokens = self._estimate_tokens(content)
                total_tokens = prompt_tokens + completion_tokens
            
            # Calculate cost (Gemini 2.0 Flash pricing)
            # Input: $0.00001875 per 1K tokens, Output: $0.000075 per 1K tokens
            # Thinking tokens are charged as input tokens
            cost = ((prompt_tokens + thinking_tokens) / 1000 * 0.00001875) + (completion_tokens / 1000 * 0.000075)
            
            llm_response = LLMResponse(
                success=True,
                content=content,
                raw_response=response,
                tool_calls=tool_calls,
                model=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                thinking_tokens=thinking_tokens,
                total_tokens=total_tokens,
                latency_seconds=latency,
                finish_reason=finish_reason
            )
            
            self.stats.add_request(llm_response, cost)
            
            if tool_calls:
                logger.info(f"✅ Response with {len(tool_calls)} tool call(s): {completion_tokens} tokens, {latency:.2f}s")
                for tc in tool_calls:
                    logger.info(f"   🔧 {tc['name']}({tc['parameters']})")
            elif thinking_tokens > 0:
                logger.info(f"✅ Response received: {completion_tokens} tokens (+{thinking_tokens} thinking), {latency:.2f}s")
            else:
                logger.info(f"✅ Response received: {completion_tokens} tokens, {latency:.2f}s")
            
            if content:
                logger.debug(f"Response preview: {content[:100]}...")
            if finish_reason and "STOP" not in finish_reason:
                logger.warning(f"Gemini finish_reason={finish_reason}")
            
            return llm_response
            
        except Exception as e:
            latency = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"❌ Gemini API error: {error_msg}")
            
            llm_response = LLMResponse(
                success=False,
                error=error_msg,
                model=self.model,
                latency_seconds=latency
            )
            
            self.stats.add_request(llm_response, 0.0)
            
            return llm_response
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Rough approximation: 1 token ≈ 4 characters for English text.
        This is not exact but sufficient for cost estimation.
        """
        return len(text) // 4
    
    # Note: _convert_tool_schema removed - using FunctionDeclaration directly now
    
    def _remove_unsupported_fields(self, schema: Any) -> Any:
        """
        Remove fields that are not supported by the Python SDK.
        
        The Google AI Studio interface supports propertyOrdering, but the
        Python SDK (google-generativeai) does NOT support it and will error.
        
        Also removes: minLength, maxLength, additionalProperties (not supported)
        
        Args:
            schema: Schema dict or any nested structure
            
        Returns:
            Cleaned schema without unsupported fields
        """
        if not isinstance(schema, dict):
            return schema
        
        # Fields to remove for Python SDK compatibility
        unsupported = ['propertyOrdering', 'minLength', 'maxLength', 'additionalProperties']
        
        cleaned = {}
        for key, value in schema.items():
            if key in unsupported:
                continue
            
            # Recursively clean nested structures
            if isinstance(value, dict):
                cleaned[key] = self._remove_unsupported_fields(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    self._remove_unsupported_fields(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                cleaned[key] = value
        
        return cleaned
    
    def generate_stream(self, prompt: str, on_chunk: Optional[Callable[[StreamChunk], None]] = None, **kwargs):
        """
        Generate response with streaming support.
        
        Yields chunks in real-time with thoughts, text, and function calls.
        
        Args:
            prompt: Prompt text
            on_chunk: Optional callback for each chunk
            **kwargs: Same as generate() - supports thinking, tools, etc.
            
        Yields:
            StreamChunk objects with type, content, and metadata
            
        Returns:
            Final LLMResponse when streaming completes
        """
        start_time = time.time()
        
        # Build generation config (same as generate)
        config_dict = {
            "temperature": kwargs.get("temperature", self.temperature),
        }
        
        if self.max_tokens:
            config_dict["max_output_tokens"] = kwargs.get("max_tokens", self.max_tokens)
        
        # Thinking mode with includeThoughts for streaming
        if kwargs.get("enable_thinking", False):
            thinking_budget = kwargs.get("thinking_budget", 16000)
            config_dict["thinking_config"] = self.types.ThinkingConfig(
                thinking_budget=thinking_budget,
                include_thoughts=True  # ✨ This enables thought summaries in stream!
            )
            logger.info(f"Streaming with thinking enabled (budget: {thinking_budget})")
        
        # Add tools if provided
        tools = kwargs.get("tools", [])
        if tools:
            try:
                gemini_tools = []
                for tool_dict in tools:
                    func_decl = self.types.FunctionDeclaration(
                        name=tool_dict.get("name", ""),
                        description=tool_dict.get("description", ""),
                        parameters=self._remove_unsupported_fields(tool_dict.get("parameters", {}))
                    )
                    gemini_tools.append(func_decl)
                
                config_dict["tools"] = [self.types.Tool(function_declarations=gemini_tools)]
                logger.info(f"Streaming with {len(tools)} tool(s)")
            except Exception as e:
                logger.warning(f"Failed to create tools: {e}")
        
        # Set response format
        response_format = kwargs.get("response_format", self.response_format)
        if response_format == "json":
            config_dict["response_mime_type"] = "application/json"
            if "response_schema" in kwargs:
                schema = kwargs["response_schema"]
                cleaned_schema = self._remove_unsupported_fields(schema)
                config_dict["response_json_schema"] = cleaned_schema
        
        try:
            logger.info(f"🌊 Starting streaming request to {self.model}...")
            
            generation_config = self.types.GenerateContentConfig(**config_dict)
            
            # Stream response!
            accumulated_thoughts = ""
            accumulated_text = ""
            tool_calls = []
            finish_reason = None
            
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=generation_config
            ):
                if not hasattr(chunk, 'candidates') or not chunk.candidates:
                    continue
                    
                candidate = chunk.candidates[0]
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason is not None:
                    finish_reason = str(candidate.finish_reason)
                if not hasattr(candidate, 'content') or not hasattr(candidate.content, 'parts'):
                    continue
                
                for part in candidate.content.parts:
                    # Check for function call FIRST (function_calls don't have text)
                    if hasattr(part, 'function_call') and part.function_call:
                        func_call = part.function_call
                        if hasattr(func_call, 'name') and func_call.name:
                            tool_call_dict = {
                                "id": f"call_{len(tool_calls)+1}",
                                "name": func_call.name,
                                "parameters": dict(func_call.args) if hasattr(func_call, 'args') else {}
                            }
                            tool_calls.append(tool_call_dict)
                            
                            stream_chunk = StreamChunk(
                                chunk_type='function_call',
                                function_call=tool_call_dict,
                                is_complete=False
                            )
                            if on_chunk:
                                on_chunk(stream_chunk)
                            yield stream_chunk
                        continue
                    
                    # Skip parts without text
                    if not hasattr(part, 'text') or not part.text:
                        continue
                    
                    # Check if this is a thought
                    if hasattr(part, 'thought') and part.thought:
                        accumulated_thoughts += part.text
                        stream_chunk = StreamChunk(
                            chunk_type='thought',
                            content=part.text,
                            is_complete=False
                        )
                        if on_chunk:
                            on_chunk(stream_chunk)
                        yield stream_chunk
                    
                    # Regular text (not a thought, not a function call)
                    else:
                        accumulated_text += part.text
                        stream_chunk = StreamChunk(
                            chunk_type='text',
                            content=part.text,
                            is_complete=False
                        )
                        if on_chunk:
                            on_chunk(stream_chunk)
                        yield stream_chunk
            
            latency = time.time() - start_time
            
            # Try to get token counts from the last chunk
            prompt_tokens = self._estimate_tokens(prompt)
            completion_tokens = self._estimate_tokens(accumulated_text)
            thinking_tokens = self._estimate_tokens(accumulated_thoughts)
            total_tokens = prompt_tokens + completion_tokens + thinking_tokens
            
            # Calculate cost
            cost = ((prompt_tokens + thinking_tokens) / 1000 * 0.00001875) + (completion_tokens / 1000 * 0.000075)
            
            # Build final response
            final_response = LLMResponse(
                success=True,
                content=accumulated_text,
                tool_calls=tool_calls,
                model=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                thinking_tokens=thinking_tokens,
                total_tokens=total_tokens,
                latency_seconds=latency,
                finish_reason=finish_reason
            )
            
            self.stats.add_request(final_response, cost)
            
            if finish_reason and "STOP" not in finish_reason:
                logger.warning(f"Gemini stream finish_reason={finish_reason}")
            logger.info(f"✅ Stream complete: {completion_tokens} tokens (+{thinking_tokens} thinking), {latency:.2f}s")
            if tool_calls:
                logger.info(f"   🔧 {len(tool_calls)} tool call(s)")
            
            # Send completion chunk
            done_chunk = StreamChunk(
                chunk_type='done',
                is_complete=True
            )
            if on_chunk:
                on_chunk(done_chunk)
            yield done_chunk
            
            return final_response
            
        except Exception as e:
            latency = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"❌ Streaming error: {error_msg}")
            
            error_response = LLMResponse(
                success=False,
                error=error_msg,
                model=self.model,
                latency_seconds=latency
            )
            
            self.stats.add_request(error_response, 0.0)
            return error_response
    
    def generate_with_retry(self, 
                           prompt: str, 
                           max_retries: int = 3,
                           retry_delay: float = 1.0,
                           **kwargs) -> LLMResponse:
        """
        Generate with automatic retry on failure.
        
        Args:
            prompt: Prompt text
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries (seconds)
            **kwargs: Generation parameters
            
        Returns:
            LLMResponse object
        """
        for attempt in range(max_retries):
            response = self.generate(prompt, **kwargs)
            
            if response.success:
                return response
            
            if attempt < max_retries - 1:
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
        
        return response


def create_llm_client(provider: str = "gemini", **kwargs) -> LLMClient:
    """
    Factory function to create LLM client.
    
    Args:
        provider: Provider name ("gemini", "openai", etc.)
        **kwargs: Provider-specific configuration
        
    Returns:
        LLMClient instance
    """
    if provider.lower() == "gemini":
        return GeminiClient(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")
