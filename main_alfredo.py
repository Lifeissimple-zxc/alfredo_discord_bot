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
from alfredo_lib.bot import ex
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
        if isinstance(error, ex.UserNotRegisteredError):
            await ctx.message.author.send(
                MAIN_CFG["error_messages"]["missing_input"].format(cmd=error.cmd)
            )
    
    ### Commands to read data iteratively

    def check_ctx(msg: discord.Message, author: discord.User):
        return msg.author == author and msg.channel == author.dm_channel

    async def _ask_user_for_data(
        ctx: commands.Context,
        input_container: dict,
        model: str,
        mode: Optional[str] = None,
        input_controller: Optional[validator.InputController] = None
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

        prompt_keys = input_controller.input_schemas[model][mode]
        
        for key in prompt_keys:
            await ctx.message.author.send(f"Please enter your {key}!")
            
            try:
                resp = await bot.wait_for(
                    "message",
                    check=lambda message: check_ctx(message, ctx.author),
                    timeout=MAIN_CFG["input_prompt_timeout"]
                )
                data = resp.content
                bot_logger.debug("Parsing %s...", key)
                data, e = input_controller.parse_input(model=model,
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
        
    async def get_input(ctx: commands.Context, command: str,
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
        
        res, e = await _ask_user_for_data(ctx=ctx, input_container=res,
                                          input_controller=input_controller,
                                          mode="base", model=model)
        # This happends due to timeout so returning no data makes sense???
        if e is not None:
            return {}
        if include_extra:
            res, e = await _ask_user_for_data(ctx=ctx, input_container=res,
                                              input_controller=input_controller,
                                              mode="extra", model=model)
           
        bot_logger.debug("Collected data for command %s: %s", command, res)
        return res

    ### Commands that users are expected to call
    @bot.command()
    async def register(ctx: commands.Context):
        command = "register" #TODO make it a config
        reg_data = await get_input(ctx=ctx, command=command,
                                   model="user", include_extra=True)
        
        # Validate command and send message to the user on success?
        # TODO Exception uncaught here
        missing = input_controller.validate_keys(user_input=reg_data, model="user")
        if missing:
            await ctx.message.author.send(
                f"Cannot run {command}. Missing fields: {missing}"
            )
            return
        await ctx.message.author.send(f"All fields are present. Running {command}.")

        user_msg, e = local_cache.create_user(reg_data)
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
    
    @bot.command()
    async def whoami(ctx: commands.Context):
        # Read data to variables
        discord_id = ctx.author.id
        #TODO how can we have this logging call embedded into the commands?
        #TODO mb a decorator in the bot class?
        bot_logger.debug("User %s invoked %s command", discord_id, "get_my_data")
        # Read from DB
        user_data, user_msg = local_cache.get_user(discord_id)
        if user_msg:
            await ctx.message.author.send(user_msg)
            return
        await ctx.message.author.send(f"Your data:\n{user_data}")

    @bot.command(aliases=("uud","update"))
    async def update_user_data(ctx: commands.Context,
                               field: Optional[str] = None,
                               value: Optional[str] = None):
        """
        ### Updates user data
        """
        command = "update_user_data" #TODO make it a config
        discord_id = ctx.author.id
        bot_logger.debug("%s user invoked %s command with args: %s, %s",
                         discord_id, command, field, value)
        # Check if users are expected to update this field  
        if (field not in input_controller.create_prompt_keys(model="user", mode="all")
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
            user_update = await get_input(ctx=ctx, command=command,
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
        e = local_cache.update_user_data(discord_id=discord_id, user_update=user_update)
        # Log on results
        if e is not None:
            bot_logger.error("Update for user %s failed, %s", discord_id, e)
            await ctx.message.author.send("Error when updating user data: %s", e)
            return
        bot_logger.debug("Update for user %s succeeded", discord_id)
        await ctx.message.author.send("Data updated!")
    
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
            raise e
        
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
            raise e
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
            raise e
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


    async def update_transaction(ctx: commands.Context, field: str, value: str):
        """
        Updates transaction using user input
        """
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        # Check if caller discord id is in db
        user, e = local_cache.get_user(discord_id=discord_id, parse=False)
        if e is not None:
            raise e
        # Check if field is valid
        # Perform type conversion if needed
            # alert on error
        # Call cache method to update transation
        # Inform user on outcome

    
    # This is where the bot is actually launched
    bot.run(ENV_VARS["DISCORD_APP_TOKEN"], root_logger=True)


if __name__ == "__main__":
    try:
        run_alfredo()
    except Exception as e:
        bot_logger.error(f"Unexpected exception: {e}")
