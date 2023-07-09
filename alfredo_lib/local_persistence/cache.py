import re
import logging
from pathlib import Path
from time import time
from alfredo_lib.local_persistence.models import (
    Base,
    User,
    LogRecordRow
)
from sqlalchemy.engine import Engine, ResultProxy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    create_engine
)
from sqlalchemy.exc import IntegrityError
from alfredo_lib import (
    MAIN_CFG
)
from typing import Union

# Get loggers
bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])

# This is an ORM that is responsible for all the operations with the local sqlite3 db.
# It needs to support the following functions:
# Add new row to users table
# Update data in users table
# Add transaction row to the table
# Drop row in the transaction table
class Cache:
    """
    Class responsible for all the db operations
    """
    def __init__(self, db_path: str):
        """
        Instantiates the class, creates the db & tables if they do not exist
        """
        self.db_path_raw = db_path
        self.users_table = User
        self.logs_table = LogRecordRow
        self.engine = self._create_engine(db_path)
        # TODO Check if the below two lines can be merged?
        Session = sessionmaker(bind=self.engine)
        self.sesh = Session()
        self.base = Base
        # Actually create schema in the db
        self._create_db_tables()
    # Create all the tables on init (along with session and )
    # Write user-related operations
    
    @staticmethod
    def _create_engine(db_path: str) -> Engine:
        """
        Creates engine object, creates folders in db_path if they don't exist
        """
        path_obj = Path(db_path)
        parent_dir = path_obj.parent
        # This path is for cases where we don't need to create anything
        if parent_dir.exists() and parent_dir.is_dir():
            bot_logger.debug("DB path exists")
        
        # Here we create parent dirs for cache db (needs to be abstracted?)
        parent_dir.mkdir(parents=True, exist_ok=True)
        bot_logger.debug("Created dirs for DB")
        
        return create_engine(f"sqlite:///{path_obj.absolute()}", echo=False)
    
    def _create_db_tables(self):
        #TODO
        """
        Creates db table with all the tables from args
        """
        bot_logger.debug("Creating db schema")
        self.base.metadata.create_all(self.engine)

    @staticmethod
    def _generate_ts() -> int:
        """
        Generates current time as unix milisec timestamp
        """
        return int(time() * 1000)
    
    def _construct_table_row(self, dst_attr_name: str, **kwargs) -> tuple:
        """
        ### Lower-level abstraction to write new rows to local sqlite
        :param dst_attr_name: name of the attribute stored within self.
        :return: tuple(sqlalchemy row, error if any)
        """
        # First, check if dst_attr_name is valid
        table = getattr(self, dst_attr_name, None)
        if table is None:
            msg = f"Local cache does not have {dst_attr_name} attr."
            return None, AttributeError(msg)
        # Getting here means we can actually add our row
        try:
            new_row = table(created=self._generate_ts(), **kwargs)
        except Exception as e:
            return None, e
        
        bot_logger.debug(f"Prepared new row for {dst_attr_name}: {kwargs}")
        return new_row, None
    
    def _add_new_row(self, row_struct: ResultProxy) -> Union[Exception, None]:
        """
        Adds row_struct to the corresponding table
        :param row_struct: sqlalchemy row object
        :return: error if any
        """
        # Add to db
        try:
            self.sesh.add(row_struct)
            self.sesh.commit()
        except Exception as e:
            self.sesh.rollback()
            return e

    def create_user(self, username: str, discord_id: int) -> tuple:
        """
        ### Creates a new user entry in the local db
        :param username: username for registration
        :param discord_id: discord_id of a user
        :return: tuple(user message, error if any)
        """
        # TODO exceptions? have no idea what might occur here
        # sqlite3.IntegrityError when unique constraint fails
        # Prepare user data from input
        user_row, e = self._construct_table_row(dst_attr_name="users_table",
                                                username=username,
                                                discord_id=discord_id)
        # Check for row struct creation errors
        if e is not None:
            user_msg = f"Internal data error: {e}"
            # Specify msg in case we have attr error
            if isinstance(e, AttributeError):
                user_msg = "Internal data error: users data does not exit on server."
            return user_msg, e

        bot_logger.debug(f"Prepared user data for {username} reg.")
        # Add to db (this also rollbacks in case of errors)
        res = self._add_new_row(user_row)
        # Save path w/o issues
        if res is None:
            user_msg = f"{username} registered"
            bot_logger.debug(user_msg)
            return user_msg, None
        
        # Handle exceptions if we got any
        if isinstance(res, IntegrityError):
            # Parse what column is causing the issue
            table, col = self.__parse_integrity_err_col(e)
            bot_logger.error(f"DB Constraint violated for {table}.{col}: {e}")
        
            if col == "username":
                user_msg = "username is already taken"
            else:
                user_msg = "You are already registered"
            return user_msg, e     
        else:
            user_msg = f"Unexpected internal error. Details: {e}"
            bot_logger.error(user_msg)
            return user_msg, e
    
    @staticmethod
    def __parse_integrity_err_col(e: IntegrityError):
        """
        Helper that extracts table & columnn that trigger IntegrityError
        :param e: exception of IntegrityError type
        :return: tuple(table, col)
        """
        e_str = str(e).lower()
        tab_col = re.search("failed: ([a-z\.\_]+)", e_str).group(1).split(".")
        return tab_col[0], tab_col[1]
    
    def update_user_data(self, field: str, value: str,
                         discord_id: int) -> tuple:
        """
        ### Updates field with value in users table
        :return: tuple(user message, error if any)
        """
        return True, None

    def _fetch_user_data(self, discord_id: int) -> tuple:
        """
        ### Fetches data on user with discord_id from the db
        :param discord_id: discord id of a user
        :return: tuple(User, error if any)
        """
        bot_logger.debug(f"Fetching user data for {discord_id}")
        user = self.sesh.query(User).filter(User.discord_id==discord_id).first()
        if user is None:
            bot_logger.debug(f"No results for {discord_id}")
            return None, ValueError("User not registered")
        return user, None
    
    @staticmethod
    def __parse_user_row(user: User) -> dict:
        """
        Parses user ORM row to a dict
        """
        # Make several modes: dict and string
        bot_logger.debug("Parsing user data to a dict")
        user_dict = {}
        cols = user.__class__.__table__.columns
        for col in cols:
            col_name = col.name
            val = getattr(user, col_name)
            if val: 
                user_dict[col_name] = val
        return user_dict
    
    def get_user(self, discord_id: int) -> tuple:
        """
        ### Gets user data as dict
        """
        user, e = self._fetch_user_data(discord_id)
        # Check for error
        if e is not None:
            user_msg = f"Failed to get user data: {e}"
            bot_logger.error(user_msg)
            return None, user_msg
        # Parse user data to dict
        user_data = self.__parse_user_row(user)
        return user_data, None
    
    def add_log_row(self, record: logging.LogRecord):
        """
        ### Writes record to a local logs table
        :param record: LogRecord from a logging call
        """
        log_row, e = self._construct_table_row(dst_attr_name="logs_table",
                                               user_id=getattr(record, "user_id", None),
                                               message=record.getMessage(),
                                               level=record.levelname,
                                               func_name=record.funcName)
        # Some TODO
        # Change prints with backup logger here
        # Mb add calls to a timeseries db here to track error and get alerted on them
        if e is not None:
            backup_logger.error(f"Logging to DB failed on row creation: {e}")

        res = self._add_new_row(log_row)
        if res is not None:
            backup_logger.error(f"Adding new DB row failed: {e}")

        


    



