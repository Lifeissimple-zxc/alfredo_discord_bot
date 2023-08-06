import yaml
import logging.config as log_config

# Read configs, not very DRY, but it's on purpose:
# To make tests self-contained!
with open("alfredo_tests/src/tests.yaml") as _tf:
    TEST_CFG = yaml.safe_load(_tf)
with open("config/main_config.yaml") as _cfg:
    MAIN_CFG = yaml.safe_load(_cfg)
with open(MAIN_CFG["logging_config"]) as _log_cfg:
    LOGGING_CONFIG = yaml.safe_load(_log_cfg)

# Logging boilerplate
log_config.dictConfig(LOGGING_CONFIG)

