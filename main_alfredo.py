import asyncio
import logging
import logging.config as log_config

import discord
from discord.ext import commands
import yaml

from alfredo_lib.alfredo_deps import (
    local_cache,
    input_controller
)
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

    bot = commands.Bot(command_prefix=MAIN_CFG["command_prefix"],
                       intents=intents)

    @bot.event
    async def on_ready():
        bot_logger.debug(f"User: {bot.user} (ID: {bot.user.id})")

    @bot.event
    async def on_command_error(ctx: commands.Context,
                               error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(MAIN_CFG["error_messages"]["missing_input"])
    
    ### Commands to read data iteratively

    def check_ctx(msg: discord.Message, author: discord.User):
        return msg.author == author and msg.channel == author.dm_channel

    async def get_input(ctx: commands.Context, command: str, mode: str):
        """
        ### Continuously prompts for user input.
        Stores user responsed in a dict.
        """
        #TODO timeout 
        discord_id = ctx.author.id
        bot_logger.debug("Prompting user %s for %s command data",
                         discord_id, command)
        res = {"discord_id": ctx.author.id}
        input_keys = input_controller.create_prompt_keys(command=command, mode=mode)
        bot_logger.debug("Prepared input keys %s for user %s", input_keys, discord_id)
        for key in input_keys:
            await ctx.message.author.send(f"Please enter your {key}!")
            
            try:
                resp = await bot.wait_for(
                    "message",
                    check=lambda message: check_ctx(message, ctx.author),
                    timeout=20
                )
                data = resp.content
            except asyncio.TimeoutError:
                await ctx.message.author.send("Took too long to respond. Aborting!")
                break

            res[key] = data
        bot_logger.debug("Collected data for command %s: %s", command, res)
        return res

    ### Commands
    @bot.command()
    async def register(ctx: commands.Context):
        command = "register" #TODO make it a config
        reg_data = await get_input(ctx=ctx, command=command, mode="all")
        
        # Validate command and send message to the user on success?
        missing = input_controller.validate(user_input=reg_data, command=command)
        if missing:
            await ctx.message.author.send(
                f"Cannot run {command}. Missing fields: {missing}"
            )
            return
        await ctx.message.author.send(
            f"All base fields are present. Running {command}."
        )

        user_msg, e = local_cache.create_user(reg_data)
        username = reg_data["username"]
        # Check for error
        if e is not None:
            await ctx.message.author.send(
                f"Registration failed for {username}: {user_msg}"
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
        bot_logger.debug("User %s invoked %s command", discord_id, "get_my_data")
        # Read from DB
        user_data, user_msg = local_cache.get_user(discord_id)
        if user_msg:
            await ctx.message.author.send(user_msg)
        await ctx.message.author.send(f"Your data:\n{user_data}")

    @bot.command(aliases=("uud",))
    async def update_user_data(ctx: commands.Context,
                               field: str = None, value: str = None):
        """
        Updates user data
        """
        # TODO can commmands have arguments for updating a specific field?
        command = "update_user_data" #TODO make it a config
        discord_id = ctx.author.id
        bot_logger.debug("%s user invoked %s command with args: %s, %s",
                         discord_id, command, field, value)
        user_update = {field: value}
        if field is None or value is None:
            # Prompt for fields to update
            user_update = await get_input(ctx=ctx, command="register", mode="all")
            bot_logger.debug("Received input user input update from user %s: %s",
                            discord_id, user_update)
            # Collect user data
            if not user_update:
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
    
    # This is where the bot is actually launched
    bot.run(ENV_VARS["DISCORD_APP_TOKEN"], root_logger=True)


if __name__ == "__main__":
    try:
        run_alfredo()
    except Exception as e:
        bot_logger.error(f"Unexpected exception: {e}")
