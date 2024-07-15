"""
Module implements an async Gsheet Gateway
"""
import json
import logging
from typing import Optional

import aiogoogle
import polars as pl
from aiogoogle import models as aiogoogle_models
from aiogoogle.auth import creds

from alfredo_lib import MAIN_CFG
from alfredo_lib.gateways.base import async_rps_limiter
from alfredo_lib.gateways.base.my_retry import simple_async_retry

bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])

SHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

READ_REQUEST_TYPE = "r"
WRITE_REQUEST_TYPE = "w"

class GoogleSheetRetriableError(Exception):
    """
    Custom exception class to differentiate cases worth triggering a retry
    """
    def __init__(self, msg: str, og_exception: Exception):
        "Instantiates the exception"
        super().__init__(msg)
        self.og_exception = og_exception

class GoogleSheetBadRequestError(Exception):
    """
    Custom exception class to differentiate 4XX cases
    """
    def __init__(self, msg: str, og_exception: Exception):
        "Instantiates the exception"
        super().__init__(msg)
        self.og_exception = og_exception

class GoogleSheetMapper:
    """
    Class encapsulates mappers that are used by GoogleSheetAsyncGateway
    """
    @staticmethod
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
    
    @staticmethod
    async def _tab_name_to_tab_id(sheet_id: str, tab_name: str,
                                  sheet_tabs_data: dict):
        """
        Mapper converting tab name to tab id
        """
        tab = sheet_tabs_data.get(tab_name, None)
        if tab is None:
            msg = f"No tab {tab_name} is sheet {sheet_id}"
            bot_logger.error("No tab %s is sheet %s", tab_name, sheet_id)
            return None, ValueError(msg)
        return tab["sheetId"], None
    
    @staticmethod
    def parse_raw_properties(sheet_properties: dict):
        """
        Mapper converting raw response to from Google Sheets
        to a dict of {tab_name: properties} form
        """
        return {
            tab["properties"]["title"]: tab["properties"]
            for tab in sheet_properties["sheets"]
        }

    @staticmethod
    def _process_sheet_response(sheet_data: list, header_rownum: int,
                                header_offset: int) -> tuple:
        """
        Splits sheet_data into header and data
        accounting for header_rownum and header_offset
        """
        header_index = header_rownum-1
        header_row = sheet_data[header_index]
        bot_logger.debug("header row fetched: %s. Index used: %s",
                         header_row, header_index)
        # Drop rows we want to skip based on params
        del sheet_data[header_index:header_index+1+header_offset]
        return header_row, sheet_data
    
    @staticmethod
    def _delete_rows_params_to_body(tab_id: str, start: int, end: int) -> dict:
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
    
    def _df_to_update_range(self, data: pl.DataFrame, start_row: int):
        """
        Creates update range in AA:ZZ notation based on data & start row
        """
        return f"A{start_row}:{self.num_to_sheet_range(len(data.columns))}"
    
    @staticmethod
    def _sheet_update_and_range_to_value_range(sheet_range: str,
                                               data_update: list):
        """
        Mapper converting sheet data and data update
        to a value range JSON body
        """
        return {
            "range": sheet_range,
            "majorDimension": "ROWS",
            "values": data_update
        }
    
    @staticmethod
    def _df_to_sheet_update(data: pl.DataFrame, include_header: bool) -> list:
        """
        Mapper converting df to a 2d list that Google understands
        """
        data_update = data.to_numpy().tolist()
        if include_header:
            data_update = [data.columns] + data_update
        return data_update
    
    @staticmethod
    def _add_sheet_params_to_add_sheet_body(title: str, rows: int,
                                            columns: int):
        """
        Creates a body for addShet request
        """
        return {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": title,
                            "gridProperties": {
                                "rowCount": rows,
                                "columnCount": columns
                            }
                        }
                    }
                }
            ]
        }
    
    def _prepare_append_values_req(
        self,
        sheet_id: str, 
        sheet_range: str,
        value_range: dict
    ) -> aiogoogle_models.Request:
        """
        Prepares append request to be sent to Google
        """
        req = self.sheet_service.spreadsheets.values.append(
            spreadsheetId=sheet_id,
            range=sheet_range,
            json=value_range,

            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            includeValuesInResponse=False,
            responseValueRenderOption="UNFORMATTED_VALUE",
            responseDateTimeRenderOption="SERIAL_NUMBER"
        )
        return req
    
    @staticmethod
    def _error_to_response_code(e: aiogoogle.excs.HTTPError) -> int:
        """
        Converts e to a response code. Needed for handling different errors.
        """
        code = e.res.json["error"].get("code", None)
        if code is not None:
            return int(code)
        
    @staticmethod
    def _error_to_message(e: aiogoogle.excs.HTTPError) -> str:
        """
        Converts e to a response code. Needed for handling different errors.
        """
        msg = e.res.json["error"].get("message", None)
        if msg is not None:
            return str(msg)
    
    def error_to_user_message(self, e: aiogoogle.excs.HTTPError) -> str:
        """
        Parses response received on error to a user-friendly string
        """
        code = self._error_to_response_code(e=e)
        message = self._error_to_message(e=e)
        user_msg = "Google Sheets Error."
        if code is not None:
            user_msg = f"{user_msg} Code: {code}."
        if message is not None:
            user_msg = f"{user_msg} Message: {message}."
        return user_msg

class GoogleSheetAsyncGateway(GoogleSheetMapper):
    """
    Implements an async class for interacting with Gsheet API.
    It relies on a service account for authentication.
    """
    def __init__(self, service_acc_path: str,
                 read_rps_limiter: async_rps_limiter.AsyncLimiter,
                 write_rps_limter: async_rps_limiter.AsyncLimiter):
        """
        Instantiates the gateway
        """
        self.raw_creds = self._new_creds(service_acc_path=service_acc_path)
        bot_logger.debug("Prepared raw Service Acc credentials")
        self.gsheet_client = aiogoogle.Aiogoogle(
            service_account_creds=self.raw_creds
        )
        self.read_limiter = read_rps_limiter
        self.write_limter = write_rps_limter
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
        async with self.gsheet_client as client:
            self.sheet_service = await client.discover(
                api_name="sheets",
                api_version=api_version
            )
        bot_logger.debug("Performed %s sheets service discovery", api_version)

    
    @simple_async_retry(exceptions=(GoogleSheetRetriableError,
                                    aiogoogle.excs.AuthError),
                        logger=bot_logger, retries=10, delay=1)
    async def __make_request(self, req: aiogoogle.models.Request,
                             timeout: int) -> aiogoogle.models.Response:
        """
        Private method simplifying sending API requests to Google Backend.
        Encorporates some basic retry logic.
        """
        try:
            async with self.gsheet_client as client:
                res = await client.as_service_account(
                    req, timeout=timeout
                )
            return res
        except aiogoogle.excs.HTTPError as e:
            if 400 <= self._error_to_response_code(e=e) < 500:
                raise GoogleSheetBadRequestError(
                    msg="Bad Request", og_exception=e
                )
            else:
                raise GoogleSheetRetriableError(
                    msg="Retriable error", og_exception=e
                )
    
    async def _request_wrapper(
            self, req: aiogoogle.models.Request,
            req_type: str, timeout: Optional[int] = None
            ) -> tuple:
        """
        Abstraction on top of __make_request that controls RPS limiting
        and handles exceptions.
        """
        # TODO exceptions
        # TODO ratelimitting!!!
        # TODO errors for API requests
        timeout = timeout or 10
        
        # Not wrapping to a separate func bc mapper has no access to limiters
        if req_type == READ_REQUEST_TYPE:
            limiter = self.read_limiter
        elif req_type == WRITE_REQUEST_TYPE:
            limiter = self.write_limter
        else:
            return None, ValueError(
                f"Bad input for req_type: {req_type}. Need 'r' or 'w'"
            )

        try:
            async with limiter:
                resp = await self.__make_request(req=req, timeout=timeout)
                return resp, None
        except (GoogleSheetBadRequestError, GoogleSheetRetriableError) as e:
            bot_logger.debug("Request error. Request: %s. Response: %s",
                             e.og_exception.req.json, e.og_exception.res.json)
            user_msg = self.error_to_user_message(e=e.og_exception)
            return None, aiogoogle.excs.HTTPError(user_msg)
    
    async def get_sheet_properties(self, sheet_id: str) -> tuple:
        """
        Fetches sheet data via a get request
        """
        bot_logger.debug("Requesting sheet metadata")
        req = self.sheet_service.spreadsheets.get(spreadsheetId=sheet_id,
                                                  includeGridData=False)
        bot_logger.debug("Prepared request")
        data, e = await self._request_wrapper(req=req,
                                              req_type=READ_REQUEST_TYPE)
        if e is not None:
            bot_logger.error("Error fetching sheet properties: %s", e)
            return None, e
        return data, e
    
    async def read_sheet(self, sheet_id: str, tab_name: str,
                         header_rownum: Optional[int] = None,
                         header_offset: Optional[int] = None,
                         as_df: Optional[bool] = None,
                         use_schema: Optional[bool] = None) -> tuple:
        """
        Fetches data from spreadsheet
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

        req = self.sheet_service.spreadsheets.values.get(
            spreadsheetId=sheet_id,
            range=f"{tab_name}!A:ZZ",
            majorDimension='ROWS'
        )
        bot_logger.debug("Prepared sheet reading request")
        sheet_data, e = await self._request_wrapper(
            req=req, req_type=READ_REQUEST_TYPE
        )
        if e is not None:
            bot_logger.error("Err reading sheet: %s", e)
            return None, e
        # 2D array with rows here
        sheet_data = sheet_data["values"]
        bot_logger.info("Received data back, len %s", len(sheet_data))

        header, data = self._process_sheet_response(sheet_data=sheet_data,
                                                    header_rownum=header_rownum,
                                                    header_offset=header_offset)
        bot_logger.debug("Accounted for header in sheet data")
        if not as_df:
            bot_logger.info("Returning as 2d list")
            return [header] + data, None
        
        # Converting to polars
        bot_logger.info("Converting to polars")
        df = pl.DataFrame(data=data)
        if len(df) > 0:
            df = df.transpose()
            df.columns = header
        if not use_schema:
            bot_logger.info("use_schema is False, returning untyped")
            return df, None
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
        resp, e = await self._request_wrapper(req=req,
                                              req_type=WRITE_REQUEST_TYPE)
        if e is not None:
            bot_logger.error("Err cleaning data: %s", e)
            return None, e
        return resp, e
    
    async def delete_rows(self, sheet_id: str, tab_name: str, end: int,
                          start: Optional[int] = None):
        """
        TODO return type hint
        Deletes rows from a tab
        """
        # Defaulting to 1 because zero is usually a header row
        if start is None:
            start = 1

        sheet_properties = await self.get_sheet_properties(sheet_id=sheet_id)
        sheet_tabs_data = self.parse_raw_properties(
            sheet_properties=sheet_properties
        )
        tab_id, e = await self._tab_name_to_tab_id(
            sheet_id=sheet_id, tab_name=tab_name,
            sheet_tabs_data=sheet_tabs_data
        )
        if e is not None:
            bot_logger.error("Rows deletion failed. Details: %s", e)
            return None, e
        bot_logger.debug("tab %s is found in sheet %s", tab_name, sheet_id)
        req_body = self._delete_rows_params_to_body(tab_id=tab_id,
                                                    start=start, end=end)
        bot_logger.debug("Deleting rows using body: %s", req_body)
        req = self.sheet_service.spreadsheets.batchUpdate(
            spreadsheetId=sheet_id,
            json=req_body
        )
        return await self._request_wrapper(req=req, req_type=WRITE_REQUEST_TYPE)

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
        
        # Convert df to a list of lists bc google expects an array
        data_update = self._df_to_sheet_update(
            data=data, include_header=include_header
        )
        # Convert data to value range
        sheet_range = f"{tab_name}!{paste_range}"
        value_range = self._sheet_update_and_range_to_value_range(
            sheet_range=sheet_range, data_update=data_update
        )
        # TODO refactor this a bit more!
        bot_logger.info("Pasting data to %s using range %s",
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
        return await self._request_wrapper(req=req, req_type=WRITE_REQUEST_TYPE)
    
    @staticmethod
    def _compute_number_of_rows_to_drop(current_len: int, new_len: int,
                                        row_limit: int):
        """
        Computes number of rows to delete to comply with row_limit
        """
        bot_logger.debug("current: %s, new: %s, limit %s",
                         current_len, new_len, row_limit)
        to_delete = 0
        if (tot_len := (current_len + new_len)) > row_limit:
            to_delete = tot_len - row_limit
        return to_delete
    
    async def append_data_native(self, sheet_id: str, tab_name: str,
                                 data: pl.DataFrame, row_limit: int,
                                 include_header: Optional[bool] = None):
        """
        Uses native append Method of the Gsheet API to add new rows to
        the sheet.
        """
        if include_header is None:
            include_header = False
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
        paste_pos = current_len - to_delete 
        # Prepare append request
        data_update = self._df_to_sheet_update(
            data=data, include_header=include_header
        )
        paste_range = self._df_to_update_range(data=data, start_row=paste_pos)
        sheet_range = f"{tab_name}!{paste_range}"
        value_range = self._sheet_update_and_range_to_value_range(
            sheet_range=sheet_range, data_update=data_update
        )
        req = self._prepare_append_values_req(
            sheet_id=sheet_id, sheet_range=sheet_range,
            value_range=value_range
        )
        # Execute append request
        bot_logger.debug("Appending Natively")
        return await self._request_wrapper(req=req, req_type=WRITE_REQUEST_TYPE)
    
    async def add_sheet(self, sheet_id: str, title: str, 
                        rows: Optional[int] = None,
                        columns: Optional[int] = None):
        """
        Adds a new sheet to the spreadsheet
        """
        rows = rows or 1000
        columns = columns or 1000
        json_body = self._add_sheet_params_to_add_sheet_body(
            title=title, rows=rows, columns=columns
        )
        req = self.sheet_service.spreadsheets.batchUpdate(
            spreadsheetId=sheet_id,
            json=json_body
        )
        return await self._request_wrapper(req=req, req_type=WRITE_REQUEST_TYPE)


#TODO Oct 3 2023:
# Start calling functions of this class in bot

