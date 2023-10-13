"""
Module implements category-related commands for alfredo
"""
import logging

import polars as pl
from discord.ext import commands

from alfredo_lib import MAIN_CFG
from alfredo_lib.alfredo_deps import cache, google_sheets_gateway, validator
from alfredo_lib.bot import ex
from alfredo_lib.bot.cogs.base import base_cog
from alfredo_lib.local_persistence import models

bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])

class CategoryCog(base_cog.CogHelper, name="category"):
    """Encapsulates commands related to categories"""

    def __init__(self, bot: commands.Bot,
                 local_cache: cache.Cache,
                 input_controller: validator.InputController,
                 sheets: google_sheets_gateway.GoogleSheetAsyncGateway):
        """
        Instantiates the class
        """
        super().__init__(bot=bot, local_cache=local_cache,
                         input_controller=input_controller,
                         sheets=sheets)

    @commands.command(alises=("get_cts",))
    async def get_categories(self, ctx: commands.Context) -> tuple:
        """
        Fetches available categories to show to the user
        """
        bot_logger.debug("Command invoked")
        try:
            categories, e = self.lc.get_categories(
                parse_mode=cache.ROW_PARSE_MODE_STRING
            )
            if e is not None:
                await ctx.author.send(
                    f"Error reading categories from the database: {e}"
                )
                return
            await ctx.author.send(f"Categories available:\n{categories}")
        except Exception as e:
            bot_logger.error("Error getting categories: %s", e)
        