
import yaml
import logging
import logging.config as log_config
from pathlib import Path
from dotenv import dotenv_values

ENV_VARS = dotenv_values(".env")

# Read logging configuration
with open("config/logging_config.yaml") as _log_cfg:
    LOGGING_CONFIG = yaml.safe_load(_log_cfg)
# Configure our logger
log_config.dictConfig(LOGGING_CONFIG)

# Read main cfg
with open("config/main_config.yaml") as _cfg:
    MAIN_CFG = yaml.safe_load(_cfg)
# Read error feedback messages to a separate variable
ERROR_MESSAGES = MAIN_CFG["error_messages"]

# Paths for reading commands
BASE_DIR = Path(__file__).parent.parent # Two levels up
CMDS_DIR = BASE_DIR / "cmd_test"
COGS_DIR = BASE_DIR / "cogs"