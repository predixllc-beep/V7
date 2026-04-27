from typing import Dict, Any, List
from agents.base import BaseEventAgent

class MetaSupervisorAgent(BaseEventAgent):
    """
    Subscribes to all major event streams and telemetry.
    Responsible for PnL attribution, dynamic scaling of risk, conflict resolution,
    and emergency kills.
    """
    def __init__(self, name: str, event_bus):
        super().__init__(name=name, role="META", event_bus=event_bus)
        self.agent_scores: Dict[str, float] = {}
        self.recent_signals: List[Dict[str, Any]] = []

    async def process(self, payload: Dict[str, Any]):
        action = payload.get("action")
        
        # Telemetry parsing
        if action:
            agent = payload.get("agent")
            data = payload.get("data", {})
            
            if action == "finished_thinking":
                # Check for conflicts
                result = data.get("result", {})
                if result and hasattr(result, "direction"):
                    await self.detect_conflict(agent, result)
            
            self.logger.debug(f"[META] Tracing {agent} - {action}")
            return
            
        # Execution status
        status = payload.get("status")
        if status:
            self.logger.info(f"[META] Monitored execution {status} for trace {payload.get('trace_id')}")
            # Learning loop: Update agent scores over time based on PNL (simulated here)
            if status == "FILLED":
                agent_id = payload.get("decision_id", "unknown")
                self.agent_scores[agent_id] = self.agent_scores.get(agent_id, 100.0) + 1.5
                self.logger.info(f"[META] Learning Loop: +1.5 points to {agent_id}. Total: {self.agent_scores[agent_id]}")

    async def detect_conflict(self, agent: str, signal_data: Any):
        """Conflict resolver across multiple signal agents"""
        self.recent_signals.append({"agent": agent, "dir": signal_data.direction, "symbol": signal_data.symbol})
        # Keep last 10
        if len(self.recent_signals) > 10:
            self.recent_signals.pop(0)
            
        sym = signal_data.symbol
        longs = sum(1 for s in self.recent_signals if s["symbol"] == sym and s["dir"] == "LONG")
        shorts = sum(1 for s in self.recent_signals if s["symbol"] == sym and s["dir"] == "SHORT")
        
        if longs > 0 and shorts > 0:
            self.logger.warning(f"[META] AGENT DISAGREEMENT on {sym}: {longs} LONG vs {shorts} SHORT")
            await self.publish_telemetry("disagreement", {"symbol": sym, "long_count": longs, "short_count": shorts})
            # Overriding risk parameters
            await self.event_bus.publish("admin.commands", {"command": "LOWER_LEVERAGE", "reason": "model_disagreement"})

    async def start(self):
        self.event_bus.subscribe("telemetry.agent", self.handle_event)
        self.event_bus.subscribe("market.executions", self.handle_event)
