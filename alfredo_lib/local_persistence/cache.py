import re
from pathlib import Path
from time import time
from alfredo_lib.local_persistence.models import (
    Base,
    User
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    create_engine
)
from sqlalchemy.exc import IntegrityError
from alfredo_lib import (
    logging
)

bot_logger = logging.getLogger("alfredo_logger")

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
        bot_logger.debug(discord_id)
        user_row = self.users_table(username=username,
                                    discord_id=discord_id,
                                    created=self._generate_ts())
        bot_logger.debug(f"Prepared user data for {username} reg")
        # Add to db
        try:
            self.sesh.add(user_row)
            self.sesh.commit()
        
        except IntegrityError as e:
            # Firstly, we rollback or DB will trigger more exceptions
            self.sesh.rollback()
            # Parse what column is causing the issue
            table, col = self.__parse_integrity_err_col(e)
            bot_logger.error(f"DB Constraint violated for {table}.{col}: {e}")
            if col == "username":
                user_msg = "username is already taken"
            else:
                user_msg = "You are already registered"
            return user_msg, e

        except Exception as e:
            user_msg = f"uncaught exception. Details: {e}"
            bot_logger.error(user_msg)
            return user_msg, e
        
        else:
            user_msg = f"{username} registered"
            bot_logger.debug(user_msg)
            return user_msg, None
    
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

        


    



