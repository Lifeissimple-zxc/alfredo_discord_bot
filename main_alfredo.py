import logging
import logging.config as log_config

import discord
import yaml
from discord.ext import commands

from alfredo_lib import ENV_VARS, MAIN_CFG
from alfredo_lib.alfredo_deps import input_controller, local_cache, sheets
from alfredo_lib.bot import ex
from alfredo_lib.bot.cogs import account, transaction

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
        # TODO make the command hidden
        if ctx.author.id not in {194543162604126208}:
            bot_logger.warning("User %s tried to load cogs", ctx.author.id)
            return
        
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
            
        
    
    # This is where the bot is actually launched
    bot.run(ENV_VARS["DISCORD_APP_TOKEN"], root_logger=True)


if __name__ == "__main__":
    try:
        run_alfredo()
    except Exception as e:
        bot_logger.error(f"Unexpected exception: {e}")
