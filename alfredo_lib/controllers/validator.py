#TODO base and extra need to come from params!

class InputController:
    """
    Controls validity of user inputs and generates prompts for collecting them.
    """
    def __init__(self, input_schemas: dict):
        """
        Creates and instance of the validator class
        :param input_schemas: parsed yaml describing base and extra keys for commands
        """
        self.input_schemas = self._parse_input_schemas(input_schemas)

    @staticmethod
    def _parse_input_schemas(input_schemas: dict) -> dict:
        """
        ### Parses input_schemas dict from key: [] to key: set() form
        :param input_schemas: parsed yaml describing base and extra keys for commands
        """
        container = {}
        for command, setup in input_schemas.items():
            if "base" not in setup.keys():
                raise ValueError(f"Command {command} does not have base defined")
            parsed_setup = {
                "base": set(setup["base"]),
                "extra": set(setup["base"])
            }
            container[command] = parsed_setup.copy()
        return container
    
    def validate(self, user_input: dict, command: str) -> set:
        """
        ###Validates whether user input has all the base keys
        :returns: Missing keys
        """
        input_keyset = set(user_input.keys())
        return self.input_schemas[command]["base"] - input_keyset
    
    def create_prompt_keys(self, command: str, mode: str = None) -> set:
        """
        ### Pulls keys for Alfredo to ask data for
        :param command: command to lookup data for
        :param mode: defines what set of keys to include
            - "all" returns union of base and extra sets
            - "base" returns base set
            - "extra" returns extra set
        
        :returns: set of keys to be used in prompt to the user
        :raises: NotImplementedError if provided with a wrong mode
        """
        mode = "all" or mode
        # Doing command data lookup once here
        command_keys = self.input_schemas[command]

        if mode == "all":
            return command_keys["base"] | command_keys["extra"]
        elif mode == "base":
            return command_keys["base"]
        elif mode == "extra":
            return command_keys["extra"]
        else:
            raise NotImplementedError(f"mode {mode} is not supported. Check docstring!")

