import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands

from alfredo_lib.alfredo_deps import (
    validator,
    cache
)
from alfredo_lib.local_persistence import models
from alfredo_lib.bot import ex
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

class TransactionCog(CogHelper, name="account"):
    """Encapsulates commands related to transactions"""

    def __init__(self, bot: commands.Bot,
                 local_cache: cache.Cache,
                 input_controller: validator.InputController):
        super().__init__(bot=bot, local_cache=local_cache,
                         input_controller=input_controller)
        
    @commands.command(aliases=("get_tr",))
    async def get_transaction(self, ctx: commands.Context) -> tuple:
        """
        Fetches a user's ongoing transaction if there is one
        """
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=discord_id, parse=False)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        transaction = self.lc.get_user_transactions(user=user, parse=True) 
        if transaction:
            await ctx.author.send(
                MAIN_CFG["messages"]["ong_transaction_exists"].format(transaction=transaction)
            )
            return
        await ctx.author.send("No ongoing transactions located")

    async def _create_transaction(self, ctx: commands.Context,
                                  user: models.User, command: str):
        """
        ### Creates a new transaction from scratch my prompting user for data
        """
        tr_data = await self.get_input(ctx=ctx, command=command, model="transaction",
                                       rec_discord_id=False, include_extra=True)
        # DO we check user input somehow here??? TODO
        tr_data["user_id"] = user.user_id
        tr_data["currency"] = user.currency
        bot_logger.debug("Transaction data prepared %s", tr_data)
        # Write to db
        msg, e = self.lc.create_transaction(tr_data)
        if e is not None:
            bot_logger.error("new_transaction() failed: %s", e)
        await ctx.author.send(msg)

    @commands.command(aliases=("tr",))
    async def new_transaction(self, ctx: commands.Context):
        """Adds a new transaction to the sheet saved by the user"""
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        command = "new_transaction"
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=discord_id, parse=False)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        transaction = self.lc.get_user_transactions(user=user, parse=True)
        bot_logger.debug("Fetched user transaction")
        if transaction:
            await ctx.author.send(
                # TODO Specify commands to be called here
                "Transaction is in progress. Delete or Update using commands."
            )
            return
        await self._create_transaction(ctx, user=user, command=command)


            
