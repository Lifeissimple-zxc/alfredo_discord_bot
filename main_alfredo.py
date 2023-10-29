"""
Module implements entry point to launching alfredo bot
"""
import logging
import logging.config as log_config

import discord
import yaml
from discord.ext import commands

from alfredo_lib import COMMANDS_METADATA, ENV_VARS, MAIN_CFG
from alfredo_lib.alfredo_deps import input_controller, local_cache, sheets
from alfredo_lib.bot import buttons, ex
from alfredo_lib.bot.cogs import account, category, transaction

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
        bot_logger.debug("User: %s (ID: %s)", bot.user, bot.user.id)
        await sheets.discover_sheet_service(
            api_version=MAIN_CFG["google_sheets"]["version"]
        )
        try:
            await bot.add_cog(
                account.AccountCog(bot=bot, local_cache=local_cache,
                                   input_controller=input_controller,
                                   sheets=sheets))
        except Exception as e:
            bot_logger.exception("Can't load AccountCog: %s", e)
        bot_logger.debug("Loaded AccountCog")
        
        try:
            await bot.add_cog(
                transaction.TransactionCog(bot=bot, local_cache=local_cache,
                                           input_controller=input_controller,
                                           sheets=sheets))
        except Exception as e:
            bot_logger.exception("Can't load TransactionCog: %s", e)
        bot_logger.debug("Loaded TransactionCog")

        try:
            await bot.add_cog(
                category.CategoryCog(bot=bot, local_cache=local_cache,
                                     input_controller=input_controller,
                                     sheets=sheets))
        except Exception as e:
            bot_logger.exception("Can't load CategoryCog: %s", e)
        bot_logger.debug("Loaded CategoryCog")

    # TODO this does not work properly!, fix
    @bot.event
    async def on_message(message: discord.Message):
        if message.author == bot.user:
            return  # Ignore messages from the bot itself
        if not message.content.startswith(MAIN_CFG["command_prefix"]):
            await message.author.send(
                MAIN_CFG["error_messages"]["msg_reaction"]
            )
    
    @bot.event
    async def on_command_error(ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.message.author.send(
                MAIN_CFG["error_messages"]["missing_input"]
            )
        elif isinstance(error, commands.BadArgument):
            arg = error.args[0] if error.args else 'Unknown input'
            await ctx.message.author.send(
                MAIN_CFG["error_messages"]["bad_argument"].format(
                    arg=arg, cmd=ctx.invoked_with
                )
            )
        # All the raises inside the bot's body are wrapped with CommandInvokeError
        elif isinstance(error, commands.CommandInvokeError):
            if isinstance(error.__cause__, ex.UserNotRegisteredError):
                bot_logger.debug("Unregistered %s attempted invoking %s",
                                ctx.message.author.id, ctx.invoked_with)
                await ctx.message.author.send(
                    MAIN_CFG["error_messages"]["user_not_registered"].format(cmd=ctx.invoked_with)
                )
            elif isinstance(error.__cause__, ex.AdminPermissionNeededError):
                bot_logger.debug("Non admin %s attempted invoking %s",
                                 ctx.message.author.id, ctx.invoked_with)
                await ctx.message.author.send(
                    MAIN_CFG["error_messages"]["admin_permission_needed"].format(cmd=ctx.invoked_with)
                )
            elif isinstance(error.__cause__, ex.WrongUpdateFieldInputError):  # noqa: E501
                bot_logger.debug(
                    "%s provided an incorrect field attempt for %s: %s",
                    ctx.message.author.id, ctx.invoked_with, error.__cause__
                )
                await ctx.message.author.send(
                    MAIN_CFG["error_messages"]["bad_field_update"].format(
                        cmd=ctx.invoked_with, e=error.__cause__
                    )
                )
            elif isinstance(error.__cause__, ex.InvalidUserInputError):
                bot_logger.debug("%s provided invalid input for %s: %s",
                                 ctx.message.author.id, ctx.invoked_with, error.__cause__)
                await ctx.message.author.send(
                    MAIN_CFG["error_messages"]["bad_input"].format(
                        cmd=ctx.invoked_with, e=error.__cause__
                    )
                )
            elif isinstance(error.__cause__, NotImplementedError):
                bot_logger.error(error.__cause__)
                await ctx.message.author.send(
                    MAIN_CFG["error_messages"]["missing_implementation"].format(
                        cmd=ctx.invoked_with, e=error.__cause__
                    )
                )
            elif isinstance(error.__cause__, ex.UnknownCommandInvokedError):
                bot_logger.error("%s invoked an unknown command: %s",
                                 ctx.message.author.id, ctx.invoked_with)
                await ctx.message.author.send(
                    MAIN_CFG["error_messages"]["missing_implementation"].format(
                        cmd=ctx.invoked_with
                    )
                )

    @bot.command(
        name=COMMANDS_METADATA["show_guide"]["name"],
        aliases=COMMANDS_METADATA["show_guide"]["aliases"],
        help=COMMANDS_METADATA["show_guide"]["help"]
    )
    async def show_guide(ctx: commands.Context):
        """
        Shows a TLDR of how the bot is used to the user
        """
        bot_logger.debug("Command invoked")
        try:
            msg = "\n".join(COMMANDS_METADATA["show_guide"]["message"])
            await ctx.message.author.send(msg)
        except Exception as e:
            msg = f"Unexpected error when preparing a guide message: {e}"
            bot_logger.error(msg)
            await ctx.message.author.send(contet=msg)

    @bot.command()
    async def start(ctx: commands.Context):
        account = buttons.AccountView(bot=bot, ctx=ctx)
        transaction = buttons.TransactionView(bot=bot, ctx=ctx)
        await ctx.message.author.send("Account commands:")
        await ctx.message.author.send(view=account)
        try:
            # Check if user is registered
            _, e = bot.cogs[MAIN_CFG["cog_names"]["account"]].lc.get_user(discord_id=ctx.author.id)
            if e is not None:
                bot_logger.debug("Unregistered user invoked start, showing account view only")
                return
        except Exception as e:
            bot_logger.error("Error checking registration command: %s", e)
            return
        bot_logger.debug("Registered user invoked start, showing transaction view")
        await ctx.message.author.send("Transaction commands:")
        await ctx.message.author.send(view=transaction)
        

    # This is where the bot is actually launched
    bot.run(ENV_VARS["DISCORD_APP_TOKEN"], root_logger=True)


if __name__ == "__main__":
    try:
        run_alfredo()
    except Exception as e:
        bot_logger.error(f"Unexpected exception: {e}")
