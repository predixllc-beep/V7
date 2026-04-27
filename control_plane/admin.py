import logging
from typing import Dict, Any

logger = logging.getLogger("control_tower")

class ControlTower:
    """
    Exposes Administrative Commands: Kill Switches, Strategy Overrides, Config Hot-Reloads.
    Also handles module registries and system configs.
    """
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.system_active = True
        self.db_config = {}
        self.redis_config = {}
        self.model_registry = {}
        self.prompt_registry = {}
        self.exchange_manager = {}

    async def emergency_kill_switch(self):
        """
        Immediately pauses all Execution Agents and cancels pending orders on Hummingbot.
        """
        logger.warning("!!! EMERGENCY KILL SWITCH ACTIVATED !!!")
        self.system_active = False
        await self.event_bus.publish("admin.commands", {"command": "KILL_ALL_EXECUTION"})
        # In a full flow, the HummingbotBridge itself would also subscribe and cancel orders

    async def resume_system(self):
        logger.info("System Resumed by Control Tower.")
        self.system_active = True
        await self.event_bus.publish("admin.commands", {"command": "RESUME_EXECUTION"})

    async def strategy_tuning(self, strategy_id: str, params: Dict[str, Any]):
        """Live adjust strategy parameters"""
        logger.info(f"Tuning strategy {strategy_id} with {params}")
        await self.event_bus.publish("admin.commands", {"command": "TUNE_STRATEGY", "strategy": strategy_id, "params": params})

    async def _handle_admin_commands(self, payload: Dict[str, Any]):
        cmd = payload.get("command")
        if cmd == "ASSIGN_MODEL":
            agent_id = payload.get("agentId")
            model_id = payload.get("modelId")
            logger.info(f"[Control Tower] Re-assigning Model {model_id} to Agent {agent_id} without restarting.")
            # Mocking the inference client reload
            self.model_registry[agent_id] = model_id
            await self.event_bus.publish("telemetry.agent", {
                "agent": agent_id,
                "action": "model_reloaded",
                "data": {"new_model": model_id}
            })

    async def start(self):
        logger.info("Control Tower Online.")
        self.event_bus.subscribe("admin.commands", self._handle_admin_commands)
