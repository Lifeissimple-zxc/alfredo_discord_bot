"""
Module to test gsheet async gateway, will be deleted later
"""
import asyncio
import logging.config

import yaml

from alfredo_lib import MAIN_CFG
from alfredo_lib.gateways import google_sheets_gateway
from alfredo_lib.gateways.base import async_rps_limiter

# Logging boilerplate
# Read logging configuration
with open(MAIN_CFG["logging_config"]) as _log_cfg:
    LOGGING_CONFIG = yaml.safe_load(_log_cfg)
# Configure our logger
logging.config.dictConfig(LOGGING_CONFIG)
# Get loggers
bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])

read_limiter = async_rps_limiter.AsyncLimiter(
    **MAIN_CFG["rps"]["google_sheets"]["read"]
)
write_limiter = async_rps_limiter.AsyncLimiter(
    **MAIN_CFG["rps"]["google_sheets"]["read"]
)
sheets = google_sheets_gateway.GoogleSheetAsyncGateway(
    service_acc_path="secrets/google.json",
    read_rps_limiter=read_limiter,
    write_rps_limter=write_limiter
)


SAMPLE_SPREADSHEET_ID = "1x_8Jq6difcp606OQUJuvO8NpE5r7yl5GfJeY7boDeGo" 
SAMPLE_TAB_READ = "test"
SAMPLE_TAB_PASTE = "test_paste"
SAMPLE_TAB_APPEND = "test_append"

async def main():
    "Wrapper of async logic"
    # Read data
    await sheets.discover_sheet_service(api_version="v4")
    sheet_data, e = await sheets.read_sheet(sheet_id=SAMPLE_SPREADSHEET_ID,
                                         tab_name=SAMPLE_TAB_READ,
                                         as_df=True)

    # Append to a new tab
    resp, e = await sheets.append_data_native(sheet_id=SAMPLE_SPREADSHEET_ID,
                                    tab_name=SAMPLE_TAB_APPEND,
                                    data=sheet_data,
                                    row_limit=10)

    # Add a new tab
    resp, e = await sheets.add_sheet(sheet_id=SAMPLE_SPREADSHEET_ID,
                                         title="someSheet")



loop = asyncio.get_event_loop()

loop.run_until_complete(main())