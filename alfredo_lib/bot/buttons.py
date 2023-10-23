import functools
import logging
from typing import Callable

import discord
from discord.ext import commands

from alfredo_lib import MAIN_CFG

bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])


def defer_decorator(interaction: discord.Interaction):
    """
    Calls interaction.response.defer() after calling the wrapped callable
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            await interaction.response.defer()
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class BaseView(discord.ui.View):
    """
    Class encompasses a base view for alfredo
    """
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        "Instantiates the view"
        self.bot = bot
        self.ctx = ctx
        super().__init__()

class AccountView(BaseView):
    """
    Class encompasses account menu
    """
    @discord.ui.button(label="Register", 
                       style=discord.ButtonStyle.blurple)
    async def account_register(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
        "Calls register from the account cog of the bot"
        await (self.bot.cogs[MAIN_CFG["cog_names"]["account"]]
                ._register(ctx=self.ctx))
        await interaction.response.defer()

    @discord.ui.button(label="Show Account Data", 
                       style=discord.ButtonStyle.blurple)
    async def account_show_data(self, interaction: discord.Interaction,
                                button: discord.ui.Button):
        await interaction.response.send_message("Showed Data")
    
    @discord.ui.button(label="Prepare Sheet", 
                       style=discord.ButtonStyle.blurple)
    async def account_prepare_sheet(self, interaction: discord.Interaction,
                                    button: discord.ui.Button):
        await interaction.response.send_message("Prepared Sheet")
    
    @discord.ui.button(label="Update User Data",
                       style=discord.ButtonStyle.blurple)
    async def account_update_data(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
        await interaction.response.send_message("Updated User Data")

    


class TransactionView:
    """
    Class encompasses 
    """
    # Shows transaction commands and invokes them if needed


class StartView(discord.ui.View):
    """
    Class implements start menu
    """
    # Shows account and transaction commands
    @discord.ui.button(label="Account", 
                       style=discord.ButtonStyle.blurple)
    async def account(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=AccountView())
        
    # @discord.ui.button(label="Transaction", 
    #                    style=discord.ButtonStyle.blurple)
    # async def transaction(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     await interaction.response.send_message(view=TransactionView())
    

