"""
Module implements an async friendly rps limiter
"""
import asyncio
import time
from typing import Optional


class AsyncLimiter:
    """
    Async RPS limiter meant to be used as a context manager
    Usage:  limiter = AsyncLimiter(RPS, # of concurrent requests)
            async with limiter:
                # make request here.
    Actual RPS will be slightly lower than the theoretical RPS.
    """
    def __init__(self, rps: float, concurrent_requests: Optional[int] = None):
        """
        Instantiates the limiter
        """
        self.rps_lock = asyncio.Lock()
        self.interval_ms = 1000 / rps
        self.last_request_time = time.time() * 1000

        self.concurrency = False
        self.sem = None
        if concurrent_requests is not None:
            self.concurrency = True
            self.sem = asyncio.Semaphore(value=concurrent_requests)

    async def __aenter__(self):
        """
        Context manager entry
        """
        if self.concurrency:
            await self.sem.acquire()
        async with self.rps_lock:
            await asyncio.sleep(
                max(
                    0.,
                    self.interval_ms - ((time.time() * 1000) - self.last_request_time)  # noqa: E501
                ) / 1000
            )
            self.last_request_time = time.time() * 1000

    async def __aexit__(self, exc_type, exc, tb):
        """
        Context manager exit
        """
        if self.concurrency:
            self.sem.release()