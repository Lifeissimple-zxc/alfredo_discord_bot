"""
Module implements transaction-realted commands for alfredo
"""
import json
import logging

import polars as pl
from discord.ext import commands
from sqlalchemy import engine

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
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=ctx.author.id)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        try:
            transaction = self.lc.get_user_transactions(
                user=user, parse_mode=cache.ROW_PARSE_MODE_STRING
            )
        except Exception as e:
            bot_logger.error("Error getting transactions: %s", e)
            raise e
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
        categories, e = self.lc.get_categories(
            parse_mode=cache.ROW_PARSE_MODE_DICT
        )
        if e is not None:
            await ctx.author.send(
                f"Can't create transaction. No categories data in db: {e}"
            )
            return
        
        await ctx.author.send(
            f"Categories available: {json.dumps(obj=categories, indent=4)}"
        )
        tr_data = await self.get_input(
            ctx=ctx, command=command, model="transaction",
            rec_discord_id=False, include_extra=True
        )
        
        # User can give a valid int for category 
        print("Dict keys", type(list(categories.keys())[0]))
        if (cat_id := tr_data["category_id"]) not in categories.keys():
            await ctx.author.send(f"Category id {cat_id} is invalid")
            return
        # Add extra metadata
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
        command = "new_transaction"
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=ctx.author.id)
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
        Deletes ongoing (not yet sent to sheets) transaction 
        """
        bot_logger.debug("Command invoked")
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=ctx.author.id)
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
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=ctx.author.id)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        # Check if field is valid
        allowed_fields = self.ic.create_prompt_keys(model="transaction",
                                                    mode="all")
        if field not in allowed_fields and field is not None:
            # TODO this should be handled in a generic fashion
            raise ex.WrongUpdateFieldInputError(
                f"{field} can't be updated by users"
            )
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

    def _ts_row_to_sheet_df(self, transaction: engine.row.Row,
                            sheet_schema: dict) -> pl.DataFrame:
        """
        Converts transaction row from db to a df that can be pasted to sheet.
        """
        bot_logger.debug("Starting data preparation for pasting to sheets")
        df = self.lc.parse_db_row(row=transaction, mode=cache.ROW_PARSE_MODE_DF)
        rename_exp = [pl.col(key).alias(value["sheet_name"])
                      for key, value in sheet_schema.items()]
        df = df.with_columns(rename_exp)
        bot_logger.debug("Renamed columns for the sheet: %s", df)
        df = df.select(
            [value["sheet_name"] for value in sheet_schema.values()]
        )
        bot_logger.debug("DF to paste to sheet: %s", df)
        return df
    
    @commands.command(aliases=("tts",))
    async def transaction_to_sheet(self, ctx: commands.Context):
        """
        Sends cached transaction to sheet and removes if from cache on success
        """
        bot_logger.debug("Command invoked")
        user, e = self.lc.get_user(discord_id=ctx.author.id)
        if e is not None:
            raise ex.UserNotRegisteredError(msg=str(e))
        transaction = self.lc.get_user_transactions(user=user)
        if not transaction:
            await ctx.author.send("No transactions located, can't send to sheet")
            return
        
        try:
            df = self._ts_row_to_sheet_df(
                transaction=transaction,
                sheet_schema=MAIN_CFG["google_sheets"]["transaction_tab"]["schema"]
            )
        except Exception as e:
            msg = f"Unexpected error when preparing a sheet update: {e}. Admin contact needed."
            bot_logger.error(msg)
            await ctx.author.send(msg)
            return
        
        bot_logger.debug("DF to paste to sheet: %s", df)
        _, e = await self.sheets.append_data_native(
            sheet_id=user.spreadsheet, data=df,
            tab_name=MAIN_CFG["google_sheets"]["transaction_tab"]["name"],
            row_limit=MAIN_CFG["google_sheets"]["transaction_tab"]["row_limit"]
        )
        if e is not None:
            msg = f"Error appending to the sheet. Please retry the command: {e}"
            bot_logger.error(msg)
            return
        e = self.lc.delete_row(user.transactions[0])
        
        if e is not None:
            msg = f"Error deleting transaction row: {e}. Please delete manually by calling delete command."
            bot_logger.error(msg)
            await ctx.author.send(msg)
            return
        
        await ctx.author.send("Transaction pasted to the sheet!")


