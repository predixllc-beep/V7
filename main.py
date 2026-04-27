import logging
import sys
import asyncio

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("Dataclaw.Main")

# Import new event-driven framework
from core.events.event_bus import EventBus
from core.freg.freg_router import FregRouter
from core.crew.crew_orchestrator import CrewOrchestrator
from agents.signal.signal_agent import SignalAgent
from agents.risk.risk_agent import RiskAgent
from agents.execution.execution_agent import ExecutionAgent
from agents.meta.meta_agent import MetaSupervisorAgent
from hummingbot_bridge.bridge import HummingbotBridge
from observability.observatory import AgentObservatory
from control_plane.admin import ControlTower

class DataclawOS:
    def __init__(self):
        logger.info("Initializing Dataclaw Autonomous Agent OS...")
        self.event_bus = EventBus()
        self.bridge = HummingbotBridge()
        self.observatory = AgentObservatory(self.event_bus)
        self.control_tower = ControlTower(self.event_bus)
        
        self.freg = FregRouter(self.event_bus)
        self.crew = CrewOrchestrator(self.event_bus)

        # Mock Provider
        mock_provider = type("MockProv", (), {"invoke": lambda self, x: "Mocked"})()

        # Initialize Swarm
        self.agents = {
            "signal": SignalAgent("MiroFish_Refactored", mock_provider, self.event_bus),
            "risk": RiskAgent("RiskGuardian", self.event_bus),
            "execution": ExecutionAgent("Executor_HB", self.event_bus, self.bridge),
            "meta": MetaSupervisorAgent("MetaOverlord", self.event_bus)
        }

    async def start(self):
        # Start core components
        await self.event_bus.start()
        await self.bridge.connect()
        await self.observatory.start()
        await self.control_tower.start()
        await self.freg.start()
        await self.crew.start()

        # Start agents (they subscribe to topics)
        for _, agent in self.agents.items():
            await agent.start()

        logger.info("Dataclaw OS Event-Driven Architecture actively monitoring...")

        try:
            # Simulate a market data feed event
            mock_market_data = {
                "symbol": "BTC/USDT",
                "exchange": "binance",
                "price": 94000.0,
                "volume": 1200.5,
                "state": {"trend": "bullish"}
            }
            
            # Publish initial event to trigger the cascade
            await self.event_bus.publish("market.data", mock_market_data)

            # Keep loop running
            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Asyncio loop cancelled.")
        except KeyboardInterrupt:
             logger.info("Shutting down Dataclaw OS.")
        except Exception as e:
             logger.error(f"Critical system failure: {e}")
             await self.control_tower.emergency_kill_switch()
        finally:
            await self.shutdown()

    async def shutdown(self):
        await self.event_bus.stop()
        await self.bridge.disconnect()
        logger.info("Shutdown complete.")

def run_system():
    os_sys = DataclawOS()
    try:
        asyncio.run(os_sys.start())
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    run_system()
