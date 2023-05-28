import discord
from alfredo_lib.local_persistence.cache import Cache
from discord.ext import commands
from alfredo_lib import (
    logging,
    ENV_VARS,
    MAIN_CFG,
    ERROR_MESSAGES
)


bot_logger = logging.getLogger("alfredo_logger")
# Useful classes
cache = Cache(MAIN_CFG["cache_path"])


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
        e = cache.create_user(username=username, discord_id=discord_id)
        # Check for error
        if e is not None:
            await ctx.send(f"Registration failed for {username}: {e}")
            return
        # Give feedback to a user
        await ctx.send(f"User {username} registered with discord_id {discord_id}")

    # This is where the bot is actually launched
    bot.run(ENV_VARS["DISCORD_APP_TOKEN"], root_logger=True)

run_alfredo()
