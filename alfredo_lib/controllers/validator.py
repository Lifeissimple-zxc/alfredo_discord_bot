"""
Module implements input prompting, parsing and validaton methods.
"""
import logging
import re
from typing import Optional, Union

from alfredo_lib import FLOAT_PRECISION, MAIN_CFG

# Get loggers
bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])


class InputValidator:
    """
    Validates types of data provided by user
    """
    def __init__(self, input_schemas: dict):
        """
        Instantiates the validator
        """
        self.types_schema = self._parse_types_schema(input_schemas)

    @staticmethod
    def _parse_types_schema(input_schemas: dict):
        container = {}
        for model, data in input_schemas.items():
            container[model] = input_schemas[model]["base"]
            if "extra" in data:
                container[model] = {
                    **container[model],
                    **input_schemas[model]["extra"]
                }
        return container

    @staticmethod
    def _convert_type(data: str, target_type: str):
        data = data.strip()
        if target_type == "str":
            return data, None
        elif target_type == "float":
            return float(data), None
        elif target_type == "int":
            return int(float(data)), None
        else:
            return None, NotImplementedError(
                f"{target_type} is not supported"
            )
    
    def parse_input(self, model: str, field: str, data: str) -> tuple:
        """
        Parses input to the target type defined by field key for model in schema
        :return: tuple(converted data, err if any)
        """
        res, e = self._convert_type(data=data,
                                    target_type=self.types_schema[model][field])
        if e is not None:
            return None, e
        return res, None
    
    @staticmethod
    def sheet_input_to_sheet_id(user_input: str) -> None:
        """
        Converts spreadsheet input provided by the user
        to a sheet id that alfredo can work with
        """
        parsing_setup = MAIN_CFG["google_sheets"]["sheet_id_parsing"]
        bot_logger.debug("Pasring sheet_input %s to id", user_input)
        sheet_id = user_input

        if re.search(pattern=parsing_setup["url_pattern"],
                     string=user_input):
            bot_logger.debug("User provided a url")
            if not (sheet_id := re.search(pattern=parsing_setup["id_pattern"],
                                    string=user_input)):
                return None, ValueError("Cannot parse url to sheet_id")
            bot_logger.debug("Fetched id from sheet input")
            sheet_id = sheet_id.group(1)
        
        if (id_len := len(sheet_id)) != parsing_setup["id_len"]:
            msg = f"Invalid len {id_len} of sheet id in url. Value: {sheet_id}"
            bot_logger.error(msg)
            return None, ValueError(msg)
        
        return sheet_id, None
    
    @staticmethod
    def number_to_percent(user_input: Union[int, float],
                          allow_negative: Optional[bool] = None) -> tuple:
        """
        Converts user given input to a percentage
        """
        if allow_negative is None:
            allow_negative = False
        
        num_val = round(user_input, FLOAT_PRECISION) 
        if not allow_negative and num_val < 0:
            return None, ValueError("Negative values are not allowed")

        if 0 < num_val <= 1:
            bot_logger.debug("Provided value is a percentage, returning")
            return num_val, None
        
        bot_logger.debug("Provided value is not a percentage, converting")
        num_val = round(num_val / 100, FLOAT_PRECISION)
        if num_val > 1:
            bot_logger.debug("Conversion did not help :(")
            return None, ValueError("Value is too high after conversion")
        
        return num_val, None 


class InputController(InputValidator):
    """
    Controls validity of user inputs and generates prompts for collecting them.
    """
    def __init__(self, input_schemas: dict):
        """
        Creates an instance of the validator class
        :param input_schemas: parsed yaml describing base and extra keys for data models
        """
        super().__init__(input_schemas=input_schemas)
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

            container[model] = {"base": set(setup["base"].keys())}
            if not setup.get("extra", None):
                container[model]["extra"] = set()
                continue
            container[model]["extra"] = set(setup["extra"].keys())

        bot_logger.debug("Parsed input schema: %s", container)
        return container
    
    def validate_keys(self, user_input: dict, model: str) -> set:
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

