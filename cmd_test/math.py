from discord.ext import commands

# First, we define our commands to be used
# Groupping commands
@commands.group()
async def math(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send(f"No, {ctx.subcommand_passed} does not belong to math")

# Command with type conversion and returning input to the user
@math.command()
async def multi(ctx, num_one: float, num_two: float):
    await ctx.send(num_one * num_two)

# Command with type conversion and returning input to the user
@math.command()
async def div(ctx, num_one: float, num_two: float):
    await ctx.send(num_one / num_two)

##################
# This should actually the above commands to the bot!
async def setup(bot):
    bot.add_command(math)
