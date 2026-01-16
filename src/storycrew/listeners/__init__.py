"""CrewAI Event Listeners for StoryCrew.

This package contains custom event listeners that hook into CrewAI's
event system to provide logging, monitoring, and integration capabilities.

To activate listeners, simply import this package in your main application:

    import storycrew.listeners

The listener instances are created at module import time, ensuring they
are registered with the CrewAI event bus.
"""

from .llm_logging_listener import llm_logging_listener

__all__ = ["llm_logging_listener"]
