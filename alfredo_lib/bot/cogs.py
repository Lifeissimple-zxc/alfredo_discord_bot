import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands

from alfredo_lib.alfredo_deps import (
    validator,
    cache
)
from alfredo_lib import MAIN_CFG

bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])


class CogHelper(commands.Cog):
    """Encapsulates methods that COGS rely on"""

    #TODO objects in this init should be singletons instead
    def __init__(self, bot: commands.Bot,
                 local_cache: cache.Cache,
                 input_controller: validator.InputController):
        self.bot = bot
        self.lc = local_cache
        self.ic = input_controller


    @staticmethod
    def check_ctx(msg: discord.Message, author: discord.User):
        """
        Helper that checks for message and channel being a DM
        """
        return msg.author == author and msg.channel == author.dm_channel
    
    async def _ask_user_for_data(
        self,
        ctx: commands.Context,
        input_container: dict,
        model: str,
        mode: Optional[str] = None
    ) -> dict:
        """
        ### Prompts for data either using input_schemas[model][mode] of input_controller
        """
        # Quick mode check to avoid doing dowstream & save computation time
        mode = mode or "base"
        if mode not in ("base", "extra"):
            bot_logger.error("Bad mode supplied: %s", mode)
            return {}
        # Making a copy not to do in-place modifications!
        res = input_container.copy()

        prompt_keys = self.ic.input_schemas[model][mode]
        
        for key in prompt_keys:
            await ctx.message.author.send(f"Please enter your {key}!")
            
            try:
                resp = await self.bot.wait_for(
                    "message",
                    check=lambda message: self.check_ctx(message, ctx.author),
                    timeout=MAIN_CFG["input_prompt_timeout"]
                )
                data = resp.content
                bot_logger.debug("Parsing %s...", key)
                data, e = self.ic.parse_input(model=model,
                                              field=key, data=data)
                if e is not None:
                    await ctx.message.author.send(f"{key} cannot be parsed: {e}")
                    if mode == "base":
                        # Returning bc 1 missing base field is a problem
                        return res, None
                    else:
                        continue

            except asyncio.TimeoutError as e:
                await ctx.message.author.send(
                    MAIN_CFG["error_messages"]["prompt_timeout"]
                )
                return res, e

            res[key] = data
        return res, None
    
    async def get_input(self, ctx: commands.Context, command: str,
                        model: str, include_extra: Optional[bool] = None,
                        rec_discord_id: Optional[bool] = None) -> dict:
        """
        ### Continuously prompts for user input.
        Stores user responsed in a dict.
        :param rec_discord_id: True means auto adding a user's discord_id to the input 
        """

        if rec_discord_id is None:
            rec_discord_id = True
        if include_extra is None:
            include_extra = True

        discord_id = ctx.author.id
        bot_logger.debug("Prompting user %s for %s command data",
                         discord_id, command)

        res = {}
        if rec_discord_id:
            res["discord_id"] = ctx.author.id
        
        res, e = await self._ask_user_for_data(
            ctx=ctx, input_container=res,
            mode="base", model=model
        )
        # This happends due to timeout so returning no data makes sense???
        if e is not None:
            return {}
        if include_extra:
            res, e = await self._ask_user_for_data(
                ctx=ctx, input_container=res,
                mode="extra", model=model
            )
           
        bot_logger.debug("Collected data for command %s: %s", command, res)
        return res

class AccountCog(CogHelper, name="account"):
    """Encapsulates commands related to user accounts"""

    def __init__(self, bot: commands.Bot,
                 local_cache: cache.Cache,
                 input_controller: validator.InputController):
        super().__init__(bot=bot, local_cache=local_cache,
                         input_controller=input_controller)

    @commands.command()
    async def register(self, ctx: commands.Context):
        """Performs User registration"""
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