import functools
import logging
from typing import Callable

import discord
from discord.ext import commands

from alfredo_lib import COMMANDS_METADATA, MAIN_CFG

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
        self.account_cog = self.bot.cogs[MAIN_CFG["cog_names"]["account"]]
        super().__init__()


class AccountView(BaseView):
    """
    Class encompasses account menu
    """ 

    @discord.ui.button(label=COMMANDS_METADATA["register"]["btn_label"], 
                       style=discord.ButtonStyle.blurple)
    async def register_btn(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        "Calls register from the account cog of the bot"
        await interaction.response.defer()
        try:
            await self.account_cog._register(ctx=self.ctx)
        except Exception as e:
            bot_logger.error("Error running button command: %s", e)

    @discord.ui.button(label=COMMANDS_METADATA["whoami"]["btn_label"], 
                       style=discord.ButtonStyle.blurple)
    async def whoami_btn(self, interaction: discord.Interaction,
                         button: discord.ui.Button):
        "Calls whoami from the account cog of the bot"
        await interaction.response.defer()
        try:
            await self.account_cog._whoami(ctx=self.ctx)
        except Exception as e:
            bot_logger.error("Error running button command: %s", e)

    @discord.ui.button(label=COMMANDS_METADATA["prepare_sheet"]["btn_label"], 
                       style=discord.ButtonStyle.blurple)
    async def prepare_sheet_btn(self, interaction: discord.Interaction,
                                    button: discord.ui.Button):
        "Calls prepare_sheet from account cog of the bot"
        await interaction.response.defer()
        try:
            await self.account_cog._prepare_sheet(ctx=self.ctx)
        except Exception as e:
            bot_logger.error("Error running button command: %s", e)
    
    @discord.ui.button(label=COMMANDS_METADATA["update_user_data"]["btn_label"],
                       style=discord.ButtonStyle.blurple)
    async def update_user_data_btn(self, interaction: discord.Interaction,
                                   button: discord.ui.Button):
        "Calls update_user_data from account cog of the bot"
        await interaction.response.defer()
        try:
            await self.account_cog._update_user_data(ctx=self.ctx)
        except Exception as e:
            bot_logger.error("Error running button command: %s", e)

    


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
    

