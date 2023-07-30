# Module stores class dependencies for running alfredo

from alfredo_lib.local_persistence import cache
from alfredo_lib.controllers import validator
from alfredo_lib import MAIN_CFG, USER_INPUT_SCHEMAS

# Start with classes as further steps might be dependent on them
local_cache = cache.Cache(MAIN_CFG["cache_path"]) # Referred by main & logging
input_controller = validator.InputController(USER_INPUT_SCHEMAS)
# Get our loggers
# bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
# backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])


