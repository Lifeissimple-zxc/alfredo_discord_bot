"""
Module stores class dependencies for running alfredo
"""

from alfredo_lib import MAIN_CFG, USER_INPUT_SCHEMAS
from alfredo_lib.controllers import validator
from alfredo_lib.gateways import google_sheets_gateway
from alfredo_lib.gateways.base import async_rps_limiter
from alfredo_lib.local_persistence import cache

# Start with classes as further steps might be dependent on them
local_cache = cache.Cache(MAIN_CFG["cache_path"]) # Referred by main & logging
input_controller = validator.InputController(input_schemas=USER_INPUT_SCHEMAS)
# Gsheet-related things
read_limiter = async_rps_limiter.AsyncLimiter(
    **MAIN_CFG["google_sheets"]["rps"]["read"]
)
write_limiter = async_rps_limiter.AsyncLimiter(
    **MAIN_CFG["google_sheets"]["rps"]["read"]
)
sheets = google_sheets_gateway.GoogleSheetAsyncGateway(
    service_acc_path=MAIN_CFG["google_sheets"]["service_file"],
    read_rps_limiter=read_limiter,
    write_rps_limter=write_limiter
)
# Get our loggers
# bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
# backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])


