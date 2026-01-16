"""LLM Event Listener for logging all LLM calls.

This listener captures:
- Outgoing prompts (with token estimation)
- Incoming responses (with token usage from API)
- Failed LLM calls with error messages
"""

import logging
from typing import Any, List
from pydantic import BaseModel

from crewai.events import BaseEventListener, crewai_event_bus
from crewai.events.types.llm_events import (
    LLMCallStartedEvent,
    LLMCallCompletedEvent,
    LLMCallFailedEvent,
)

logger = logging.getLogger("StoryCrew")


class LLMLoggingListener(BaseEventListener):
    """Logs all LLM interactions including prompts, responses, and token usage.

    This listener hooks into CrewAI's event system to capture:
    - Every prompt sent to the LLM (with estimated token count)
    - Every response received (with actual token usage from API)
    - Any LLM call failures with error details

    The logged data is written to the StoryCrew logger and can be
    analyzed to optimize prompts, track costs, and debug issues.
    """

    def __init__(self):
        """Initialize the listener with counters for statistics."""
        super().__init__()
        self.call_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def setup_listeners(self, crewai_event_bus):
        """Register event handlers with the CrewAI event bus.

        Args:
            crewai_event_bus: The global CrewAI event bus
        """

        @crewai_event_bus.on(LLMCallStartedEvent)
        def on_llm_call_started(source, event: LLMCallStartedEvent):
            """Handler for LLM call started events.

            Logs the outgoing prompt (messages) with estimated token count.
            """
            self.call_count += 1

            logger.info("=" * 80)
            logger.info(f"[LLM EVENT] Call #{self.call_count} Started")
            logger.info(f"[LLM EVENT] Model: {event.model}")

            # Log task and agent info if available
            if hasattr(event, 'task_name'):
                logger.info(f"[LLM EVENT] Task: {event.task_name}")
            if hasattr(event, 'agent_role'):
                logger.info(f"[LLM EVENT] Agent: {event.agent_role}")

            # Log the prompt (messages)
            if event.messages:
                self._log_prompt_messages(event.messages)

        @crewai_event_bus.on(LLMCallCompletedEvent)
        def on_llm_call_completed(source, event: LLMCallCompletedEvent):
            """Handler for LLM call completed events.

            Logs the response content and actual token usage from the API.
            """
            logger.info(f"[LLM EVENT] Call #{self.call_count} Completed")
            logger.info(f"[LLM EVENT] Call Type: {event.call_type}")

            # Log the response and token usage
            self._log_response_with_tokens(event.response)

            logger.info("=" * 80)

        @crewai_event_bus.on(LLMCallFailedEvent)
        def on_llm_call_failed(source, event: LLMCallFailedEvent):
            """Handler for LLM call failed events.

            Logs error details when an LLM call fails.
            """
            logger.error("=" * 80)
            logger.error(f"[LLM EVENT] Call #{self.call_count} FAILED")
            logger.error(f"[LLM EVENT] Error: {event.error}")

            # Log task/agent context if available
            if hasattr(event, 'task_name'):
                logger.error(f"[LLM EVENT] Task: {event.task_name}")
            if hasattr(event, 'agent_role'):
                logger.error(f"[LLM EVENT] Agent: {event.agent_role}")

            logger.error("=" * 80)

    def _log_prompt_messages(self, messages):
        """Log prompt messages with token estimation.

        Args:
            messages: Either a string prompt or a list of message dicts
        """
        try:
            if isinstance(messages, str):
                # Simple string prompt
                token_count = self._estimate_tokens(messages)
                logger.info(f"[LLM PROMPT] 📤 Total ({token_count:,} tokens est.)")
                # Log first 2000 chars
                preview = messages[:2000]
                if len(messages) > 2000:
                    preview += f"... [truncated, total {len(messages)} chars]"
                logger.info(f"[LLM PROMPT] {preview}")

            elif isinstance(messages, list):
                # List of message dicts (standard OpenAI format)
                total_tokens = 0
                logger.info(f"[LLM PROMPT] 📤 Messages: {len(messages)} messages")

                for i, msg in enumerate(messages):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')

                    # Handle string content
                    if isinstance(content, str):
                        tokens = self._estimate_tokens(content)
                        total_tokens += tokens
                        logger.info(f"[LLM PROMPT] Message {i+1} [{role}] ({tokens:,} tokens est.):")

                        # Log first 1000 chars for preview
                        preview = content[:1000]
                        if len(content) > 1000:
                            preview += f"... [truncated, total {len(content)} chars]"
                        logger.info(f"[LLM PROMPT] {preview}")

                    # Handle multimodal content (text + images)
                    elif isinstance(content, list):
                        logger.info(f"[LLM PROMPT] Message {i+1} [{role}]: (multimodal content)")
                        for part in content:
                            if isinstance(part, dict):
                                if 'text' in part:
                                    text = part['text']
                                    tokens = self._estimate_tokens(text)
                                    total_tokens += tokens
                                    logger.info(f"[LLM PROMPT]   - Text ({tokens:,} tokens est.): {text[:500]}")
                                elif 'image_url' in part:
                                    logger.info(f"[LLM PROMPT]   - Image URL: {part['image_url'][:100]}")

                logger.info(f"[LLM PROMPT] 📊 Total Estimated Tokens: {total_tokens:,}")

            else:
                logger.warning(f"[LLM PROMPT] Unknown message format: {type(messages)}")

        except Exception as e:
            logger.error(f"[LLM PROMPT] Error logging prompt: {e}")

    def _log_response_with_tokens(self, response):
        """Log response content and extract token usage.

        Args:
            response: Response object (could be various types)
        """
        try:
            response_dict = None

            # Try to convert response to dict
            if hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
            elif hasattr(response, 'dict'):
                response_dict = response.dict()
            elif isinstance(response, dict):
                response_dict = response
            else:
                response_dict = {'raw': str(response)}

            # Extract and log token usage
            if isinstance(response_dict, dict) and 'usage' in response_dict:
                usage = response_dict['usage']
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)

                self.total_input_tokens += prompt_tokens
                self.total_output_tokens += completion_tokens

                logger.info(f"[LLM TOKENS] 📊 Actual Token Usage:")
                logger.info(f"[LLM TOKENS]   Input (prompt):  {prompt_tokens:,} tokens")
                logger.info(f"[LLM TOKENS]   Output (completion): {completion_tokens:,} tokens")
                logger.info(f"[LLM TOKENS]   Total: {total_tokens:,} tokens")

                # Calculate cost estimate
                input_cost = (prompt_tokens / 1_000_000) * 0.50
                output_cost = (completion_tokens / 1_000_000) * 1.50
                total_cost = input_cost + output_cost
                logger.info(f"[LLM TOKENS]   Est. Cost: ${total_cost:.4f}")
                logger.info(f"[LLM TOKENS] 📈 Cumulative: {self.total_input_tokens:,} in + {self.total_output_tokens:,} out = {self.total_input_tokens + self.total_output_tokens:,} total")

            # Extract and log response content
            content = None
            if isinstance(response_dict, dict):
                # OpenAI-style response with choices
                if 'choices' in response_dict and len(response_dict['choices']) > 0:
                    choice = response_dict['choices'][0]
                    if 'message' in choice:
                        content = choice['message'].get('content', '')
                    elif 'text' in choice:
                        content = choice['text']
                    else:
                        content = str(choice)

                # Direct content field
                elif 'content' in response_dict:
                    content = response_dict['content']

                # Fallback to raw response
                elif 'raw' in response_dict:
                    content = str(response_dict['raw'])

            if content:
                token_count = self._estimate_tokens(content)
                logger.info(f"[LLM RESPONSE] 📥 Response Content ({token_count:,} tokens est., {len(content):,} chars):")

                # Log first 3000 chars
                if len(content) > 3000:
                    logger.info(f"[LLM RESPONSE] {content[:3000]}... [truncated, total {len(content)} chars]")
                else:
                    logger.info(f"[LLM RESPONSE] {content}")

        except Exception as e:
            logger.error(f"[LLM RESPONSE] Error logging response: {e}")

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using character-based heuristics.

        Approximate: 1 token ≈ 4 characters for English, 2-3 characters for Chinese

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        # Count Chinese characters (Unicode range for CJK)
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # Count English characters and others
        other_chars = len(text) - chinese_chars

        # Rough estimate: Chinese ~2 chars/token, English ~4 chars/token
        estimated_tokens = (chinese_chars / 2) + (other_chars / 4)
        return int(estimated_tokens)


# Create an instance of the listener at module import time
# This ensures the listener is registered with the event bus
llm_logging_listener = LLMLoggingListener()
