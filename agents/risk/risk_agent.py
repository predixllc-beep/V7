import uuid
import hashlib
from typing import Dict, Any

from agents.base import BaseEventAgent
from core.events.schemas import DecisionEvent

class RiskAgent(BaseEventAgent):
    """
    Consumes Signals and produces Decisions.
    Responsible for validating confidence thresholds, position sizing, and leverage.
    Implements Volatility Aware Sizing and Risk Kernel Enforcement.
    """
    def __init__(self, name: str, event_bus):
        super().__init__(name=name, role="RISK", event_bus=event_bus)
        self.min_confidence = 0.70
        self.max_leverage = 5.0
        self.max_usd_position = 1000.0
        self._processed_signals = set()
        
    def dedup_signal(self, symbol: str, direction: str, timebucket: str) -> bool:
        """Signal dedup: hash(symbol+direction+timebucket)"""
        sig_hash = hashlib.sha256(f"{symbol}:{direction}:{timebucket}".encode()).hexdigest()
        if sig_hash in self._processed_signals:
            return False
        self._processed_signals.add(sig_hash)
        return True

    def calculate_dynamic_leverage(self, confidence: float, volatility: float) -> float:
        """Dynamic leverage based on volatility and confidence"""
        base_lev = 1.0 + (confidence - self.min_confidence) * 10
        # Reduce leverage if volatility is high
        volatility_penalty = max(1.0, volatility * 100) # Example scaling
        lev = base_lev / volatility_penalty
        return min(max(lev, 1.0), self.max_leverage)

    def calculate_var_sizing(self, confidence: float, volatility: float) -> float:
        """Value at Risk (VaR) position sizing"""
        # simplified VaR size scaling
        size = self.max_usd_position * confidence
        if volatility > 0.05:
            size *= 0.5 # slash size in high vol
        return size

    async def process(self, payload: Dict[str, Any]):
        """
        payload is expected to be a SignalEvent
        """
        trace_id = payload.get("trace_id", str(uuid.uuid4()))
        confidence = payload.get("confidence", 0.0)
        direction = payload.get("direction", "NEUTRAL")
        symbol = payload.get("symbol", "UNKNOWN")
        volatility = payload.get("market_volatility", 0.02) # from enriched signal
        timebucket = payload.get("timestamp", "0000")[:13] # truncate to hour

        if not self.dedup_signal(symbol, direction, timebucket):
            self.logger.warning(f"[{self.name}] Duplicate signal rejected: {symbol} {direction}")
            return None

        approved = False
        reasoning = "Neutral signal or below confidence threshold."
        leverage = 1.0
        amount_usd = 0.0

        if confidence >= self.min_confidence and direction in ["LONG", "SHORT"]:
            approved = True
            leverage = self.calculate_dynamic_leverage(confidence, volatility)
            amount_usd = self.calculate_var_sizing(confidence, volatility)
            reasoning = f"Approved {direction} with {confidence:.2f} conf, {leverage:.2f}x lev, {amount_usd:.2f} USD size (VaR)."
            
            # Kill switch check
            if volatility > 0.15: # 15% extreme vol
                approved = False
                reasoning = "VETO: Extreme volatility kill switch engaged."

        decision = DecisionEvent(
            trace_id=trace_id,
            signal_id=payload.get("agent_id", "unknown_signal"),
            symbol=symbol,
            approved=approved,
            risk_score=volatility * 10, # proxy risk score
            leverage=leverage,
            amount_usd=amount_usd,
            reasoning=reasoning
        )

        await self.event_bus.publish("trading.decisions", decision.model_dump())
        return decision

    async def start(self):
        self.event_bus.subscribe("market.signals", self.handle_event)
