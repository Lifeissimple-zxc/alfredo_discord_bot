import discord
import logging.config
from discord.ext import commands
from cogs.greetings import Greetings
from alfredo_lib import (
    LOGGING_CONFIG,
    ENV_VARS,
    CMDS_DIR,
    COGS_DIR
)
# Continue from https://www.youtube.com/watch?v=ynD_dffUzrg&list=PLESMQx4LeD3N0-KKPPDaToZhBsom2E_Ju&index=14
# Boilerplate for logging config
logging.config.dictConfig(LOGGING_CONFIG)
bot_logger = logging.getLogger("alfredo_logger")


def run_bot():
    """
    Test func for running the bot for the first time ever
    """
    intents = discord.Intents.default()  # This parses messages to the bot
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        bot_logger.info(f"User: {bot.user} (ID: {bot.user.id})")

        # Add our commands from a separate file
        for cmd_file in CMDS_DIR.glob("*.py"):
            # Ignore inits
            if ((cmd_name := cmd_file.name) == "__init__.py"):
                continue
            # Load the file ignoring last 3 .py chars in name
            await bot.load_extension(f"cmd_test.{cmd_name[:-3]}")

        # Bulk load our cogs
        for cog_file in COGS_DIR.glob("*.py"):
            # Ignore inits
            if ((cog_name := cog_file.name) == "__init__.py"):
                continue
            await bot.load_extension(f"cogs.{cog_name[:-3]}")

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("You did not provide any input, WHY?")

    # Command for the bot (example to keep hidden)
    @bot.command(aliases=["p", "pi"],
                 help="Good for playing ping pong",
                 description="Answers with pong, not very useful, eh?",
                 brief="Who needs expenses when we can do ping <> pong",
                 enabled=True,
                 hidden=True)
    async def ping(ctx):
        """
        Answers with pong
        """
        await ctx.send("pong")

    # Ping that replies to a DM
    @bot.command()
    async def ping_dm(ctx: commands.Context):
        await ctx.message.author.send("PONG!")
        
    @bot.command()
    async def test(ctx):
        """
        Tests that a bot responds to commands
        """
        await ctx.send("Testing Testing 1-2-3 I am Alfredo, let's track expenses!")

    # Command that mirrors input to the user
    # Mirros till the first space
    @bot.command()
    async def say(ctx, what):
        await ctx.send(what)

    @bot.command()
    async def say_words(ctx, *what):
        await ctx.send(" ".join(what))


    # Command for sending a brief summary about the user
    # Using a type hint allows us to access user data
    @bot.command()
    async def whoami(ctx, who: discord.Member):
        await ctx.send(who.display_name)
        await ctx.send(who.name)
        await ctx.send(who.joined_at)

    # Example of error handling (classic)
    # @bot.command()
    # async def to_number(ctx, input: str):
    #     try:
    #         converted = float(input)
    #     except ValueError:
    #         await ctx.send(f"Cannot convert `{input}` to number :(")
    #     else:
    #         await ctx.send(converted)

    @bot.command() # This is our command
    async def to_number(ctx, input: str):
        await ctx.send(float(input))

    # Example of error handling (discord.py local)
    # @to_number.error
    # async def to_number_error(ctx, error):
    #     if isinstance(error, ValueError): ## This is not handled here for some reason
    #         await ctx.send("Cannot by converted to number")
    #     elif isinstance(error, commands.MissingRequiredArgument):
    #         await ctx.send("You did not provide any input, WHY?")

    # Command to reload the bot (partially)?
    @bot.command()
    async def reload(ctx, cog: str):
        await bot.reload_extension(f"cogs.{cog.lower()}")

    @bot.command()
    async def unload(ctx, cog: str):
        await bot.unload_extension(f"cogs.{cog.lower()}")
    
    @bot.command()
    async def load(ctx, cog: str):
        await bot.load_extension(f"cogs.{cog.lower()}")

    # Command with a permission
    async def is_owner(ctx):
        return ctx.author.id
    @bot.command()
    @commands.check(is_owner)
    async def say_admin(ctx, what: str=None):
        if what is None:
            what = "WHAT"
        await ctx.send(what)
    # Erorr handler for permission related errors
    @say_admin.error
    async def say_admin_error(ctx: commands.Context, error):
        if isinstance(error, commands.CommandError):
            await ctx.send("Permission denied")

    bot.run(ENV_VARS["DISCORD_APP_TOKEN"], root_logger=True)

run_bot()