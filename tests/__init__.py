import yaml
import logging.config

with open(file="config/main_config.yaml", encoding="utf-8") as _f:
    MAIN_CFG = yaml.safe_load(_f)
with open(file=MAIN_CFG["logging_config"], encoding="utf-8") as _f:
    LOGGING_CONFIG = yaml.safe_load(_f)
with open(file=MAIN_CFG["user_input_schemas"], encoding="utf-8") as _f:
    USER_INPUT_SCHEMAS = yaml.safe_load(_f)

# Logging boilerplate
logging.config.dictConfig(LOGGING_CONFIG)

