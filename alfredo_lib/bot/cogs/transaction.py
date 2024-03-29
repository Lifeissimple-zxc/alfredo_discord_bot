"""
Module implements transaction-realted commands for alfredo
"""
import asyncio
import logging

import polars as pl
from discord.ext import commands
from sqlalchemy import engine

from alfredo_lib import COMMANDS_METADATA, MAIN_CFG
from alfredo_lib.alfredo_deps import cache, google_sheets_gateway, validator
from alfredo_lib.bot import buttons, ex
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

    async def _get_transaction(self, ctx: commands.Context):
        """
        Actual get_transaction implementation
        """
        bot_logger.debug("Command invoked")
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=ctx.author.id)
        if e is not None:
            raise ex.UserNotRegisteredError(str(e))
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

    @commands.command(name=COMMANDS_METADATA["get_transaction"]["name"],
                      aliases=COMMANDS_METADATA["get_transaction"]["aliases"],
                      help=COMMANDS_METADATA["get_transaction"]["help"])
    async def get_transaction(self, ctx: commands.Context) -> tuple:
        """
        Fetches a user's ongoing transaction if there is one
        """
        await self._get_transaction(ctx=ctx)

    @staticmethod
    async def __poll_on_view_id_input(view: buttons.TransactionCategoryView,
                                      data_container: dict):
        bot_logger.debug("Polling on input view provision")
        while True:
            if "category_id" in data_container:
                bot_logger.debug("Input provided before timeout")
                return
            elif view.is_done and "category_id" not in data_container:
                raise asyncio.TimeoutError
            await asyncio.sleep(1)
    
    @staticmethod
    def _category_data_to_category_view(categories: dict,
                                        ctx: commands.Context,
                                        data_container: dict) -> buttons.TransactionCategoryView:
        view = buttons.TransactionCategoryView(timeout=MAIN_CFG["input_prompt_timeout"],
                                               ctx=ctx)
        bot_logger.debug("Instantiated view")
        for cat_id, cat_name in categories.items():
            view.add_item(
                buttons.TransactionButton(
                    label=cat_name,
                    category_id=cat_id,
                    data_container=data_container
                )
            )
        bot_logger.debug("Added view buttons")
        return view
    
    async def _collect_category_id(self, ctx: commands.Context, categories: dict,
                                   data_container: dict):
        """
        Shows categories as buttons for users to select
        """
        view = self._category_data_to_category_view(categories=categories, ctx=ctx,
                                                    data_container=data_container)
        await ctx.message.author.send("Choose category", view=view)
        await self.__poll_on_view_id_input(view=view, data_container=data_container)
    
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
        transaction = {}
        await self._collect_category_id(ctx=ctx, categories=categories,
                                        data_container=transaction)
        tr_data = await self.get_input(
            ctx=ctx, command=command, model="transaction",
            rec_discord_id=False, include_extra=True
        )
        tr_data = {**transaction, **tr_data}
        # Add extra metadata
        tr_data["user_id"] = user.user_id
        tr_data["currency"] = user.currency
        bot_logger.debug("Transaction data prepared %s", tr_data)
        # Write to db
        msg, e = self.lc.create_transaction(tr_data)
        if e is not None:
            bot_logger.error("new_transaction() failed: %s", e)
        await ctx.author.send(msg)

    async def _new_transaction(self, ctx: commands.Context):
        """
        Actual new_transaction implementation
        """
        bot_logger.debug("Command invoked")
        command = "new_transaction"
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=ctx.author.id)
        if e is not None:
            raise ex.UserNotRegisteredError(str(e))
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

    @commands.command(name=COMMANDS_METADATA["new_transaction"]["name"],
                      aliases=COMMANDS_METADATA["new_transaction"]["aliases"],
                      help=COMMANDS_METADATA["new_transaction"]["help"])
    async def new_transaction(self, ctx: commands.Context):
        """Creates a new transaction row in alfredo's backend db"""
        await self._new_transaction(ctx=ctx)
    
    async def _delete_transaction(self, ctx: commands.Context):
        """
        Actual delete_transaction implementation
        """
        bot_logger.debug("Command invoked")
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=ctx.author.id)
        if e is not None:
            raise ex.UserNotRegisteredError(str(e))
        # Get transaction as ORM obj
        transaction = self.lc.get_user_transactions(user=user)
        if not transaction:
            await ctx.author.send("No transactions located, can't delete")
            return
        # Delete transaction using cache class methods
        # TODO this is hacky, refactor
        tr_row = (
            self.lc.sesh.query(models.Transaction)
            .filter(models.Transaction.transaction_id==transaction._asdict()["transaction_id"])
            .first()
        )
        e = self.lc.delete_row(tr_row)
        if e is not None:
            msg = f"Error deleting transaction row: {e}"
            bot_logger.error(msg)
            await ctx.author.send(msg)
            return
        await ctx.author.send("Transaction deletion - success!")
    
    @commands.command(name=COMMANDS_METADATA["delete_transaction"]["name"],
                      aliases=COMMANDS_METADATA["delete_transaction"]["aliases"],
                      help=COMMANDS_METADATA["delete_transaction"]["help"])
    async def delete_transaction(self, ctx: commands.Context):
        """
        Deletes ongoing (not yet sent to sheets) transaction 
        """
        await self._delete_transaction(ctx=ctx)

    @commands.command(name=COMMANDS_METADATA["update_transaction"]["name"],
                      aliases=COMMANDS_METADATA["update_transaction"]["aliases"],
                      help=COMMANDS_METADATA["update_transaction"]["help"])
    async def update_transaction(self, ctx: commands.Context,
                                 field: str, data: str):
        """
        Updates transaction using user input
        """
        bot_logger.debug("Command invoked")
        # Check if caller discord id is in db
        user, e = self.lc.get_user(discord_id=ctx.author.id)
        if e is not None:
            raise ex.UserNotRegisteredError(str(e))
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
        df = df.with_columns(
            (pl.from_epoch(**MAIN_CFG["google_sheets"]["transaction_tab"]["ts_conversion"])
             .cast(pl.Utf8))).with_columns(rename_exp)
        bot_logger.debug("Renamed columns for the sheet & converted ts: %s", df)
        df = df.select(
            [value["sheet_name"] for value in sheet_schema.values()]
        )
        bot_logger.debug("DF to paste to sheet: %s", df)
        return df
    
    async def _transaction_to_sheet(self, ctx: commands.Context):
        """
        Implements transaction_to_sheet
        """
        bot_logger.debug("Command invoked")
        user, e = self.lc.get_user(discord_id=ctx.author.id)
        if e is not None:
            raise ex.UserNotRegisteredError(str(e))
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
    
    @commands.command(name=COMMANDS_METADATA["transaction_to_sheet"]["name"],
                      aliases=COMMANDS_METADATA["transaction_to_sheet"]["aliases"],
                      help=COMMANDS_METADATA["transaction_to_sheet"]["help"])
    async def transaction_to_sheet(self, ctx: commands.Context):
        """
        Sends cached transaction to sheet and removes if from db on success
        """
        await self._transaction_to_sheet(ctx=ctx)
        


