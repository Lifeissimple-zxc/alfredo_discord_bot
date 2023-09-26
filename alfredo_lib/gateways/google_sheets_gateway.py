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
    
    async def _tab_name_to_tab_id(self, sheet_id: str, tab_name: str):
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
            return None, ValueError(msg)
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

    async def clear_data(self, sheet_id: str, tab_name: str, cell_range: str):
        """
        TODO return type hint
        Method for deleting cell data. Does not delete rows.
        """
        sheet_range = f"{tab_name}!{cell_range}"
        req = self.sheet_service.spreadsheets.values.clear(
            spreadsheetId=sheet_id,
            range=sheet_range
        )
        resp = await self._make_request(req=req)
        return resp
    
    @staticmethod
    def __delete_rows_params_to_body(tab_id: str, start: int, end: int) -> dict:
        """
        Mapper converting delete rows params to a request body that Google
        api understands.
        """
        return {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": tab_id,
                            "dimension": "ROWS",
                            "startIndex": start,
                            "endIndex": end
                        }    
                    }
                }
            ]
        }
    
    async def delete_rows(self, sheet_id: str, tab_name: str, end: int,
                          start: Optional[int] = None):
        """
        TODO return type hint
        Deletes rows from a tab
        """
        if start is None:
            start = 1

        tab_id, e = await self._tab_name_to_tab_id(sheet_id=sheet_id,
                                                   tab_name=tab_name)
        if e is not None:
            bot_logger.error("Rows deletion failed. Details: %s", e)
            return None, e
        bot_logger.debug("tab %s is found in sheet %s", tab_name, sheet_id)
        req_body = self.__delete_rows_params_to_body(tab_id=tab_id,
                                                     start=start, end=end)
        bot_logger.debug("Deleting rows using body: %s", req_body)
        req = self.sheet_service.spreadsheets.batchUpdate(
            spreadsheetId=sheet_id,
            json=req_body
        )
        resp = await self._make_request(req=req)
        return resp, None
    
    @staticmethod
    def _df_to_update_range(data: pl.DataFrame, start_row: int):
        """
        Creates update range in AA:ZZ notation based on data & start row
        """
        return f"A{start_row}:{num_to_sheet_range(len(data.columns))}"
    
    @staticmethod
    def __paste_params_to_body(value_range: dict):
        """
        Mapper converting paste params to request body
        """
        #TODO make sure it's used or delete
        return {
            "valueInputOption": "RAW",
            "data": value_range,
            "includeValuesInResponse": False,
            "responseValueRenderOption": "UNFORMATTED_VALUE",
            "responseDateTimeRenderOption": "SERIAL_NUMBER"
        }
    
    async def paste_data(self, sheet_id: str, tab_name: str,
                         start_row: int, data: pl.DataFrame,
                         include_header: Optional[bool] = None):
        """
        Pastes data to the sheet. Overrides data already existing in the sheet.
        :param sheet_id: id of the spreadsheet
        :param tab_name: tab where to paste
        :param start_row: where where we paste the data
        :param data: data to paste to the sheet
        """
        if include_header is None:
            include_header = True
        #TODO type hints 
        # Delete already existing data before pasting
        paste_range = self._df_to_update_range(data=data, start_row=start_row)
        # naive assumption, no resp check
        await self.clear_data(sheet_id=sheet_id, tab_name=tab_name,
                              cell_range=paste_range)
        
        # TODO abstract to a function!
        # Convert df to a list of lists bc google expects an array
        data_update = data.to_numpy().tolist()
        # TODO make it optional, only when header is included?
        if include_header:
            data_update = [data.columns] + data_update
        # Convert data to value range
        sheet_range = f"{tab_name}!{paste_range}"
        value_range = {
            "range": sheet_range,
            "majorDimension": "ROWS",
            "values": data_update
        } 
        # Convert data to a list of lists
        # TODO refactor this a bit more!
        bot_logger.debug("Pasting data to %s using range %s",
                         tab_name, paste_range)
        req = self.sheet_service.spreadsheets.values.update(
            spreadsheetId=sheet_id,
            range=sheet_range,
            json=value_range,

            valueInputOption="RAW",
            includeValuesInResponse=False,
            responseValueRenderOption="UNFORMATTED_VALUE",
            responseDateTimeRenderOption="SERIAL_NUMBER"
        )
        return await self._make_request(req=req)
    
    @staticmethod
    def _compute_number_of_rows_to_drop(current_len: int, new_len: int,
                                        row_limit: int):
        """
        Computes number of rows to delete to comply with row_limit
        """
        bot_logger.debug("Computing how many rows to drop")
        bot_logger.debug("current: %s, new: %s, limit %s",
                         current_len, new_len, row_limit)
        to_delete = 0
        if (tot_len := (current_len + new_len)) > row_limit:
            # End of the range is exclusive so doing +1
            to_delete = tot_len - row_limit
        return to_delete

    async def append_data(self, sheet_id: str, tab_name: str,
                          data: pl.DataFrame, row_limit: int):
        # TODO row limit should be pulled from config
        """
        ### Appends data data accounting for row_limit not to overload sheet
        :param TODO:
        :return: TODO
        """
        # Get current data + check for errorrs
        curr_data = await self.read_sheet(sheet_id=sheet_id,
                                          tab_name=tab_name,
                                          as_df=True)
        # TODO error check (read_sheet needs to be updated)
        current_len = len(curr_data)
        new_len = len(data)
        to_delete = self._compute_number_of_rows_to_drop(
            current_len=current_len, new_len=new_len,
            row_limit=row_limit
        )
        bot_logger.debug("Have to delete %s rows", to_delete)

        if to_delete > 0:
            # End of the range is exclusive so doing +1
            _, _ = await self.delete_rows(sheet_id=sheet_id,
                                          tab_name=tab_name,
                                          end=to_delete+1)
            # Add one more row here TODO
        # To delete is inflated, correcting here
        # TODO 26 Sept continue from the above :UP:
        paste_pos = current_len - to_delete + 2
        bot_logger.debug("Appending at %s", paste_pos)
        return await self.paste_data(sheet_id=sheet_id, tab_name=tab_name,
                                     start_row=paste_pos, data=data,
                                     include_header=False)


        


    
        






# TODO unite it alll under a class
# TODO worksheet???


# def sheet_to_df():
#     pass

# def paste_rows():
#     pass

# def append_rows():
#     pass