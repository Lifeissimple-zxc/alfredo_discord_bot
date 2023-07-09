import logging
import queue
from retry import retry
from typing import List, Dict
from requests import session, RequestException
from atexit import register
from pathlib import Path

from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler
from logging.config import ConvertingList
from logging import LogRecord

from alfredo_lib.local_persistence.cache import Cache
from alfredo_lib import (
    ENV_VARS, ENV, MAIN_CFG
)

# Constants
LEVEL_MAP = {"CRITICAL": 50, "ERROR": 40, "WARNING": 30,
             "INFO": 20, "DEBUG": 10, "NOTSET": 0}
_LOG_QUEUE = queue.Queue() # This is referred to in logging config yaml
backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])

class QueueListenerHandler(QueueHandler):
    """
    ### This class listens to the handlers attached to the queue stored within self.
    It works on a separate thread thus supports both sync and async code.
    Inspired by my colleagues from Uber and the below medium article:
    https://rob-blackbourn.medium.com/how-to-use-python-logging-queuehandler-with-dictconfig-1e8b1284e27a
    """
    def __init__(self, handlers: List, queue: queue.Queue,
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
        self.listener = QueueListener(queue, *handlers, respect_handler_level)
        # Avoid the need to start the logging queue manually
        if autorun:
            self.listener.start()
            # ACHTUNG: we enable the logging queue to flush by using atexit.register
            register(self.listener.stop)
    
    @staticmethod
    def __convert_handlers(handlers: List) -> List:
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
        return super().emit(record)


class LevelFilter(logging.Filter):
    """
    ### QueueListener does not do level filtering by default, this class does it.
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
        # Looser check by default
        allow = (record.levelno >= self.level)
        # Override for strict setup when needed
        if self.strict:
            allow = (self.level == record.levelno)

        return allow

        
class AttributeFilter(logging.Filter):
    """
    Class for filtering based on at attribute of a LogRecord
    """
    def __init__(self, attr_name: str, allow_val: bool, default_val: bool):
        """
        :param attr_name: name of the attribute to use for filtering
        :param allow_val: value that greenlights filtering
        :param default_val: default value of the attribute
        """
        super().__init__()
        self.attr_name = attr_name
        self.allow_val = allow_val
        self.default_val = default_val

    def filter(self, record: LogRecord) -> bool:
        """
        ### Performs filtering a record
        :param record: LogRecord to filter
        """
        return getattr(record, self.attr_name, self.default_val) == self.allow_val


class DiscordHandler(logging.Handler):
    """
    Class handles logging to a Discord channel
    """
    def __init__(self, wbhk: str = ENV_VARS[f"DISCORD_LOGGING_WEBHOOK_{ENV}"],
                 users_to_tag: List[str] = MAIN_CFG["discord"]["users_to_tag"][ENV],
                 project: str = MAIN_CFG["discord"]["project"],
                 max_chars: int = None, autoflush: bool = None, warn_str: str = None):
        """
        :param wbhk: webhook of the channel where the log messages are to be sent
        :param users_to_tag: string of user id to tag in the message
        :param max_chars: max len of a message, 2000k is the default
        """
        # Inherit and construct the class
        super().__init__()
        # Default values
        self.max_chars = max_chars or 2000
        self.autoflush = autoflush or True
        self.warn_str = warn_str or ":warning:"
        # Other attributes
        self.sesh = session()
        self.wbhk = wbhk
        self.project = project
        self.users_to_tag = self._create_usr_tag_str(users_to_tag)
        # Register session closure to be done at the exit
        register(self.sesh.close)

    @staticmethod
    def _create_usr_tag_str(users_to_tag: List[str]) -> str:
        """
        ### Converts users_to_tag to a tagging string
        """
        tag_str = [f"<@{user}>" for user in users_to_tag]
        return " ".join(tag_str)
        
    def _format_level(self, record: LogRecord) -> str:
        """
        ### Generates a wrapper string depending on the level of the record
        https://docs.python.org/3/library/logging.html#logging-levels
        :return: string that will preceed the messsage
        """
        repts = (record.levelno - 20) // 10
        # No wrapper string for INFO and lower
        wrapper = ""
        if repts > 0:
            wrapper = repts * self.warn_str
        return wrapper
    
    def _truncate_message(self, msg: str, buffer: int = None) -> str:
        """
        ### Truncates the log messages to fit within the self.max_chars limit
        :param msg: message to be sent to discord
        :param buffer: extra characters to remove from the msg, defaults to 0
        :return: truncated message to be sent to discord
        """
        if buffer is None:
            buffer = 0
        truncated = msg
        if (len(msg) + buffer) > self.max_chars:
            truncated = msg[:self.max_chars - buffer - 1]
        return truncated
    
    def _prepare_message(self, record: LogRecord) -> str:
        """
        ### Method performs all the steps for formatting record to a discord message str
        """
        log_msg = record.getMessage()
        # Add project name if any
        if self.project != "":
            log_msg = f"*{self.project}*: {log_msg}"
        # Handle wrapping for severe messages
        log_msg = f"{self._format_level(record)} {log_msg}"
        # Truncate
        log_msg = self._truncate_message(log_msg, buffer=len(self.users_to_tag))
        # Add people to tag
        log_msg += f" {self.users_to_tag}"

    def _prepare_request(self, record: LogRecord) -> Dict:
        """
        ### Prepares payload for sending log message to discord
        :param record: LogRecord we want to handle
        """
        full_msg = self._prepare_message(record)

        return {"content": full_msg}
    
    @retry(exceptions=RequestException, tries=10, delay=0.5, jitter=(0.5, 3))
    def _log_to_discord(self, record: LogRecord):
        """
        ### Sends log to discord using other lower-level methods of the class
        :param record: LogRecord we want to handle
        """
        data = self._prepare_request(record)
        try:
            resp = self.sesh.post(url=self.wbhk, data=data)
            # Check if we should retry
            if not 200 <= resp.status_code < 300:
                # Triggers decorator
                raise RequestException
        except RequestException as e:
            backup_logger.error(f"Failed to log to discord despite retries: {e}")
        except Exception as e:
            backup_logger.error(f"Uncaught exception when logging to discord: {e}")
    
    def emit(self, record: LogRecord):
        """
        ### Actually performs the logging to discord. Relient on lower-level methods.
        :param record: LogRecord we want to handle
        """
        self._log_to_discord(record)
            

class DbHandler(logging.Handler):
    """
    Handles writing log records to a local sqlite db
    """
    def __init__(self, cache_instance: Cache):
        """
        Stores an instance of Cahce within self. This instance interacts with the db.
        """
        super().__init__()
        self.__cache_instance = cache_instance

    def emit(self, record: LogRecord):
        """
        Performs logging to db
        """
        self.__cache_instance.add_log_row(record)


class BackupFileHandler(TimedRotatingFileHandler):
    """
    Backup handler used when rest of the handlers fail.
    """
    def __init__(self, folder: str, file: str):
        """
        ### Creates folder for log files if it does not exist.
        ##### Dest files are rotated at midnight UTC.
        :param folder: name of the folder to store our log files.
        :param file: name of the log file
        """
        log_file_path = Path(folder, file)
        log_file_dir = log_file_path.parent
        # Here we create the folder structure for logging files
        # Fist check if folder exists
        if log_file_dir.exists():
            if not log_file_dir.is_dir():
                # Create it if not a directory
                log_file_dir.mkdir(parents=True)
        # We also create if the folder does not exist at all
        else:
            log_file_dir.mkdir(parents=True)
        # Construct our logging class using inheritance
        super().__init__(filename=log_file_path, when="MIDNIGHT", utc=True)


