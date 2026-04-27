import logging
import uuid
from typing import Dict, Any

logger = logging.getLogger("Dataclaw.FREG")

class FregRouter:
    """
    FREG Layer (Frontend / Rule Engine Gateway).
    Responsible ONLY for input validation, signal normalization 
    and routing to the CREW layer.
    """
    def __init__(self, event_bus):
        self.event_bus = event_bus

    async def start(self):
        self.event_bus.subscribe("market.data", self.handle_market_data)
        self.event_bus.subscribe("external.signal", self.handle_external_signal)
        logger.info("[FREG] Online. Validating and routing inputs.")

    async def handle_market_data(self, payload: Dict[str, Any]):
        """Normalize market tick data and route to crew."""
        trace_id = payload.get("trace_id", str(uuid.uuid4()))
        if "symbol" not in payload:
            logger.warning("[FREG] Invalid market data dropped: missing symbol.")
            return

        normalized = {
            "trace_id": trace_id,
            "type": "market_tick",
            "symbol": payload["symbol"],
            "price": payload.get("price", 0.0),
            "state": payload.get("state", {}),
            "source": payload.get("exchange", "unknown")
        }
        await self.event_bus.publish("crew.tasks", normalized)

    async def handle_external_signal(self, payload: Dict[str, Any]):
        """Normalize external strategy signals (e.g., Freqtrade) and route to crew."""
        trace_id = payload.get("trace_id", str(uuid.uuid4()))
        symbol = payload.get("symbol")
        direction = payload.get("direction")
        
        if not symbol or not direction:
            logger.warning("[FREG] Invalid external signal dropped.")
            return

        normalized = {
            "trace_id": trace_id,
            "type": "external_signal",
            "symbol": symbol,
            "direction": direction,
            "confidence": payload.get("confidence", 0.5),
            "source": payload.get("source", "freqtrade")
        }
        await self.event_bus.publish("crew.tasks", normalized)
