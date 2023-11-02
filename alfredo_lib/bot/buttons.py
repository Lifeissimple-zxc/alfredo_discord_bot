"""
Module implements UI buttons of the bot
"""
import asyncio
import functools
import logging
from typing import Any, Callable, Coroutine, Optional

import discord
from discord.ext import commands
from discord.interactions import Interaction

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
        self.transaction_cog = self.bot.cogs[MAIN_CFG["cog_names"]["transaction"]]
        super().__init__()


class AccountView(BaseView):
    """
    Class encompasses menu buttons for account commands
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

class TransactionView(BaseView):
    """
    Class encompasses menu buttons for transaction commands
    """
    
    @discord.ui.button(label=COMMANDS_METADATA["get_transaction"]["btn_label"],
                       style=discord.ButtonStyle.blurple)
    async def get_transaction_btn(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
        "Calls get_transaction from account cog of the bot"
        await interaction.response.defer()
        try:
            await self.transaction_cog._get_transaction(ctx=self.ctx)
        except Exception as e:
            bot_logger.error("Error running button command: %s", e)

    @discord.ui.button(label=COMMANDS_METADATA["new_transaction"]["btn_label"],
                       style=discord.ButtonStyle.blurple)
    async def new_transaction_btn(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
        "Calls new_transaction from transaction cog of the bot"
        await interaction.response.defer()
        try:
            await self.transaction_cog._new_transaction(ctx=self.ctx)
        except Exception as e:
            bot_logger.error("Error running button command: %s", e)
    
    @discord.ui.button(label=COMMANDS_METADATA["delete_transaction"]["btn_label"],
                       style=discord.ButtonStyle.blurple)
    async def delete_transaction_btn(self, interaction: discord.Interaction,
                                     button: discord.ui.Button):
        "Calls delete_transaction from transaction cog of the bot"
        await interaction.response.defer()
        try:
            await self.transaction_cog._delete_transaction(ctx=self.ctx)
        except Exception as e:
            bot_logger.error("Error running button command: %s", e)
    
    @discord.ui.button(label=COMMANDS_METADATA["transaction_to_sheet"]["btn_label"],
                       style=discord.ButtonStyle.blurple)
    async def transaction_to_sheet_btn(self, interaction: discord.Interaction,
                                       button: discord.ui.Button):
        "Calls transaction_to_sheet from transaction cog of the bot"
        await interaction.response.defer()
        try:
            await self.transaction_cog._transaction_to_sheet(ctx=self.ctx)
        except Exception as e:
            bot_logger.error("Error running button command: %s", e)


class TransactionButton(discord.ui.Button):
    """
    Class implements a ui button used to transaction category
    """
    def __init__(self,
                 label: str,
                 category_id: int,
                 data_container: dict,
                 style: Optional[discord.ButtonStyle] = None):
        """
        Instantiates a button
        """
        if style is None:
            style = discord.ButtonStyle.green
        super().__init__(label=label, style=style)
        self.category_id = category_id
        self.data_container = data_container

    async def callback(self, interaction: discord.interactions.Interaction):
        """
        Custom callback that records clicked category to the dict
        """
        await interaction.response.defer()
        self.data_container["category_id"] = self.category_id
        await interaction.followup.send(
            f"You have chosen: {self.label}"
        )
        await interaction.edit_original_response(view=None)


class TransactionCategoryView(discord.ui.View):
    """
    Class implements a custom view to use with instances of TransactionButton
    """
    def __init__(self, timeout: int, ctx: commands.Context):
        """
        Instantiates the class
        """
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.is_done = False

    async def on_timeout(self):
        """
        Parent on_timeout override to flush buttons from the ui
        """
        bot_logger.debug("View timed out")
        self.stop()
        bot_logger.debug("Stopped view")
        self.is_done = True

     



    

