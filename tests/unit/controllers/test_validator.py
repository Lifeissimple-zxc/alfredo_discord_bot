"""
Module implements tests for validator module from alfredo_lib
"""
import logging
import unittest

from alfredo_lib.controllers import validator
from tests import MAIN_CFG, USER_INPUT_SCHEMAS

test_logger = logging.getLogger(MAIN_CFG["test_logger"])

class TestInputController(unittest.TestCase):
    """
    Class for test cases of InputController and InputValidator
    """

