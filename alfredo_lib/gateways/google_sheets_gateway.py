"""
Module implements an async Gsheet Gateway
"""
import json
import logging
from typing import Optional

import aiogoogle
import polars as pl
from aiogoogle.auth import creds

from alfredo_lib import MAIN_CFG

bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])

SHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def num_to_sheet_range(num: int) -> str:
    """
    Mapper converting col number to a spreadsheet column
    """
    bot_logger.debug("Preparing sheet range from num %s", num)
    rem, layers = num % 26, num // 26
    bot_logger.debug("Rem: %s, layers: %s", rem, layers)
    first = ""
    if layers > 0:
        first = chr(65+layers-1)
    return f"{first}{chr(65+rem-1)}"

class GoogleSheetAsyncGateway:
    """
    Implements an async class for interacting with Gsheet API.
    It relies on a service account for authentication.
    """
    def __init__(self, service_acc_path: str):
        """
        Instantiates the gateway
        """
        self.raw_creds = self._new_creds(service_acc_path=service_acc_path)
        bot_logger.debug("Prepared raw Service Acc credentials")
        self.gsheet_client = aiogoogle.Aiogoogle(
            service_account_creds=self.raw_creds
        )
        bot_logger.debug("Instantiated GSheet Async Gateway")

    @staticmethod
    def _new_creds(service_acc_path: str) -> creds.ServiceAccountCreds:
        """
        Helper instantiating credentials object for Google API authentication
        """
        service_account_key = json.load(open(file=service_acc_path,
                                             encoding="utf-8",
                                             mode="r"))
        return creds.ServiceAccountCreds(scopes=SHEET_SCOPES,
                                         **service_account_key)
    
    async def discover_sheet_service(self, api_version: str):
        """
        ### Discovers sheets api service
        Outside of __init__ bc it needs an await
        """
        self.sheet_service = await self.gsheet_client.discover(
            api_name="sheets",
            api_version=api_version
        )
        bot_logger.debug("Performed %s sheets service discovery", api_version)

    async def _make_request(self, req: aiogoogle.models.Request):
        """
        Abstraction to simplifiy how we send requests to Gsheet backend
        """
        # TODO exceptions
        # TODO ratelimitting!!!
        # TODO errors for API requests
        resp = await self.gsheet_client.as_service_account(req)
        return resp
    
    async def get_sheet_properties(self, sheet_id: str):
        """
        Fetches sheet data via a get request
        """
        bot_logger.debug("Requesting sheet metadata")
        req = self.sheet_service.spreadsheets.get(spreadsheetId=sheet_id,
                                                  includeGridData=False)
        bot_logger.debug("Prepared request")
        return await self._make_request(req=req)
    
    async def tab_name_to_tab_id(self, sheet_id: str, tab_name: str):
        """
        Mapper converting tab name to tab id
        """
        sheet_properties = await self.get_sheet_properties(sheet_id=sheet_id)
        bot_logger.debug("Got sheet properties from the API")
        all_tabs_data = {
            tab["properties"]["title"]: tab["properties"]
            for tab in sheet_properties["sheets"]
        }
        bot_logger.debug("Rearranged tab data to a simpler dict for vlookups")
        tab = all_tabs_data.get(tab_name, None)
        if tab is None:
            msg = f"No tab {tab_name} is sheet {sheet_id}"
            bot_logger.debug("No tab %s is sheet %s", tab_name, sheet_id)
            return None, KeyError(msg)
        return tab["sheetId"], None
        


    @staticmethod
    def _process_sheet_response(sheet_data: list, header_rownum: int,
                                header_offset: int) -> tuple:
        """
        Splits sheet_data into header and data
        accounting for header_rownum and header_offset
        """
        header_index = header_rownum-1
        header_row = sheet_data[header_index]
        # Drop rows we want to skip based on params
        del sheet_data[header_index:header_index+1+header_offset]
        return header_row, sheet_data

    async def read_sheet(self, sheet_id: str, tab_name: str,
                         header_rownum: Optional[int] = None,
                         header_offset: Optional[int] = None,
                         as_df: Optional[bool] = None,
                         use_schema: Optional[bool] = None):
        """
        Fetches data from spreadsheet to a python dict
        """
        # Default values
        if header_rownum is None:
            header_rownum = 1
        if header_offset is None:
            header_offset = 0
        if as_df is None:
            as_df = False
        if use_schema is None:
            use_schema = False

        data_req = self.sheet_service.spreadsheets.values.get(
            spreadsheetId=sheet_id,
            range=f"{tab_name}!A:ZZ",
            majorDimension='ROWS'
        )
        bot_logger.debug("Prepared sheet reading request")
        sheet_data = await self._make_request(req=data_req)
        # 2D array with rows here
        bot_logger.debug("Received data back")
        sheet_data = sheet_data["values"]

        header, data = self._process_sheet_response(sheet_data=sheet_data,
                                                    header_rownum=header_rownum,
                                                    header_offset=header_offset)
        bot_logger.debug("Accounted for header in sheet data")
        if not as_df:
            bot_logger.debug("Returning as 2d list")
            return [header] + data
        
        # Converting to polars
        bot_logger.debug("Converting to polars")
        df = pl.DataFrame(data=data).transpose()
        df.columns = header
        if not use_schema:
            bot_logger.debug("use_schema is False, returning untyped")
            return df
        # Typecasting TODO

    async def clear_data(self, sheet_id: str, tab_name: str, cols_len: int):
        """
        TODO return type hint
        Method for overriding data. Does not delete rows.
        """
        sheet_range = f"{tab_name}!A:{num_to_sheet_range(num=cols_len)}"
        print(sheet_range)
        req = self.sheet_service.spreadsheets.values.clear(
            spreadsheetId=sheet_id,
            range=sheet_range
        )
        resp = await self._make_request(req=req)
        return resp
    
    async def delete_rows(self, sheet_id: str, tab_name: str,
                          start: Optional[int] = None,
                          end: Optional[int] = None):
        """
        TODO return type hint
        Deletes rows from a tab
        """

    
        






# TODO unite it alll under a class
# TODO worksheet???


# def sheet_to_df():
#     pass

# def paste_rows():
#     pass

# def append_rows():
#     pass