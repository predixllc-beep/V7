import logging
from typing import Dict, Any

logger = logging.getLogger("observatory")

class AgentObservatory:
    """
    Consumes telemetry from EventBus and aggregates it for UI / Dashboards.
    Allows Control Tower to fetch live health metrics.
    Tracks: PnL, drift, model disagreement, reasoning, and alerts.
    """
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.agent_metrics = {}
        self.anomalies = []

    async def ingest_telemetry(self, payload: Dict[str, Any]):
        """Handler for telemetry events."""
        agent = payload.get("agent")
        action = payload.get("action")
        data = payload.get("data", {})
        
        if agent and agent not in self.agent_metrics:
            self.agent_metrics[agent] = {
                "starts": 0, "finishes": 0, "errors": 0,
                "confidence_history": [], "pnl": 0.0
            }

        if action == "started_thinking":
            self.agent_metrics[agent]["starts"] += 1
        elif action == "finished_thinking":
            self.agent_metrics[agent]["finishes"] += 1
            if "result" in data and hasattr(data["result"], "confidence"):
                conf = data["result"].confidence
                self.agent_metrics[agent]["confidence_history"].append(conf)
                if len(self.agent_metrics[agent]["confidence_history"]) > 10:
                    self.agent_metrics[agent]["confidence_history"].pop(0)
        elif action == "error":
            self.agent_metrics[agent]["errors"] += 1
            self.anomalies.append({"type": "agent_error", "agent": agent, "error": data.get("error")})
        elif action == "disagreement":
            self.anomalies.append({"type": "model_disagreement", "data": data})

        # Push to backend UI WebSocket or Redis (simulated via logger)
        logger.debug(f"[OBSERVATORY] Metrics updated: {agent} {action}")
        if self.anomalies:
            logger.warning(f"[OBSERVATORY ALERT] Anomalies detected: {self.anomalies[-1]}")

    async def start(self):
        self.event_bus.subscribe("telemetry.agent", self.ingest_telemetry)
        logger.info("Agent Observatory Started.")
