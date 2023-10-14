"""
Module implements category-related commands for alfredo
"""
import logging

import polars as pl
from discord.ext import commands

from alfredo_lib import ADMINS, MAIN_CFG
from alfredo_lib.alfredo_deps import cache, google_sheets_gateway, validator
from alfredo_lib.bot import ex
from alfredo_lib.bot.cogs.base import base_cog, helpers
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

    @commands.command(aliases=("new_cat",))
    @helpers.admin_command(admin_ids=ADMINS, logger=bot_logger,
                           command_name="create_category")
    async def create_category(self, ctx: commands.Context) -> tuple:
        """
        Creates a new category for transactions. Admin only.
        """
        category_data = await self.get_input(
            ctx=ctx, command="create_category",
            model="category", rec_discord_id=False,
            include_extra=False
        )
        bot_logger.debug("Transaction data prepared: %s", category_data)
        msg, e = self.lc.create_category(category_data=category_data)
        if e is not None:
            bot_logger.error("create_category() failed: %s", e)
        await ctx.author.send(msg)
        