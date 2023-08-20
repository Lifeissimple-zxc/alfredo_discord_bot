"""
Module encompasses custom excpetions used in the bot's logic
"""

class UserNotRegisteredError(Exception):
    """
    Custom expection to be raised when a user invoving a command
    is not registered in the database
    """
    def __init__(self, msg: str, cmd: str):
        """Instantiates the error"""
        super().__init__(msg)
        self.cmd = cmd