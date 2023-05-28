
import yaml
from pathlib import Path
from dotenv import dotenv_values

ENV_VARS = dotenv_values(".env")

with open("config/logging_config.yaml") as _log_cfg:
    LOGGING_CONFIG = yaml.safe_load(_log_cfg)

# Paths for reading commands
BASE_DIR = Path(__file__).parent.parent # Two levels up
CMDS_DIR = BASE_DIR / "cmd_test"
COGS_DIR = BASE_DIR / "cogs"