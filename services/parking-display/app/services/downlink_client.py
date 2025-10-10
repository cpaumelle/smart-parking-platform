import httpx
import logging
from typing import Dict, Any
import asyncio
import time

logger = logging.getLogger("downlink-client")

class DownlinkClient:
    """HTTP client for sending downlinks via existing Downlink Service"""

    def __init__(self, base_url: str = None):
        import os
        self.base_url = base_url or os.getenv("DOWNLINK_SERVICE_URL", "http://parking-downlink:8000")
        self.timeout = 5.0
        self.max_retries = 2

    async def send_downlink(
        self,
        dev_eui: str,
        fport: int,
        data: str,
        confirmed: bool = False
    ) -> Dict[str, Any]:
        """
        Send downlink via existing Downlink Service

        Args:
            dev_eui: Device EUI of Class C display
            fport: LoRaWAN fPort (usually 1)
            data: Hex payload (e.g., "01" for FREE)
            confirmed: Request LoRaWAN confirmation

        Returns:
            {
                "success": bool,
                "error": str or None,
                "response_time_ms": float,
                "response": dict or None
            }
        """
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/downlink/send",
                        json={
                            "dev_eui": dev_eui,
                            "fport": fport,
                            "data": data,
                            "confirmed": confirmed
                        }
                    )

                    response_time = (time.time() - start_time) * 1000

                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"Downlink sent to {dev_eui}: {data} ({response_time:.1f}ms)")
                        return {
                            "success": True,
                            "error": None,
                            "response_time_ms": response_time,
                            "response": result
                        }
                    else:
                        error_msg = f"HTTP {response.status_code}: {response.text}"
                        if attempt < self.max_retries:
                            logger.warning(f"Downlink attempt {attempt + 1} failed to {dev_eui}: {error_msg}, retrying...")
                            await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                            continue
                        else:
                            logger.error(f"Downlink failed to {dev_eui} after {self.max_retries + 1} attempts: {error_msg}")
                            return {
                                "success": False,
                                "error": error_msg,
                                "response_time_ms": (time.time() - start_time) * 1000,
                                "response": None
                            }

            except asyncio.TimeoutError:
                error_msg = f"Timeout after {self.timeout}s"
                if attempt < self.max_retries:
                    logger.warning(f"Downlink timeout attempt {attempt + 1} to {dev_eui}, retrying...")
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    logger.error(f"Downlink timeout to {dev_eui} after {self.max_retries + 1} attempts")
                    return {
                        "success": False,
                        "error": error_msg,
                        "response_time_ms": (time.time() - start_time) * 1000,
                        "response": None
                    }
            except Exception as e:
                error_msg = f"Exception: {str(e)}"
                if attempt < self.max_retries:
                    logger.warning(f"Downlink exception attempt {attempt + 1} to {dev_eui}: {error_msg}, retrying...")
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    logger.error(f"Downlink exception to {dev_eui} after {self.max_retries + 1} attempts: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "response_time_ms": (time.time() - start_time) * 1000,
                        "response": None
                    }

        # Should never reach here
        return {
            "success": False,
            "error": "Unknown error",
            "response_time_ms": (time.time() - start_time) * 1000,
            "response": None
        }

    async def health_check(self) -> bool:
        """Check if downlink service is reachable"""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
