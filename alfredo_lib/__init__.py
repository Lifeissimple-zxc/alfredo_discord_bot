import yaml
from dotenv import dotenv_values

ENV_VARS = dotenv_values(".env")

with open("config/logging_config.yaml") as _log_cfg:
    LOGGING_CONFIG = yaml.safe_load(_log_cfg)