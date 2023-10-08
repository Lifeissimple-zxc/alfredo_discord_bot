import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands

from alfredo_lib import MAIN_CFG
from alfredo_lib.alfredo_deps import cache, validator
from alfredo_lib.bot import ex
from alfredo_lib.bot.cogs.base import base_cog
from alfredo_lib.local_persistence import models

bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])

class AccountCog(base_cog.CogHelper, name="account"):
    """Encapsulates commands related to user accounts"""

    def __init__(self, bot: commands.Bot,
                 local_cache: cache.Cache,
                 input_controller: validator.InputController):
        super().__init__(bot=bot, local_cache=local_cache,
                         input_controller=input_controller)

    @commands.command()
    async def register(self, ctx: commands.Context):
        """Performs User registration""" #TODO this is user facing, beware
        command = "register" #TODO make it a config
        reg_data = await self.get_input(ctx=ctx, command=command,
                                   model="user", include_extra=True)
        
        # Validate command and send message to the user on success?
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
        # Check for error
        if e is not None:
            await ctx.message.author.send(
                f"{command} failed for {username}: {user_msg}"
            )
            return
        # Give feedback to a user
        await ctx.message.author.send(
            f"User {username} registered with discord_id {reg_data['discord_id']}"
        )
    
    @commands.command()
    async def whoami(self, ctx: commands.Context):
        # Read data to variables
        discord_id = ctx.author.id
        #TODO how can we have this logging call embedded into the commands?
        #TODO mb a decorator in the bot class?
        bot_logger.debug("User %s invoked %s command", discord_id, "get_my_data")
        # Read from DB, generally we parse here
        # So the second item might not be an exception
        user_data, user_msg = self.lc.get_user(discord_id)
        if user_msg is not None:
            raise ex.UserNotRegisteredError(msg=user_msg)
        await ctx.message.author.send(f"Your data:\n{user_data}")
    
    @commands.command(aliases=("uud","update"))
    async def update_user_data(self,
                               ctx: commands.Context,
                               field: Optional[str] = None,
                               value: Optional[str] = None):
        """
        ### Updates user data
        """
        command = "update_user_data" #TODO make it a config
        discord_id = ctx.author.id
        bot_logger.debug("%s user invoked %s command with args: %s, %s",
                         discord_id, command, field, value)
        # TODO this function is too long
        # TODO can we re-use the user object returned from local_cache.get_user?
        # Check for user's eligiblity to edit this
        _, e = self.lc.get_user(discord_id=discord_id, parse=False)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        # Check if users are expected to update this field  
        if (field not in self.ic.create_prompt_keys(model="user", mode="all")
            and field is not None):
            await ctx.author.send(f"{field} can't be updated by users")
            return
        # Also check that value is not empty
        check = bool(field) + bool(value)
        bot_logger.debug("Update check is %i", check)
        if check == 1 or (value is not None and len(value) == 0):
            await ctx.author.send(f"Can't run update with {value}, try again")
            return

        user_update = {field: value}
        # TODO the below IF needs to be a function?
        # if check is zero, we prompt for all fields!
        if check == 0:
            bot_logger.debug("%s user did not provide any fields, prompting...",
                             discord_id)
            # Prompt for fields to update
            user_update = await self.get_input(ctx=ctx, command=command,
                                               model="user", include_extra=True)
            bot_logger.debug("Received update input from user %s: %s",
                             discord_id, user_update)
            # Len of 1 means we only have discord id
            if len(user_update) == 1:
                await ctx.message.author.send(
                    "No update data provided, stopping command."
                )
                return
        # Attempt an update
        bot_logger.debug("Attempting update on user %s db data", discord_id)
        e = self.lc.update_user_data(discord_id=discord_id, user_update=user_update)
        # Log on results
        if e is not None:
            bot_logger.error("Update for user %s failed, %s", discord_id, e)
            await ctx.message.author.send("Error when updating user data: %s", e)
            return
        bot_logger.debug("Update for user %s succeeded", discord_id)
        await ctx.message.author.send("Data updated!")