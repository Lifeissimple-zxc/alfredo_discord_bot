"""
Module implements transaction-realted commands for alfredo
"""
import logging

import polars as pl
from discord.ext import commands

from alfredo_lib import MAIN_CFG
from alfredo_lib.alfredo_deps import cache, google_sheets_gateway, validator
from alfredo_lib.bot import ex
from alfredo_lib.bot.cogs.base import base_cog
from alfredo_lib.local_persistence import models

bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])

class TransactionCog(base_cog.CogHelper, name="transaction"):
    """Encapsulates commands related to transactions"""

    def __init__(self, bot: commands.Bot,
                 local_cache: cache.Cache,
                 input_controller: validator.InputController,
                 sheets: google_sheets_gateway.GoogleSheetAsyncGateway):
        """
        Instantiates the class
        """
        super().__init__(bot=bot, local_cache=local_cache,
                         input_controller=input_controller,
                         sheets=sheets)
        
    @commands.command(aliases=("get_tr",))
    async def get_transaction(self, ctx: commands.Context) -> tuple:
        """
        Fetches a user's ongoing transaction if there is one
        """
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=discord_id)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        transaction = self.lc.get_user_transactions(
            user=user, parse_mode=cache.ROW_PARSE_MODE_STRING
        ) 
        if transaction:
            await ctx.author.send(
                MAIN_CFG["messages"]["ong_transaction_exists"].format(transaction=transaction)
            )
            return
        await ctx.author.send("No ongoing transactions located")

    async def _create_transaction(self, ctx: commands.Context,
                                  user: models.User, command: str):
        """
        ### Creates a new transaction from scratch my prompting user for data
        """
        tr_data = await self.get_input(ctx=ctx, command=command, model="transaction",
                                       rec_discord_id=False, include_extra=True)
        # DO we check user input somehow here??? TODO
        tr_data["user_id"] = user.user_id
        tr_data["currency"] = user.currency
        bot_logger.debug("Transaction data prepared %s", tr_data)
        # Write to db
        msg, e = self.lc.create_transaction(tr_data)
        if e is not None:
            bot_logger.error("new_transaction() failed: %s", e)
        await ctx.author.send(msg)

    @commands.command(aliases=("tr",))
    async def new_transaction(self, ctx: commands.Context):
        """Adds a new transaction to the sheet saved by the user"""
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        command = "new_transaction"
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=discord_id)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        transaction = self.lc.get_user_transactions(
            user=user, parse_mode=cache.ROW_PARSE_MODE_STRING
        )
        bot_logger.debug("Fetched user transaction")
        if transaction:
            await ctx.author.send(
                # TODO Specify commands to be called here
                "Transaction is in progress. Delete or Update using commands."
            )
            return
        await self._create_transaction(ctx, user=user, command=command)
    
    @commands.command(aliases=("del_tr",))
    async def delete_ong_transaction(self, ctx: commands.Context):
        """
        ### Deletes ongoing transaction 
        """
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=discord_id)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        # Get transaction as ORM obj
        transaction = self.lc.get_user_transactions(user=user)
        if not transaction:
            await ctx.author.send("No transactions located, can't delete")
            return
        # Delete transaction using cache class methods
        e = self.lc.delete_row(transaction)
        if e is not None:
            msg = f"Error deleting transaction row: {e}"
            bot_logger.error(msg)
            await ctx.author.send(msg)
            return
        await ctx.author.send("Transaction deletion - success!")

    @commands.command(aliases=("upd_tr",))
    async def update_transaction(self, ctx: commands.Context,
                                 field: str, data: str):
        """
        Updates transaction using user input
        """
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=discord_id)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        # Check if field is valid
        allowed_fields = self.ic.create_prompt_keys(model="transaction",
                                                    mode="all")
        if field not in allowed_fields and field is not None:
            # TODO this should be handled in a generic fashion
            await ctx.author.send(f"{field} can't be updated by users")
            return 
        # Perform type conversion if needed
        data, e = self.ic.parse_input(model="transaction",
                                               field=field, data=data)
        if e is not None:
            # TODO this should be handled in a generic fashion too
            await ctx.author.send(f"{data} is not valid for {field}: {e}")
            return
        # Fetch transation that to apply updates to
        transaction = self.lc.get_user_transactions(user=user)
        if not transaction:
            # TODO Generic handling?
            await ctx.author.send("No transactions located, can't update")
            return
        # Call cache method to update transation
        e = self.lc.update_transaction(update={field: data},
                                           transaction=transaction)
        if e is not None:
            msg = f"DB Data update failed for transaction: {e}"
            bot_logger.error(msg)
            await ctx.author.send(msg)
        await ctx.author.send("Transaction data updated!")

    @commands.command(aliases=("tts",))
    async def transaction_to_sheet(self, ctx: commands.Context):
        """
        Sends cached transaction to sheet and removes if from cache on success
        """
        bot_logger.debug("Command invoked")
        discord_id = ctx.author.id
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=discord_id)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        # Check for base fields presence TODO
        transaction = self.lc.get_user_transactions(user=user)
        if not transaction:
            await ctx.author.send("No transactions located, can't send to sheet")
            return
        df = self.lc.parse_db_row(row=transaction, mode=cache.ROW_PARSE_MODE_DF)
        # TODO move this schema creation & colrenaming to a separate func
        sheet_schema = MAIN_CFG["google_sheets"]["transaction_tab"]["schema"]
        cols_to_sheet = list(sheet_schema.keys())
        # Take a subset
        df = df.select(cols_to_sheet)
        bot_logger.debug("Prepared data to send to sheet: %s", df)
        # Rename cols
        rename_exp = [pl.col(key).alias(value["sheet_name"])
                      for key, value in sheet_schema.items()]
        df = df.with_columns(rename_exp)
        bot_logger.debug("Renamed columns for the sheet: %s", df)
        sheet_cols = [value["sheet_name"] for value in sheet_schema.values()]
        df = df.select(sheet_cols)
        bot_logger.debug("DF to paste to sheet: %s", df)
        # Append to sheet
        _, e = await self.sheets.append_data_native(
            sheet_id=user.spreadsheet, data=df,
            tab_name=MAIN_CFG["google_sheets"]["transaction_tab"]["name"],
            row_limit=MAIN_CFG["google_sheets"]["transaction_tab"]["row_limit"]
        )
        # Check for error
        if e is not None:
            msg = f"Error appending to the sheet. Please retry the command: {e}"
            bot_logger.error(msg)
            return
        e = self.lc.delete_row(transaction)
        if e is not None:
            msg = f"Error deleting transaction row: {e}"
            bot_logger.error(msg)
            await ctx.author.send(msg)
            return
        await ctx.author.send("Transaction pasted to the sheet!")


