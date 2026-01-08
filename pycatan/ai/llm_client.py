"""
LLM Client for AI Agents.

This module provides abstraction for different LLM providers.
Currently supports:
- Google Gemini
"""

import logging
import time
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM API call."""
    success: bool
    content: Optional[str] = None
    raw_response: Optional[Any] = None
    error: Optional[str] = None
    
    # Metadata
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    thinking_tokens: int = 0  # For thinking mode
    total_tokens: int = 0
    latency_seconds: float = 0.0
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
            
        return {
            "success": self.success,
            "content": self.content[:200] + "..." if self.content and len(self.content) > 200 else self.content,
            "error": self.error,
            "model": self.model,
            "tokens": tokens_dict,
            "latency_seconds": round(self.latency_seconds, 2),
            "timestamp": self.timestamp
        }


@dataclass
class LLMStats:
    """Statistics for LLM usage."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful": self.successful_requests,
            "failed": self.failed_requests,
            "success_rate": f"{self.successful_requests / self.total_requests * 100:.1f}%" if self.total_requests > 0 else "0%",
            "total_tokens": self.total_tokens,
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
    
    Supports Gemini models through the Google Generative AI API.
    """
    
    def __init__(self, 
                 model: str = "models/gemini-2.5-flash",
                 api_key: str = "",
                 temperature: float = 0.7,
                 max_tokens: Optional[int] = None,
                 response_format: str = "json",
                 **kwargs):
        """
        Initialize Gemini client.
        
        Args:
            model: Model name (e.g., "models/gemini-2.5-flash")
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
        
        # Initialize Gemini client
        try:
            import google.generativeai as genai
            self.genai = genai
            self.genai.configure(api_key=api_key)
            self.model_instance = genai.GenerativeModel(model)
            logger.info(f"Initialized Gemini client with model: {model}")
        except ImportError:
            logger.error("google-generativeai package not installed. Install with: pip install google-generativeai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
    
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate response from Gemini.
        
        Args:
            prompt: Prompt text (can be JSON string or plain text)
            **kwargs: Override default generation parameters
                     - response_schema: JSON schema to enforce structure
                     - enable_thinking: Enable thinking mode
                     - thinking_budget: Max tokens for thinking
            
        Returns:
            LLMResponse object with result
        """
        start_time = time.time()
        
        # Prepare generation config
        generation_config = {
            "temperature": kwargs.get("temperature", self.temperature),
        }
        
        if self.max_tokens:
            generation_config["max_output_tokens"] = kwargs.get("max_tokens", self.max_tokens)
        
        # Thinking mode (Gemini 2.0+)
        if kwargs.get("enable_thinking", False):
            generation_config["thinking_config"] = {
                "thinking_budget": kwargs.get("thinking_budget", 16000)
            }
        
        # Set response format
        response_format = kwargs.get("response_format", self.response_format)
        if response_format == "json":
            generation_config["response_mime_type"] = "application/json"
            
            # Add response_schema if provided (enforces structure)
            if "response_schema" in kwargs:
                # NOTE: propertyOrdering works in AI Studio but NOT in Python SDK
                # We need to remove it for the SDK to accept the schema
                schema = kwargs["response_schema"]
                cleaned_schema = self._remove_unsupported_fields(schema)
                generation_config["response_schema"] = cleaned_schema
        
        try:
            logger.info(f"Sending request to Gemini ({self.model})...")
            logger.debug(f"Prompt length: {len(prompt)} chars")
            
            # Generate response
            response = self.model_instance.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            latency = time.time() - start_time
            
            # Extract content
            content = response.text
            
            # Token counting
            # Try to get actual usage from response, fall back to estimation
            thinking_tokens = 0
            try:
                if hasattr(response, 'usage_metadata'):
                    prompt_tokens = response.usage_metadata.prompt_token_count
                    completion_tokens = response.usage_metadata.candidates_token_count
                    total_tokens = response.usage_metadata.total_token_count
                    
                    # Extract thinking tokens if available (Gemini 2.0 thinking mode)
                    if hasattr(response.usage_metadata, 'thoughts_token_count'):
                        thinking_tokens = response.usage_metadata.thoughts_token_count
                    
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
                model=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                thinking_tokens=thinking_tokens,
                total_tokens=total_tokens,
                latency_seconds=latency
            )
            
            self.stats.add_request(llm_response, cost)
            
            if thinking_tokens > 0:
                logger.info(f"✅ Response received: {completion_tokens} tokens (+{thinking_tokens} thinking), {latency:.2f}s")
            else:
                logger.info(f"✅ Response received: {completion_tokens} tokens, {latency:.2f}s")
            logger.debug(f"Response preview: {content[:100]}...")
            
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
