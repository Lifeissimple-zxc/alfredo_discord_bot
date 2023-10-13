"""
Module implements miscellaneous helpers used by bot commands
"""
import functools
import logging
from typing import Callable, Sequence

from discord.ext import commands


class ContextMissingError(Exception):
    """
    Custom exception for scenarios where ctx is not in kwargs
    """
    pass


def _args_contain_ctx(args: Sequence):
    """
    Locates context in args if there is one, otherwise returns a None
    """
    for a in args:
        if isinstance(a, commands.Context):
            return a

def admin_command(admin_ids: set, logger: logging.Logger,
                  command_name: str):
    """
    Restricts command uses to admin_ids by raising exc_to_trigger
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # get admin from ctx arg (ctx.author.id)
            if (ctx := _args_contain_ctx(args)) is None:
                e = ContextMissingError("ctx arg not found")
                logger.error(e)
                raise e
            logger.debug("Found context in args")
            if ctx.author.id not in admin_ids:
                logger.warning("User %s tried calling %s w/o admin rights",
                               ctx.author.id, command_name)
                raise Exception("Test ERror to see that the decorator works")
            logger.debug("Checked author for being an admin, running %s",
                         command_name)
            return await func(*args, **kwargs)
        return wrapper
    return decorator   
            