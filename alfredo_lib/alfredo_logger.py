import logging
import queue
from requests import session
from time import time
from atexit import register
from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler
from logging.config import ConvertingList
from logging import (
    Handler,
    LogRecord
)

# Constants
LEVEL_MAP = {"CRITICAL": 50, "ERROR": 40, "WARNING": 30,
             "INFO": 20, "DEBUG": 10, "NOTSET": 0}

class QueueListenerHandler(QueueHandler):
    """
    ### This class listens to the handlers attached to the queue stored within self.
    It works on a separate thread thus supports both sync and async code.
    Inspired by my colleagues from Uber and the below medium article:
    https://rob-blackbourn.medium.com/how-to-use-python-logging-queuehandler-with-dictconfig-1e8b1284e27a
    """
    def __init__(self, handlers: list, queue: queue.Queue,
                 autorun: bool=None, respect_handler_level: bool=None):
        """
        ### Constructor of the class. Attaches a list of handlers to a queue.
        :param handlers: List of handlers for logging.
        :param queue: queue.Queue object.
        :param autorun: bool flag, True automatically starts and flushes the listener.
        :param respect_handler_level: Input to QueueListener, defaults to False.
        """
        # Default boolean flags
        if autorun is None:
            autorun = True
        if respect_handler_level is None:
            respect_handler_level = False
        # Inherit from QueueHandler
        super().__init__(queue=queue)
        # Transform datatypes for handlers
        handlers = self.__convert_handlers(handlers=handlers)
        # Save listener within self
        self.listener = QueueListener(
            queue=queue,
            respect_handler_level=respect_handler_level,
            *handlers
        )
        # Avoid the need to start the logging queue manually
        if autorun:
            self.listener.start()
            # ACHTUNG: we enable the logging queue to flush by using atexit.register
            register(self.listener.stop)
    
    @staticmethod
    def __convert_handlers(handlers: list) -> list:
        """
        ### Helper method to parse handlers.
        Iterates of the list of handlers and returns it.
        :param handlers: List of handlers for logging.
        :return: list of handlers ready to be user by the QueueListener
        """
        if isinstance(handlers, ConvertingList):
            # For some reason when not using indexing the loop does not work :(
            handlers = [handlers[i] for i in range(len(handlers))]
        return handlers
    
    def start(self):
        """
        Starts QueueListener attached to the class
        """
        self.listener.start()

    def stop(self):
        """
        Stops QueueListener attached to the class
        """
        self.listener.stop()

    def emit(self, record: LogRecord):
        """
        Performs logging
        :param record: LogRecord we want to handle
        """
        return super().emit(record=record)

class LevelFilter(logging.Filter):
    """
    ### QueueListener does not do level filtering by default, this class takes care of it.
    """
    def __init__(self, level: str, strict: bool=None):
        """
        Constructor of the class
        :param level: level of a LogRecord message, None by default.
        :param strict: Boolean flag, True means only specified level records are logged.
        """
        # Default value
        if strict is None:
            strict = False
        # Inherit for filtering methods to actually work
        super().__init__()
        # Validate logging level
        if level not in LEVEL_MAP.keys():
            raise ValueError(f"Wrong level: {level}, must be in {LEVEL_MAP.keys()}!")
        self.level = LEVEL_MAP[level]
        self.strict = strict

    def filter(self, record: LogRecord):
        """
        ### Actually performs filtering
        :param record: LogRecord we want to handle
        """
        if self.strict:
            # Make sure only the specific level goes through
            allow = (self.level == record.levelno)
        else:
            # Looser check
            allow = (record.levelno >= self.level)
        return allow

        



# class AttributeFilter:
#     pass


# class DiscordHandler:
#     pass

# class DbHandler:
#     pass
