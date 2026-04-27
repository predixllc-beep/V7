import logging
import asyncio
import aiohttp
from typing import Dict, Any

logger = logging.getLogger("hummingbot_bridge")

class HummingbotBridge:
    """
    Adapter layer connecting Dataclaw Intelligence to Hummingbot Gateway / Client logic.
    Handles signal-to-order translation, execution, and feedback tracking.
    """
    def __init__(self, api_url: str = "http://localhost:16422"):
        self.api_url = api_url
        self.session = None
        self._circuit_breaker_open = False
        self._failures = 0

    async def connect(self):
        """Initialize HTTP session for gateway"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        logger.info(f"Connected to Hummingbot Bridge at {self.api_url}")

    async def disconnect(self):
        if self.session:
            await self.session.close()

    async def place_order(self, symbol: str, side: str, amount: float, exchange: str = "binance", order_type: str = "MARKET") -> Dict[str, Any]:
        """
        Sends an order payload to Hummingbot gateway endpoints.
        """
        if self._circuit_breaker_open:
            logger.warning("Circuit breaker OPEN. Dropping order execution.")
            return {"success": False, "error": "CircuitBreakerOpen", "exchange": exchange}

        logger.info(f"[{side}] order requested via Hummingbot on {symbol} for {amount} on {exchange}")
        
        payload = {
            "chain": "ethereum",  # or dynamically derived
            "network": "mainnet", # or dynamically derived
            "connector": exchange,
            "tradingPair": symbol,
            "side": side.upper(),
            "amount": str(amount),
            "type": order_type.upper()
        }

        try:
            # Assuming /amms/trade for DEX or custom script endpoint for CEX via Gateway
            # We use a 5-second timeout for rapid failover
            timeout = aiohttp.ClientTimeout(total=5)
            async with self.session.post(f"{self.api_url}/amms/trade", json=payload, timeout=timeout) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    self._reset_circuit()
                    return {
                        "success": True,
                        "exchange": exchange,
                        "tx_hash": data.get("txHash", "unknown_tx"),
                        "raw_response": data
                    }
                else:
                    err_text = await response.text()
                    logger.error(f"Hummingbot error status {response.status}: {err_text}")
                    self._record_failure()
                    return {"success": False, "error": f"HTTP {response.status}", "exchange": exchange}

        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to Hummingbot for {exchange}")
            self._record_failure()
            return {"success": False, "error": "TimeoutError", "exchange": exchange}
        except Exception as e:
            logger.error(f"Hummingbot Bridge execution failed: {e}")
            self._record_failure()
            return {"success": False, "error": str(e), "exchange": exchange}

    def _record_failure(self):
        self._failures += 1
        if self._failures >= 3:
            self._circuit_breaker_open = True
            logger.error("CIRCUIT BREAKER OPENED due to multiple Hummingbot failures.")
            # Trigger auto-reset in background
            asyncio.create_task(self._reset_circuit_delayed())

    async def _reset_circuit_delayed(self):
        await asyncio.sleep(60) # Wait 60s before trying again
        self._circuit_breaker_open = False
        self._failures = 0
        logger.info("Circuit breaker auto-reset. System accepting orders again.")

    def _reset_circuit(self):
        self._circuit_breaker_open = False
        self._failures = 0
