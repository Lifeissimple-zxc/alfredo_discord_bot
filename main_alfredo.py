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

    # Command for registering a user
    @bot.command()
    async def register(ctx: commands.Context, username: str):
        # Read data to variables
        discord_id = ctx.author.id
        # Add to db
        # TODO return a tuple here and check for error
        user_msg, e = local_cache.create_user(username=username, discord_id=discord_id)
        # Check for error
        if e is not None:
            await ctx.send(f"Registration failed for {username}: {user_msg}")
            return
        # Give feedback to a user
        await ctx.send(f"User {username} registered with discord_id {discord_id}")

    @bot.command()
    async def get_user(ctx: commands.Context):
        # Read data to variables
        discord_id = ctx.author.id
        # Read from DB
        user_data, user_msg = local_cache.get_user(discord_id)
        if user_msg:
            await ctx.send(user_msg)
        await ctx.send(f"Your data: {user_data}")

    ### Commands to read data iteratively

    def check_ctx(msg: discord.Message, author: discord.User):
        return msg.author == author and msg.channel == author.dm_channel

    async def get_input(ctx: commands.Context, command: str, mode: str):
        """
        ### Continuously prompts for user input.
        Stores user responsed in a dict.
        """
        bot_logger.debug("Prompting user %s for %s command data",
                         ctx.author.id, command)
        res = {"discord_id": ctx.author.id}
        for key in input_controller.create_prompt_keys(command=command, mode=mode):
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
            print(res)
        bot_logger.debug("Collected data for command %s: %s", command, res)
        return res

    @bot.command()
    async def reg_new(ctx: commands.Context):
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



                
    
    # This is where the bot is actually launched
    bot.run(ENV_VARS["DISCORD_APP_TOKEN"], root_logger=True)

run_alfredo()
