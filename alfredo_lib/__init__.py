import dotenv
import yaml


ENV_VARS = dotenv.dotenv_values(".env")
ENV = "LOCAL" # TODO shold be coming from CLI args

# Read main cfg
with open(file="config/main_config.yaml", encoding="utf-8") as _f:
    MAIN_CFG = yaml.safe_load(_f)

FLOAT_PRECISION = MAIN_CFG["float_precision"]

ERROR_MESSAGES = MAIN_CFG["error_messages"]

with open(file=MAIN_CFG["user_input_schemas"], encoding="utf-8") as _f:
    USER_INPUT_SCHEMAS = yaml.safe_load(_f)

with open(file=MAIN_CFG["secrets"], encoding="utf-8") as _f:
    SECRETS = yaml.safe_load(_f)
# Making it a set for faster lookups
ADMINS = set(SECRETS["admin_discord_ids"])

with open(file=MAIN_CFG["commands_metadata"], encoding="utf-8") as _f:
    COMMANDS_METADATA = yaml.safe_load(_f)
