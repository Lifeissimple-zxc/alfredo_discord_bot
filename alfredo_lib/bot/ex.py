"""
Module encompasses custom excpetions used in the bot's logic
"""

class UserNotRegisteredError(Exception):
    """
    Custom expection to be raised when a user invoking a command
    is not registered in the internal database
    """
    pass


class WrongUpdateFieldInputError(Exception):
    """"
    Custom exception to be raised when a user invoking an
    update-like command provided an incorrect field
    """
    pass


class ContextMissingError(Exception):
    """
    Custom exception for scenarios where ctx is not in kwargs
    """
    pass


class AdminPermissionNeededError(Exception):
    """
    Custom exception for scenarios where non-admin calls and admin command
    """
    pass

class InvalidUserInputError(Exception):
    """
    Indicates that a user's input did not pass validation
    """
    pass