#TODO base and extra need to come from params!
import logging
from typing import Optional

from alfredo_lib import MAIN_CFG
# Get loggers
bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])

class InputController:
    """
    Controls validity of user inputs and generates prompts for collecting them.
    """
    def __init__(self, input_schemas: dict):
        """
        Creates an instance of the validator class
        :param input_schemas: parsed yaml describing base and extra keys for data models
        """
        self.input_schemas = self._parse_input_schemas(input_schemas)

    @staticmethod
    def _parse_input_schemas(input_schemas: dict) -> dict:
        """
        ### Parses input_schemas dict from {"key": []} to {"key": set()} form
        :param input_schemas: parsed yaml describing base and extra keys for models
        """
        container = {}
        for model, setup in input_schemas.items():
            if not setup.get("base", None):
                raise ValueError(f"Command {model} does not have base defined")

            container[model] = {"base": set(setup["base"])}
            if not setup.get("extra", None):
                continue
            container[model]["extra"] = set(setup["extra"])

        bot_logger.debug("Parsed input schema: %s", container)
        return container
    
    def validate(self, user_input: dict, model: str) -> set:
        """
        ### Validates whether user input has all the base keys
        :returns: Missing keys
        """
        input_keyset = set(user_input.keys())
        return self.input_schemas[model]["base"] - input_keyset
    
    def create_prompt_keys(self, model: str, mode: Optional[str] = None) -> set:
        """
        ### Pulls keys for Alfredo to ask data for
        :param command: model to lookup data for
        :param mode: defines what set of keys to include
            - "all" returns union of base and extra sets
            - "base" returns base set
            - "extra" returns extra set
        
        :returns: set of keys to be used in prompt to the user
        :raises: NotImplementedError if provided with a wrong mode
        """
        mode = "all" or mode
        # Doing command data lookup once here
        command_keys = self.input_schemas[model]
        if mode == "all":
            return (command_keys["base"] | command_keys["extra"])
        elif mode == "base":
            return command_keys["base"]
        elif mode == "extra":
            return command_keys["extra"]
        else:
            raise NotImplementedError(f"mode {mode} is not supported. Check docstring!")

