"""
Module to test gsheet async gateway, will be deleted later
"""
import asyncio
import logging.config

import yaml

from alfredo_lib import MAIN_CFG
from alfredo_lib.gateways import google_sheets_gateway

# Logging boilerplate
# Read logging configuration
with open(MAIN_CFG["logging_config"]) as _log_cfg:
    LOGGING_CONFIG = yaml.safe_load(_log_cfg)
# Configure our logger
logging.config.dictConfig(LOGGING_CONFIG)
# Get loggers
bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])

sheets = google_sheets_gateway.GoogleSheetAsyncGateway(
    service_acc_path="secrets/google.json"
)

SAMPLE_SPREADSHEET_ID = "1x_8Jq6difcp606OQUJuvO8NpE5r7yl5GfJeY7boDeGo" 
SAMPLE_TAB_READ = "test"
SAMPLE_TAB_PASTE = "test_paste"

async def main():
    "Wrapper of async logic"

    await sheets.discover_sheet_service(api_version="v4")
    sheet_data = await sheets.read_sheet(sheet_id=SAMPLE_SPREADSHEET_ID,
                                         tab_name=SAMPLE_TAB_READ,
                                         as_df=True)
    print(sheet_data)
    # Clear data test
    # resp = await sheets.clear_data(sheet_id=SAMPLE_SPREADSHEET_ID,
    #                                tab_name=SAMPLE_TAB_PASTE,
    #                                cols_len=1)
    # print(resp)

    # tab id check
    tab_id, err = await sheets.tab_name_to_tab_id(sheet_id=SAMPLE_SPREADSHEET_ID,
                                   tab_name=SAMPLE_TAB_PASTE)
    print(tab_id)

loop = asyncio.get_event_loop()

loop.run_until_complete(main())