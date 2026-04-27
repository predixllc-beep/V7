import logging
import traceback
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from core.events.event_bus import EventBus

class BaseEventAgent(ABC):
    """
    Event-driven Base Agent.
    Enforces separated concerns, fault tolerance, and observability.
    """
    def __init__(self, name: str, role: str, event_bus: EventBus):
        self.name = name
        self.role = role
        self.event_bus = event_bus
        self.logger = logging.getLogger(f"agent.{name.lower()}")
        self._memory = {}

    async def handle_event(self, event_payload: Dict[str, Any]):
        """
        Standardized entrypoint with fault tolerance and telemetry.
        """
        try:
            # Observability: Agent starts thinking
            await self.publish_telemetry("started_thinking", event_payload)
            
            result = await self.process(event_payload)
            
            # Observability: Agent finished successfully
            await self.publish_telemetry("finished_thinking", {"result": result})
            
            return result
        except Exception as e:
            self.logger.exception(f"[{self.name}] Error handling event.")
            await self.publish_telemetry("error", {"error": str(e), "trace": traceback.format_exc()})
            await self.fallback(event_payload, e)

    @abstractmethod
    async def process(self, payload: Dict[str, Any]) -> Any:
        """Core logic to be implemented by subclass."""
        pass

    async def fallback(self, payload: Dict[str, Any], error: Exception):
        """Fallback logic if processing fails. Can be overridden."""
        self.logger.warning(f"[{self.name}] using default fallback for payload.")

    async def publish_telemetry(self, action: str, data: Dict[str, Any]):
        """Push internal state to observatory."""
        if hasattr(self, 'event_bus') and self.event_bus:
            payload = {
                "agent": self.name,
                "role": self.role,
                "action": action,
                "data": data
            }
            await self.event_bus.publish("telemetry.agent", payload)
