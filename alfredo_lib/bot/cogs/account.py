"""
Module implements account-realted commands for alfredo
"""
import logging
from typing import Optional

from discord.ext import commands

from alfredo_lib import COMMANDS_METADATA, MAIN_CFG
from alfredo_lib.alfredo_deps import cache, google_sheets_gateway, validator
from alfredo_lib.bot import ex
from alfredo_lib.bot.cogs.base import base_cog

bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])

class AccountCog(base_cog.CogHelper, name=MAIN_CFG["cog_names"]["account"]):
    """Encapsulates commands related to user accounts"""

    def __init__(self, bot: commands.Bot,
                 local_cache: cache.Cache,
                 input_controller: validator.InputController,
                 sheets: google_sheets_gateway.GoogleSheetAsyncGateway):
        """
        Instantiates account cog
        """
        super().__init__(bot=bot, local_cache=local_cache,
                         input_controller=input_controller,
                         sheets=sheets)

    async def _register(self, ctx: commands.Context):
        """
        Actual register implementation
        """
        command = COMMANDS_METADATA["register"]["name"]
        user, _ = self.lc.get_user(discord_id=ctx.author.id)
        if user is not None:
            await ctx.message.author.send("You are already registered")
            return

        reg_data = await self.get_input(ctx=ctx, command=command,
                                        model="user", include_extra=True)
        # TODO Exception uncaught here
        missing = self.ic.validate_keys(user_input=reg_data, model="user")
        if missing:
            await ctx.message.author.send(
                f"Cannot run {command}. Missing fields: {missing}"
            )
            return
        await ctx.message.author.send(f"All fields are present. Running {command}.")

        user_msg, e = self.lc.create_user(reg_data)
        username = reg_data["username"]
        if e is not None:
            await ctx.message.author.send(
                f"{command} failed for {username}: {user_msg}"
            )
            return
        await ctx.message.author.send(
            f"User {username} registered with discord_id {reg_data['discord_id']}"
        )
    
    @commands.command(**COMMANDS_METADATA["register"])
    async def register(self, ctx: commands.Context):
        """Performs User registration"""
        await self._register(ctx=ctx)
        

    @commands.command(**COMMANDS_METADATA["prepare_sheet"])
    async def prepare_sheet(self, ctx: commands.Context):
        """Prepares sheet for alfredo"""
        bot_logger.debug("User %s invoked %s command",
                         ctx.author.id, COMMANDS_METADATA["prepare_sheet"]["name"])
        user_data, user_msg = self.lc.get_user(discord_id=ctx.author.id)
        if user_msg is not None:
            raise ex.UserNotRegisteredError(msg=user_msg)
        sheet_id = user_data.spreadsheet
        bot_logger.debug("Preparing sheet %s for user %s",
                         sheet_id, ctx.author.id)
        e = await self._prepare_sheet(sheet_id=sheet_id)
        # Quick check for success to avoid indenting code
        if e is None:
            await ctx.message.author.send("Sheet preparation - ok!")
            return
        bot_logger.error("Error preparing sheet %s: %s", sheet_id, e)
        await ctx.message.author.send(
            f"Error when preparing sheet: {e}"
        )
        
    @commands.command(**COMMANDS_METADATA["whoami"])
    async def whoami(self, ctx: commands.Context):
        """Shows account data if a user is registered"""
        bot_logger.debug("User %s invoked %s command",
                         ctx.author.id, COMMANDS_METADATA["whoami"]["name"])
        user_data, user_msg = self.lc.get_user(
            discord_id=ctx.author.id, parse_mode=cache.ROW_PARSE_MODE_STRING
        )
        if user_msg is not None:
            raise ex.UserNotRegisteredError(msg=user_msg)
        await ctx.message.author.send(f"Your data:\n{user_data}")
    
    @commands.command(**COMMANDS_METADATA["update_user_data"])
    async def update_user_data(self,
                               ctx: commands.Context,
                               field: Optional[str] = None,
                               data: Optional[str] = None):
        """
        Updates user data
        """
        command = COMMANDS_METADATA["update_user_data"]["name"]
        bot_logger.debug("%s user invoked %s command with args: %s, %s",
                         ctx.author.id, command, field, data)
        # TODO this function is too long
        # TODO can we re-use the user object returned from local_cache.get_user?
        # Check for user's eligiblity to edit this
        _, e = self.lc.get_user(discord_id=ctx.author.id)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        # Check if users are expected to update this field  
        if (field not in self.ic.create_prompt_keys(model="user", mode="all")
            and field is not None):
            await ctx.author.send(f"{field} can't be updated by users")
            return
        # Also check that value is not empty
        check = bool(field) + bool(data)
        bot_logger.debug("Update check is %i", check)
        if check == 1 or (data is not None and len(data) == 0):
            await ctx.author.send(f"Can't run update with {data}, try again")
            return

        user_update = {field: data}
        # TODO the below IF needs to be a function?
        # if check is zero, we prompt for all fields!
        if check == 0:
            bot_logger.debug("%s user did not provide any fields, prompting...",
                             ctx.author.id)
            # Prompt for fields to update
            user_update = await self.get_input(ctx=ctx, command=command,
                                               model="user", include_extra=True)
            bot_logger.debug("Received update input from user %s: %s",
                             ctx.author.id, user_update)
            # Len of 1 means we only have discord id
            if len(user_update) == 1:
                await ctx.message.author.send(
                    "No update data provided, stopping command."
                )
                return
        # Attempt an update
        bot_logger.debug("Attempting update on user %s db data", ctx.author.id)
        e = self.lc.update_user_data(discord_id=ctx.author.id,
                                     user_update=user_update)
        # Log on results
        if e is not None:
            bot_logger.error("Update for user %s failed, %s", ctx.author.id, e)
            await ctx.message.author.send("Error when updating user data: %s", e)
            return
        bot_logger.debug("Update for user %s succeeded", ctx.author.id)
        await ctx.message.author.send("Data updated!")
