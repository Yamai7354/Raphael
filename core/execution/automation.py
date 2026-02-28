import logging
import asyncio
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)


class TaskAutomator:
    """
    Wraps asynchronous callable operations with exponential backoff and retry logic.
    Ideal for remote API connections, scraping, or unstable hardware integrations.
    """

    def __init__(self, max_retries: int = 3, initial_delay: int = 1):
        self.max_retries = max_retries
        self.initial_delay = initial_delay

    async def execute_with_retry(
        self, operation: Callable[..., Any], *args, **kwargs
    ) -> Dict[str, Any]:
        """
        Executes an arbitrary function call. Caught exceptions spawn a retry delay
        equal to (delay * 2^attempt) before re-trying up to max_retries.
        """
        attempt = 0
        current_delay = self.initial_delay

        while attempt <= self.max_retries:
            try:
                logger.debug(
                    f"TaskAutomator launching operation '{operation.__name__}' -> Attempt {attempt}/{self.max_retries}"
                )
                # We expect the operations returning a standardized dict or raising
                result = await operation(*args, **kwargs)
                return result

            except Exception as e:
                attempt += 1
                if attempt > self.max_retries:
                    logger.critical(
                        f"TaskAutomator exhausted {self.max_retries} retries for '{operation.__name__}'. Failing definitively."
                    )
                    return {"error": str(e), "retries_exhausted": True}

                logger.warning(
                    f"TaskAutomator caught crash ({e}). Executing backoff wait {current_delay}s..."
                )
                await asyncio.sleep(current_delay)
                current_delay *= 2  # Exponential wait
