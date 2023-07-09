# Module stores class dependencies for running alfredo
from alfredo_lib import MAIN_CFG
from alfredo_lib.local_persistence.cache import Cache

# Start with classes as further steps might be dependent on them
cache = Cache(MAIN_CFG["cache_path"]) # Referred by main & logging

# Get our loggers
# bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
# backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])


