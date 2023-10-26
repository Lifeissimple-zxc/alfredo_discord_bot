"""
Module implements utility functions relied on by account and transaction cogs
"""
import asyncio
import logging
from typing import Optional, Union

import discord
import polars as pl
from discord.ext import commands

from alfredo_lib import MAIN_CFG
from alfredo_lib.alfredo_deps import cache, google_sheets_gateway, validator

bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])

class CogHelper(commands.Cog):
    """Encapsulates methods that COGS rely on"""

    #TODO objects in this init should be singletons instead
    def __init__(self, bot: commands.Bot,
                 local_cache: cache.Cache,
                 input_controller: validator.InputController,
                 sheets: google_sheets_gateway.GoogleSheetAsyncGateway):
        """
        Instantiates the helper class
        """
        self.bot = bot
        self.lc = local_cache
        self.ic = input_controller
        self.sheets = sheets

    @staticmethod
    def check_ctx(msg: discord.Message, author: discord.User):
        """
        Helper that checks for message and channel being a DM
        """
        return msg.author == author and msg.channel == author.dm_channel
    
    async def _ask_user_for_data(
        self,
        ctx: commands.Context,
        input_container: dict,
        model: str,
        mode: Optional[str] = None
    ) -> dict:
        """
        Prompts for data either using input_schemas[model][mode] of input_controller
        """
        # Quick mode check to avoid doing dowstream & save computation time
        mode = mode or "base"
        if mode not in ("base", "extra"):
            bot_logger.error("Bad mode supplied: %s", mode)
            return {}
        # Making a copy not to do in-place modifications!
        res = input_container.copy()

        prompt_keys = self.ic.input_schemas[model][mode]
        
        for key in prompt_keys:
            await ctx.message.author.send(f"Please enter your {key}!")
            
            try:
                resp = await self.bot.wait_for(
                    "message",
                    check=lambda message: self.check_ctx(message, ctx.author),
                    timeout=MAIN_CFG["input_prompt_timeout"]
                )
                data = resp.content
                bot_logger.debug("Parsing %s...", key)
                data, e = self.ic.parse_input(model=model,
                                              field=key, data=data)
                if e is not None:
                    await ctx.message.author.send(f"{key} cannot be parsed: {e}")
                    if mode == "base":
                        # Returning bc 1 missing base field is a problem
                        return res, None
                    else:
                        continue
                # Special handling & parsing
                if key == "spreadsheet":
                    # TODO duplicate code here
                    data, e = self.ic.sheet_input_to_sheet_id(sheet_input=data)
                    if e is not None:
                        await ctx.message.author.send(f"{key} cannot be parsed: {e}")
                        return res, None


            except asyncio.TimeoutError as e:
                await ctx.message.author.send(
                    MAIN_CFG["error_messages"]["prompt_timeout"]
                )
                return res, e

            res[key] = data
        return res, None
    
    async def get_input(self, ctx: commands.Context, command: str,
                        model: str, include_extra: Optional[bool] = None,
                        rec_discord_id: Optional[bool] = None) -> dict:
        """
        ### Continuously prompts for user input.
        Stores user responsed in a dict.
        :param rec_discord_id: True means auto adding a user's discord_id to the input 
        """

        if rec_discord_id is None:
            rec_discord_id = True
        if include_extra is None:
            include_extra = True

        bot_logger.debug("Prompting user %s for %s command data",
                         ctx.author.id, command)

        res = {}
        if rec_discord_id:
            res["discord_id"] = ctx.author.id
        
        res, e = await self._ask_user_for_data(
            ctx=ctx, input_container=res,
            mode="base", model=model
        )
        # This happends due to timeout so returning no data makes sense???
        if e is not None:
            return {}
        if include_extra:
            res, e = await self._ask_user_for_data(
                ctx=ctx, input_container=res,
                mode="extra", model=model
            )
           
        bot_logger.debug("Collected data for command %s: %s", command, res)
        return res
    
    async def _format_sheet(self, sheet_id: str) -> Union[None, Exception]:
        """
        Prepares spreadsheet where transactions will be appended
        """
        # Get sheet data
        sp, e = await self.sheets.get_sheet_properties(sheet_id=sheet_id)
        if e is not None:
            bot_logger.error("Error fetching sheet properties: %s", e)
        # Check if tab is there
        sheet_data = self.sheets.parse_raw_properties(sheet_properties=sp)
        tab_name = MAIN_CFG["google_sheets"]["transaction_tab"]["name"]
        tab_schema = MAIN_CFG["google_sheets"]["transaction_tab"]["schema"]
        hdr_index = MAIN_CFG["google_sheets"]["hdr_index"]
        header_row = [value["sheet_name"] for value in tab_schema.values()]
        # Adding if not present
        if tab_name not in sheet_data.keys():
            bot_logger.debug("%s sheet does not have %s tab",
                             sheet_id, tab_name)
            _, e = await self.sheets.add_sheet(sheet_id=sheet_id,
                                               title=tab_name)
            if e is not None:
                return e
            bot_logger.debug("Added %s tab", tab_name)
            df = pl.DataFrame(data=[header_row]).transpose()

            _, e = await self.sheets.paste_data(sheet_id=sheet_id,
                                                tab_name=tab_name,
                                                start_row=hdr_index,
                                                data=df, include_header=False)
            if e is not None:
                return e
            bot_logger.debug("Added %s row to the tab", df)
            return
        # Check if header matches schema
        sheet_df, e = await self.sheets.read_sheet(sheet_id=sheet_id,
                                                   tab_name=tab_name,
                                                   header_rownum=hdr_index,
                                                   as_df=True)
        if e is not None:
            return e
        bot_logger.debug("Fetched %s data from the sheet", sheet_df)
        sheet_header = list(sheet_df.columns)
        bot_logger.debug("Sheet header: %s, needed row: %s",
                         sheet_header, header_row)
        if sorted(sheet_header) != sorted(header_row):
            msg = f"Sheet {sheet_id} has a malformed {tab_name} tab."
            msg = f"{msg} Paste {header_row} to the first row and try again."
            return ValueError(msg)
