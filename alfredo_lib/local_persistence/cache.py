"""
Module implements classes for interacting with a local DB using ORM
"""
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional, Union, List

import polars as pl
from sqlalchemy import create_engine, engine, exc, orm

from alfredo_lib import MAIN_CFG
from alfredo_lib.local_persistence import models

# Get loggers
bot_logger = logging.getLogger(MAIN_CFG["main_logger_name"])
backup_logger = logging.getLogger(MAIN_CFG["backup_logger_name"])

# This is an ORM that is responsible for all the operations with the local sqlite3 db.
# It needs to support the following functions:
# Add new row to users table
# Update data in users table
# Add transaction row to the table
# Drop row in the transaction table

# Constants for parsing ORM rows to PY objects
ROW_PARSE_MODE_STRING = "str"
ROW_PARSE_MODE_DICT = "dict"
ROW_PARSE_MODE_DF = "df"
OK_ROW_PARSE_MODES = {
    ROW_PARSE_MODE_STRING,
    ROW_PARSE_MODE_DICT,
    ROW_PARSE_MODE_DF
}

class DbErrorHandler:
    """
    Class respponsible for parsing DB errors.
    Generates user-facing messages as well.
    """
    @staticmethod
    def _handle_unexpected_err(e: Exception):
        """
        TODO
        """
        user_msg = f"Unexpected internal error. Details: {e}"
        bot_logger.error(user_msg)
        return user_msg, e

    @staticmethod
    def _parse_integrity_err_col(e: exc.IntegrityError):
        """
        Helper that extracts table & columnn that trigger IntegrityError
        :param e: exception of IntegrityError type
        :return: tuple(table, col)
        """
        # Doing this type check despite EAFP due to bot being async
        # It causes passing wrong types here go unnoticed!
        if not isinstance(e, exc.IntegrityError):
            msg = f"Wrong handler for error {e} of type {type(e)}"
            bot_logger.error(msg)
            raise TypeError(msg)
        bot_logger.debug("Parsing integriy error data...")
        tab_col = re.search("failed: ([a-z\.\_]+)", str(e).lower()).group(1).split(".")
        table, col = tab_col[0], tab_col[1]
        bot_logger.error("DB Constraint violated: %s", e) 
        return table, col
    
    def handle_integrity_err_user(self, e: exc.IntegrityError):
        """
        TODO
        """
        table, col = self._parse_integrity_err_col(e)
        bot_logger.debug("%s.%s caused error", table, col)

        if col == "username":
            user_msg = "username is already taken"
        else:
            user_msg = "You are already registered"
        
        bot_logger.debug("Integrity error result parsed")
        return user_msg, e


class BaseCache(DbErrorHandler):
    """
    Class responsible for all the db operations
    """
    def __init__(self, db_path: str):
        """
        Instantiates the class, creates the db & tables if they do not exist
        """
        self.db_path_raw = db_path
        self.logs_table = models.LogRecordRow
        self.engine = self._create_engine(db_path)
        # TODO Check if the below two lines can be merged?
        Session = orm.sessionmaker(bind=self.engine)
        self.sesh = Session()
        self.base = models.Base
    # Create all the tables on init (along with session and )
    # Write user-related operations
    
    @staticmethod
    def _create_engine(db_path: str) -> engine.Engine:
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
    
    def _drop_all_tables(self):
        """
        Private helper to drop all tables in schema, needed for tests
        """
        with self.engine.begin() as conn:
            for table in self.base.metadata.sorted_tables:
                conn.execute(table.delete())
            conn.commit()
   
    def _create_db_tables(self):
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
        return int(time.time() * 1000)
    
    @staticmethod
    def parse_db_row(row: engine.row.Row, mode: Optional[str] = None) -> dict:
        """
        Parses an ORM row according to mode
        """
        # Default mode to string
        mode = mode or ROW_PARSE_MODE_STRING
        if mode not in OK_ROW_PARSE_MODES:
            e = ValueError(
                f"Bad parse mode {mode}. Expected one of: {OK_ROW_PARSE_MODES}"
            )
            bot_logger.error(e)
            raise e
        # Make several modes: dict and string TODO
        bot_logger.debug("Parsing user data to a dict")
        res = {}
        cols = row.__class__.__table__.columns
        for col in cols:
            col_name = col.name
            val = getattr(row, col_name)
            if val: 
                res[col_name] = val
        
        if mode == ROW_PARSE_MODE_STRING:
            return json.dumps(res, indent=4)
        elif mode == ROW_PARSE_MODE_DICT:
            return res
        elif mode == ROW_PARSE_MODE_DF:
            # Our dict needs a transformation to be a df
            df_data = {key: [value] for key, value in res.items()}
            df = pl.DataFrame(df_data)
            return df
        
    
    def _construct_table_row(self, dst_attr_name: str, **kwargs) -> tuple:
        """
        ### Mapper converting kwargs to an ORM row object of dst_attr_name.
        :param dst_attr_name: name of the attribute stored within self.
        :return: tuple(sqlalchemy row, error if any)
        """
        # First, check if dst_attr_name is valid
        table = getattr(self, dst_attr_name, None)
        if table is None:
            msg = f"Local cache does not have {dst_attr_name} attr."
            return None, AttributeError(msg)
        # This if is needed for tests of this method
        if "created" not in kwargs:
            kwargs["created"] = self._generate_ts()
        # Getting here means we can actually add our row
        try:
            new_row = table(**kwargs)
        except Exception as e:
            return None, e
        
        bot_logger.debug(f"Prepared new row for {dst_attr_name}: {kwargs}")
        return new_row, None
    
    def _add_new_row(self, row_struct: engine.ResultProxy) -> Union[Exception, None]:
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
        
    def delete_row(self, row_struct: engine.ResultProxy) -> Union[Exception, None]:
        """
        Removes row_struct from the db
        :param row_struct: sqlalchemy row object
        :return: error if any
        """
        try:
            self.sesh.delete(row_struct)
            self.sesh.commit()
        except Exception as e:
            self.sesh.rollback()
            return e
        
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
        # Mb add calls to a timeseries db here to track error and get alerted on them
        if e is not None:
            backup_logger.error(f"Logging to DB failed on row creation: {e}")

        res = self._add_new_row(log_row)
        if res is not None:
            backup_logger.error(f"Adding new DB row failed: {e}")


class UserCache(BaseCache):
    """
    ### Class encapsulates all cache operations on user data
    """
    def __init__(self, db_path: str):
        """
        Instantiates the class, creates the db & tables if they do not exist
        """
        super().__init__(db_path)
        self.users_table = models.User

    def create_user(self, reg_data: dict) -> tuple:
        """
        ### Creates a new user entry in the local db
        :param username: username for registration
        :param discord_id: discord_id of a user
        :return: tuple(user message, error if any)
        """
        # Prepare user data from input
        username = reg_data["username"]
        user_row, e = self._construct_table_row(dst_attr_name="users_table", **reg_data)
        # Check for row struct creation errors
        if e is not None:
            user_msg = f"Internal data error: {e}"
            # Specify msg in case we have attr error
            if isinstance(e, AttributeError):
                user_msg = "Internal data error: users data does not exist on server."
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
        if isinstance(res, exc.IntegrityError):
            return self.handle_integrity_err_user(res)
        else:
            bot_logger.warning("Uncaught error: preparsing user message")
            return self._handle_unexpected_err(res)

    def _fetch_user_data(self, discord_id: int) -> tuple:
        """
        ### Fetches data on user with discord_id from the db
        :param discord_id: discord id of a user
        :return: tuple(User, error if any)
        """
        user = (self.sesh.query(models.User)
                .filter(models.User.discord_id==discord_id).first())
        if user is None:
            bot_logger.debug(f"No results for {discord_id}")
            return None, ValueError("User not registered")
        return user, None  
    
    def get_user(self, discord_id: int,
                 parse_mode: Optional[str] = None) -> tuple:
        """
        Fetches user data
        """
        bot_logger.debug("Fetching user data for %s", discord_id)

        user, e = self._fetch_user_data(discord_id=discord_id)
        # Check for error
        if e is not None:
            user_msg = f"Failed to get user data: {e}"
            bot_logger.error(user_msg)
            return None, user_msg
        # Parse user data to dict
        bot_logger.debug("Got user data for %s", discord_id)
        # Quick return when parsing is not needed
        if parse_mode is None:
            bot_logger.debug("parse_mode not provided, returing ORM object")
            return user, None
        
        # Getting here means we parse ORM object for some user-facing stuff
        try:
            user_data = self.parse_db_row(user, mode=parse_mode)
        except Exception as e:
            bot_logger.error("%s Error parsing user data: %s", e)
        bot_logger.debug("Parsed user data for %s", discord_id)
        return user_data, None
    
    def update_user_data(self, discord_id: int,
                         user_update: dict) -> Union[Exception, None]:
        """
        ### Updates field with value in users table
        :return: error if any
        """
        (self.sesh.query(models.User).filter(models.User.discord_id == discord_id)
         .update(user_update))
        try: 
            self.sesh.commit()
            bot_logger.debug("Update query succeeded for user %s", discord_id)
            return None
        except Exception as e:
            bot_logger.error("Update query failed for user %s: %s", discord_id, e)
            self.sesh.rollback()
            return e


class TransactionCache(BaseCache):
    """
    Class encapsulates all cache operations on transaction data.
    """
    def __init__(self, db_path: str):
        """
        Instantiates the class
        """
        super().__init__(db_path=db_path)
        self.transactions_table = models.Transaction

    def create_transaction(self, tr_data: dict) -> tuple:
        """
        Creates a new transaction entry in the local db
        :param username: username for registration
        :param discord_id: discord_id of a user
        :return: tuple(user message, error if any)
        """
        # Prepare user data from input
        # When a transaction is created, created and updated ts are the same!
        tr_data["updated_at"] = self._generate_ts()
        row, e = self._construct_table_row(dst_attr_name="transactions_table",
                                           **tr_data) 
        # Check for row struct creation errors
        if e is not None:
            user_msg = "Internal data error"
            # Specify msg in case we have attr error
            if isinstance(e, AttributeError):
                user_msg += " transactions data does not exist on server."
            return user_msg, e

        bot_logger.debug("Prepared transaction data row")
        # Add to db (this also rollbacks in case of errors)
        res = self._add_new_row(row)
        # Save path w/o issues
        if res is None:
            user_msg = "Transaction saved locally"
            bot_logger.debug(user_msg)
            return user_msg, None
        
        return "Error saving transaction", res

    def update_transaction(self, update: dict,
                           transaction: models.Transaction) -> tuple:
        """
        Updates transaction
        """
        tr_to_update = self.sesh.query(models.Transaction).filter(
            models.Transaction.transaction_id == transaction.transaction_id
        )
        tr_to_update.update(update)
        try: 
            self.sesh.commit()
            bot_logger.debug("Update query succeeded for transaction %s",
                             transaction.transaction_id)
        except Exception as e:
            bot_logger.error("Update query failed for transaction %s: %s",
                             transaction.transaction_id, e)
            self.sesh.rollback()
            return e
        

class CategoryCache(BaseCache):
    """
    Encompasses operations on category data
    """
    def __init__(self, db_path: str):
        """
        Instantiates the class
        """
        super().__init__(db_path=db_path)

    def _fetch_categories(self) -> List[models.TransactionCategoryRow]:
        """
        Fetches categories from the db
        """
        return self.sesh.query(models.TransactionCategoryRow.category_id,
                               models.TransactionCategoryRow.category_name).all()
    
    def get_categories(self, parse_mode: Optional[str] = None) -> tuple:
        """
        Fetches categoriesfrom the db and parses to a python dict of
                {
                    category_id: category_name
                }
        form if parse_mode is provided
        """    
        category_rows = self._fetch_categories()
        if len(category_rows) == 0:
            return None, ValueError("No categories in the db")
        if parse_mode is None:
            bot_logger.debug("parse_mode not provided, returing ORM object")
            return category_rows, None
        try:
            res = {row.category_id: row.category_name for row in category_rows}
            if parse_mode == ROW_PARSE_MODE_DICT:
                return res, None
            elif parse_mode == ROW_PARSE_MODE_STRING:
                return json.dumps(res, indent=4), None
            else:
                raise Exception(
                    f"Bad parse mode {parse_mode}. Expected: {ROW_PARSE_MODE_DICT} or {ROW_PARSE_MODE_STRING}"  # noqa: E501
                )
        except Exception as e:
            bot_logger.warning("Error parsing catetory rows to dict")
            return None, e

        

class Cache(UserCache, TransactionCache, CategoryCache):
    """
    Class unites all cache operations and is meant to be used in other modules
    """ 
    def __init__(self, db_path: str):
        """
        Instantiates the class
        """
        super().__init__(db_path)
        # Actually create schema in the db, only calling in this class
        self._create_db_tables()

    def get_user_transactions(
            self, user: models.User,
            parse_mode: Optional[str] = None
        ) -> Union[models.Transaction, dict, None]:
        """
        Fetches transaction of the current user. 
        """
        bot_logger.debug("Reading transactions of %s", user.username)
        if not user.transactions:
            return None
        try:
            tr_row = user.transactions[0]
        except Exception as e:
            bot_logger.error("Error reading transactions for %s: %s",
                             user.username, e)
        if parse_mode is None:
            bot_logger.debug(
                "parse_mode not provided, returning ORM transaction object"
            )
            return tr_row
        # Separating result / no result scenarions with this if
        # if tr_row:
        return self.parse_db_row(tr_row, mode=parse_mode)


        


    



