import logging
import uuid
import asyncio
from typing import Dict, Any

logger = logging.getLogger("Dataclaw.CREW")

class CrewOrchestrator:
    """
    CREW Layer.
    Orchestrates agents, maintains state context.
    Receives normalized tasks from FREG, coordinates agent response,
    and publishes consolidated signals to the RISK GATE.
    """
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self._active_contexts = {}

    async def start(self):
        self.event_bus.subscribe("crew.tasks", self.handle_task)
        self.event_bus.subscribe("crew.results", self.handle_agent_result)
        logger.info("[CREW] Orchestrator online. Managing agent flows.")

    async def handle_task(self, task: Dict[str, Any]):
        """Dispatches tasks to the appropriate agents based on task type."""
        trace_id = task.get("trace_id")
        task_type = task.get("type")
        
        self._active_contexts[trace_id] = {
            "task": task,
            "results": [],
            "status": "pending"
        }

        if task_type == "market_tick":
            # Delegate analysis to Signal Agents
            logger.info(f"[CREW] Delegating market analysis for {task.get('symbol')} to Signal agents.")
            await self.event_bus.publish("agent.signal.analyze", task)
        elif task_type == "external_signal":
            # Pass directly after validation to consensus
            logger.info(f"[CREW] Processing external signal for {task.get('symbol')} from {task.get('source')}.")
            await self.finalize_consensus(trace_id, [{
                "confidence": task.get("confidence"),
                "direction": task.get("direction"),
                "reasoning": f"External signal from {task.get('source')}"
            }])
        else:
            logger.warning(f"[CREW] Unknown task type: {task_type}")

    async def handle_agent_result(self, result: Dict[str, Any]):
        """Collects results from agents."""
        trace_id = result.get("trace_id")
        if trace_id in self._active_contexts:
            self._active_contexts[trace_id]["results"].append(result)
            
            # Simple aggregation logic: wait for 1 result for now
            # In advanced crew setups, wait for quorum or time threshold
            if len(self._active_contexts[trace_id]["results"]) >= 1:
                await self.finalize_consensus(trace_id, self._active_contexts[trace_id]["results"])

    async def finalize_consensus(self, trace_id: str, results: list):
        """Consolidates agent results and publishes to RISK GATE."""
        context = self._active_contexts.pop(trace_id, None)
        if not context:
            return

        task = context["task"]
        symbol = task.get("symbol")
        
        # Taking the first result as the consensus for now
        consensus = results[0]
        confidence = consensus.get("confidence", 0.0)
        direction = consensus.get("direction", "NEUTRAL")
        reasoning = consensus.get("reasoning", "No reason provided")

        if confidence > 0.0 and direction != "NEUTRAL":
            logger.info(f"[CREW] Consensus reached for {symbol}: {direction} ({confidence}). Routing to RISK GATE.")
            
            # Construct standard SignalEvent dict
            signal_payload = {
                "trace_id": trace_id,
                "agent_id": "CREW_CONSENSUS",
                "symbol": symbol,
                "confidence": confidence,
                "direction": direction,
                "reasoning": reasoning,
                "timestamp": task.get("timestamp") # allow risk dedup
            }
            # Route to RISK GATE
            await self.event_bus.publish("market.signals", signal_payload)
        else:
            logger.info(f"[CREW] Consensus for {symbol} is HOLD/NEUTRAL. Dropping.")

