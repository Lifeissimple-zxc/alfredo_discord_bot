"""
Module implements an async Gsheet Gateway
"""
import json
import aiogoogle
from aiogoogle.auth import creds

SHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class WorkSheet:
    pass


class GoogleSheetAsyncGateway:
    """
    Implements an async class for interacting with Gsheet API.
    It relies on a service account for authentication.
    """
    def __init__(self, service_acc_path: str):
        """
        Instantiates the gateway
        """
        self.gsheet_client = aiogoogle.Aiogoogle(
            service_account_creds=self._new_creds(service_acc_path=service_acc_path)
        )    

    @staticmethod
    def _new_creds(service_acc_path: str) -> creds.ServiceAccountCreds:
        """
        Helper instantiating credentials object for Google API authentication
        """
        service_account_key = json.load(open(file=service_acc_path,
                                             encoding="utf-8",
                                             mode="r"))
        return creds.ServiceAccountCreds(scopes=SHEET_SCOPES, **service_account_key)
    
    async def discover_sheet_service(self, api_version: str):
        """
        Discovers sheets api service
        """
        self.sheet_service = await self.gsheet_client.discover(
            api_name="sheets", api_version=api_version
        )

    async def get_sheet_data(self, sheet_id: str):
        """
        Fetches sheet data via a get request
        """
        resp = await self.gsheet_client.as_service_account(
            self.sheet_service.spreadsheets.get(
                spreadsheetId=sheet_id, includeGridData=False
            )
        )
        return resp
    
    async def open_sheet(sheet_id: str, sheet_tab_name: str) -> WorkSheet:
        pass
    


# TODO unite it alll under a class
# TODO worksheet???


# def sheet_to_df():
#     pass

# def paste_rows():
#     pass

# def append_rows():
#     pass