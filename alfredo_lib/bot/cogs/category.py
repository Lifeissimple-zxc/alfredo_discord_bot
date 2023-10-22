"""
Module implements category-related commands for alfredo
"""
import logging

from discord.ext import commands

from alfredo_lib import ADMINS, COMMANDS_METADATA, MAIN_CFG
from alfredo_lib.alfredo_deps import cache, google_sheets_gateway, validator
from alfredo_lib.bot import ex
from alfredo_lib.bot.cogs.base import base_cog, helpers

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

    @commands.command(**COMMANDS_METADATA["get_categories"])
    async def get_categories(self, ctx: commands.Context) -> tuple:
        """
        Fetches available categories to show to the user
        """
        bot_logger.debug("Command invoked")
        categories, e = self.lc.get_categories(
            parse_mode=cache.ROW_PARSE_MODE_STRING
        )
        if e is not None:
            await ctx.author.send(
                f"Error reading categories from the database: {e}"
            )
            return
        await ctx.author.send(f"Categories available:\n{categories}")
        

    @commands.command(**COMMANDS_METADATA["create_category"])
    @helpers.admin_command(admin_ids=ADMINS, logger=bot_logger)
    async def create_category(self, ctx: commands.Context) -> tuple:
        """
        Creates a new category for transactions. Admin only.
        """
        bot_logger.debug("Command invoked")
        category_data = await self.get_input(
            ctx=ctx, command=COMMANDS_METADATA["create_category"]["name"],
            model="category", rec_discord_id=False,
            include_extra=False
        )
        bot_logger.debug("Transaction data prepared: %s", category_data)
        msg, e = self.lc.create_category(category_data=category_data)
        if e is not None:
            bot_logger.error("create_category() failed: %s", e)
        await ctx.author.send(msg)

    @commands.command(**COMMANDS_METADATA["update_category"])
    @helpers.admin_command(admin_ids=ADMINS, logger=bot_logger)
    async def update_category(self, ctx: commands.Context, category_id: int,
                              field: str, data: str) -> tuple:
        """
        Updates category data
        """
        bot_logger.debug("Command invoked")
        allowed_fields = self.ic.create_prompt_keys(model="category",
                                                    mode="all")
        if field not in allowed_fields and field is not None:
            raise ex.WrongUpdateFieldInputError(
                f"{field} can't be updated by users"
            )
        #TODO not doing data validation till we pass MVP stage of the project
        update = {field: data}
        e = self.lc.update_category(category_id=category_id, update=update)
        if e is not None:
            msg = f"DB Data update failed for category: {e}"
            bot_logger.error(msg)
            await ctx.author.send(msg)
        await ctx.author.send("Category data updated!")
        
    @commands.command(**COMMANDS_METADATA["delete_category"])
    @helpers.admin_command(admin_ids=ADMINS, logger=bot_logger)
    async def delete_category(self, ctx: commands.Context, category_id: int):
        """
        Deletes category with the given id
        """
        bot_logger.debug("Command invoked")
        category = self.lc._fetch_category(category_id=category_id)
        if category is None:
            await ctx.author.send(
                f"Category with {category_id} does not exist!"
            )
            return
        e = self.lc.delete_row(row_struct=category)
        if e is not None:
            msg = f"Error deleting category row: {e}"
            bot_logger.error(msg)
            await ctx.author.send(msg)
            return
        await ctx.author.send("Category deletion - success!")
