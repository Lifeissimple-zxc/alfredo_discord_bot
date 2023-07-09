# Module stores class dependencies for running alfredo
from alfredo_lib.local_persistence.cache import Cache
from alfredo_lib import (
    MAIN_CFG
)

cache = Cache(MAIN_CFG["cache_path"]) # Referred by main & logging