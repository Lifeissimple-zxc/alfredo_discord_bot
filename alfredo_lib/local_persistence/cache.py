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
    # Abstract logging timestamps
    
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
    
    def create_user(self, username: str, discord_id: int):
        """
        Creates a new user entry in the local db
        """
        # TODO exceptions? have no idea what might occur here
        # sqlite3.IntegrityError when unique constraint fails
        # Prepare user data from input
        user_row = self.users_table(username=username,
                                    discord_id=discord_id,
                                    created=self._generate_ts())
        bot_logger.debug(f"Prepared user data for {username} reg")
        # Add to db
        
        try:
            self.sesh.add(user_row)
            self.sesh.commit()
            bot_logger.debug(f"{username} registered")
        except Exception as e:
            bot_logger.error(f"Registration failed for {username}: {e}")
            return e

    



