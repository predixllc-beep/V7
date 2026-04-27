import uuid
from typing import Dict, Any

from agents.base import BaseEventAgent
from core.events.schemas import SignalEvent

class SignalAgent(BaseEventAgent):
    """
    Consumes market data and produces SignalEvents.
    Responsible ONLY for analyzing the market and providing directional signals.
    """
    def __init__(self, name: str, provider, event_bus):
        super().__init__(name=name, role="SIGNAL", event_bus=event_bus)
        self.provider = provider
    
    async def process(self, payload: Dict[str, Any]):
        """
        payload is expected to be MarketData Event
        """
        trace_id = payload.get("trace_id", str(uuid.uuid4()))
        market_state = payload.get("state", {})
        symbol = payload.get("symbol", "UNKNOWN")
        
        self.logger.info(f"[{self.name}] Analyzing market state for {symbol}...")
        
        # Simplified LLM/Provider call (simulated intelligence)
        # In actual implementation: result = await self.provider.invoke(...)
        prompt = f"Analyze {symbol} given state: {market_state}. Return JSON with confidence, direction, reasoning."
        
        # Simulation for refactored architecture
        response_data = {
            "confidence": 0.85,
            "direction": "LONG",
            "reasoning": "Strong bullish divergence."
        }
        
        signal = SignalEvent(
            trace_id=trace_id,
            agent_id=self.name,
            symbol=symbol,
            confidence=response_data["confidence"],
            direction=response_data["direction"],
            reasoning=response_data["reasoning"]
        )
        
        # Output is returned to the CREW layer for consensus
        await self.event_bus.publish("crew.results", signal.model_dump())
        return signal

    async def start(self):
        self.event_bus.subscribe("agent.signal.analyze", self.handle_event)
