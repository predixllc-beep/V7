import logging
import uuid
from typing import Dict, Any

from agents.base import BaseEventAgent
from core.events.schemas import ExecutionEvent

# Assuming a HummingbotBridge will be passed or accessible
class ExecutionAgent(BaseEventAgent):
    """
    Consumes Decisions and produces Execution Events / Interacts with Bridge.
    Responsible exclusively for order routing, execution, and fill tracking.
    """
    def __init__(self, name: str, event_bus, hummingbot_bridge):
        super().__init__(name=name, role="EXECUTION", event_bus=event_bus)
        self.bridge = hummingbot_bridge
        self.fallback_exchanges = ["bybit", "okx"]

    async def process(self, payload: Dict[str, Any]):
        """
        payload is expected to be a DecisionEvent
        """
        trace_id = payload.get("trace_id", str(uuid.uuid4()))
        approved = payload.get("approved", False)
        symbol = payload.get("symbol", "UNKNOWN")
        
        if not approved:
            self.logger.info(f"[{self.name}] Decision not approved, ignoring.")
            return

        amount = payload.get("amount_usd", 0)
        # Parse reasoning to get original direction for side
        reasoning = payload.get("reasoning", "")
        side = "BUY" if "LONG" in reasoning else "SELL"

        self.logger.info(f"[{self.name}] Dispatching approved order for {symbol} = {amount} USD, side: {side}")
        
        # Dispatch to Hummingbot bridge with failover logic
        primary_exchange = "binance"
        bridge_result = await self._attempt_execution(symbol, amount, side, primary_exchange)
        
        if not bridge_result.get("success"):
            self.logger.warning(f"[{self.name}] Execution on {primary_exchange} failed. Attempting failover...")
            for fallback in self.fallback_exchanges:
                self.logger.info(f"[{self.name}] Trying failover exchange: {fallback}")
                bridge_result = await self._attempt_execution(symbol, amount, side, fallback)
                if bridge_result.get("success"):
                    break

        status = "FILLED" if bridge_result.get("success") else "FAILED"
        
        execution_event = ExecutionEvent(
            trace_id=trace_id,
            decision_id=str(payload.get("signal_id", "unknown")),
            exchange=bridge_result.get("exchange", "hummingbot_gateway"),
            symbol=symbol,
            order_type="MARKET",
            side=side,
            amount=amount,
            status=status
        )

        await self.event_bus.publish("market.executions", execution_event.model_dump())
        return execution_event
        
    async def _attempt_execution(self, symbol: str, amount: float, side: str, exchange: str):
        try:
            return await self.bridge.place_order(
                symbol=symbol,
                side=side,
                amount=amount,
                exchange=exchange,
                order_type="MARKET"
            )
        except Exception as e:
            self.logger.error(f"Error executing on {exchange}: {e}")
            return {"success": False, "error": str(e), "exchange": exchange}

    async def start(self):
        self.event_bus.subscribe("trading.decisions", self.handle_event)
