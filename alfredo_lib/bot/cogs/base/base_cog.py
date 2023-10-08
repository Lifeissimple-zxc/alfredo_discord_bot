import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands

from alfredo_lib import MAIN_CFG
from alfredo_lib.alfredo_deps import cache, validator
from alfredo_lib.bot import ex
from alfredo_lib.local_persistence import models

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
