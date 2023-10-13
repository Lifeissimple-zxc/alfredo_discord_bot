"""
Module implements a simple async-friendly retry decorator
"""
import asyncio
import functools
import logging
from typing import Callable, Sequence


def simple_async_retry(exceptions: Sequence, logger: logging.Logger,
                       retries: int, delay: int):
    """
    Retries retries number of times with delay on exceptions
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(retries+1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    logger.debug("Caught an exception: %s", e)
                    if attempt < retries:
                        logger.debug("Retrying in %s seconds...", delay)
                        await asyncio.sleep(delay)
                    else:
                        logger.warning("Retries exhausted. Raising err")
                        raise e
        return wrapper
    return decorator

                        
