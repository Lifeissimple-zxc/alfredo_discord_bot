import asyncio
import logging
import logging.config as log_config
from typing import Optional

import discord
import yaml
from discord.ext import commands

from alfredo_lib.alfredo_deps import (
    local_cache,
    input_controller,
    validator 
)
from alfredo_lib.local_persistence import models
from alfredo_lib.bot import ex, cogs
from alfredo_lib import MAIN_CFG, ENV_VARS

# Logging boilerplate
# Read logging configuration
with open(MAIN_CFG["logging_config"]) as _log_cfg:
    LOGGING_CONFIG = yaml.safe_load(_log_cfg)
# Configure our logger
log_config.dictConfig(LOGGING_CONFIG)
# Get loggers
bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])


def run_alfredo():
    """
    Entry point to running Alfredo bot
    """
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix=MAIN_CFG["command_prefix"], intents=intents)

    @bot.event
    async def on_ready():
        bot_logger.debug("User: %s (ID: %s)", bot.user, bot.user.id)

    @bot.event
    async def on_command_error(ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.message.author.send(MAIN_CFG["error_messages"]["missing_input"])
        # All the raises inside the bot's body are wrapped with CommandInvokeError
        elif isinstance(error, commands.CommandInvokeError):
            cause = error.__cause__
            if isinstance(cause, ex.UserNotRegisteredError):
                bot_logger.info("Unregistered %s tried to invoke %s",
                                ctx.message.author.id, ctx.invoked_with)
                await ctx.message.author.send(
                    MAIN_CFG["error_messages"]["user_not_registered"].format(cmd=ctx.invoked_with)
                )
    
    @bot.command()
    async def load_cogs(ctx: commands.Context):
        """
        Secret command to loading cogs
        """ 
        # TODO add admin check here, should come from config
        if ctx.author.id not in {194543162604126208}:
            bot_logger.warning("User %s tried to load cogs", ctx.author.id)
            return
        # TODO make the command hidden
        await bot.add_cog(cogs.AccountCog(bot=bot, local_cache=local_cache,
                                          input_controller=input_controller))
        bot_logger.debug("Loaded AccountCog")
    
    
    @bot.command(aliases=("get_tr",))
    async def get_transaction(ctx: commands.Context) -> tuple:
        """
        ### Fetches user transactions
        :return:
        """
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        
        # Check if caller discord id is in db
        user, e = local_cache.get_user(discord_id=discord_id, parse=False)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        
        transaction = local_cache.get_user_transactions(user=user, parse=True) 
        if transaction:
            await ctx.author.send(
                MAIN_CFG["messages"]["ong_transaction_exists"].format(transaction=transaction)
            )
            return
        await ctx.author.send("No ongoing transactions located")
    
    async def create_transaction(ctx: commands.Context, user: models.User,
                                 command: str):
        """
        ### Creates a new transaction from scratch my prompting user for data
        """
        tr_data = await get_input(ctx=ctx, command=command, model="transaction",
                                  rec_discord_id=False, include_extra=True)
        # Validate input (parse numbers) TODO
        # Add user level features fot the user input
        tr_data["user_id"] = user.user_id
        tr_data["currency"] = user.currency
        bot_logger.debug("Transaction data prepared %s", tr_data)
        # Write to db
        msg, e = local_cache.create_transaction(tr_data)
        if e is not None:
            bot_logger.error("new_transaction() failed: %s", e)
        await ctx.author.send(msg)

    @bot.command(aliases=("tr",))
    async def new_transaction(ctx: commands.Context):
        """
        ### Adds a new transaction to the sheet saved by the user
        """
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        command = "new_transaction"
        # Check if caller discord id is in db
        user, e = local_cache.get_user(discord_id=discord_id, parse=False)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        transaction = local_cache.get_user_transactions(user=user, parse=True)
        bot_logger.debug("Fetched user transaction")
        if transaction:
            await ctx.author.send(
                # TODO Specify commands to be called here
                "Transaction is in progress. Delete or Update using commands."
            )
            return
        await create_transaction(ctx, user=user, command=command)

    @bot.command(aliases=("del_tr",))
    async def delete_ong_transaction(ctx: commands.Context):
        """
        ### Deletes ongoing transaction 
        """
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        # Check if caller discord id is in db
        user, e = local_cache.get_user(discord_id=discord_id, parse=False)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        # Get transaction as ORM obj
        transaction = local_cache.get_user_transactions(user=user, parse=False)
        if not transaction:
            await ctx.author.send("No transactions located, can't delete")
            return
        # Delete transaction using cache class methods
        e = local_cache.delete_row(transaction)
        if e is not None:
            msg = f"Error deleting transaction row: {e}"
            bot_logger.error(msg)
            await ctx.author.send(msg)
            return
        await ctx.author.send("Transaction deletion - success!")


    @bot.command(aliases=("upd_tr",))
    async def update_transaction(ctx: commands.Context, field: str, data: str):
        """
        Updates transaction using user input
        """
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        # Check if caller discord id is in db
        user, e = local_cache.get_user(discord_id=discord_id, parse=False)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        # Check if field is valid
        allowed_fields = input_controller.create_prompt_keys(model="transaction",
                                                             mode="all")
        if field not in allowed_fields and field is not None:
            # TODO this should be handled in a generic fashion
            await ctx.author.send(f"{field} can't be updated by users")
            return 
        # Perform type conversion if needed
        data, e = input_controller.parse_input(model="transaction",
                                               field=field, data=data)
        if e is not None:
            # TODO this should be handled in a generic fashion too
            await ctx.author.send(f"{data} is not valid for {field}: {e}")
            return
        # Fetch transation that to apply updates to
        transaction = local_cache.get_user_transactions(user=user, parse=False)
        if not transaction:
            # TODO Generic handling?
            await ctx.author.send("No transactions located, can't update")
            return
        # Call cache method to update transation
        e = local_cache.update_transaction(update={field: data},
                                           transaction=transaction)
        if e is not None:
            msg = f"DB Data update failed for transaction: {e}"
            bot_logger.error(msg)
            await ctx.author.send(msg)
        await ctx.author.send("Transaction data updated!")
    
    # This is where the bot is actually launched
    bot.run(ENV_VARS["DISCORD_APP_TOKEN"], root_logger=True)


if __name__ == "__main__":
    try:
        run_alfredo()
    except Exception as e:
        bot_logger.error(f"Unexpected exception: {e}")
