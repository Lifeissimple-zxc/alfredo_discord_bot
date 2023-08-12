from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey
)

from alfredo_lib import MAIN_CFG

FLOAT_PRECISION = MAIN_CFG["float_precision"]

# Define our tables
# First we need a base to access metadata about schema
Base = declarative_base()

class User(Base):
    """
    ### Class models user data powering alferdo
    """
    # Tablename
    __tablename__ = "users"

    # User Attributes
    user_id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    discord_id = Column(Integer, unique=True, nullable=False)
    timezone = Column(String(50))
    created = Column(Integer, nullable=False)
    currency = Column(String(10))
    spreadsheet = Column(String(50))

class Transaction(Base):
    """
    ### Class models transaction rows
    """
    __tablename__ = "transaction_cache"

    transaction_id = Column(Integer, primary_key=True)
    created = Column(Integer, nullable=False)
    # user_id as FK
    user_id = Column(
        Integer,
        ForeignKey("users.user_id",ondelete="CASCADE"),
        nullable=False
    )
    amount = Column(Float(precision=FLOAT_PRECISION), nullable=False)
    # Making it three here because of ISO 4217
    # Ideally, I should not be storing text, but model currencies as a separate table :)
    # For comment text is the only option
    currency = Column(String(3), nullable=False)
    category = Column(String(30), nullable=False)
    comment = Column(String(100))
    split_percent = Column(Float(precision=FLOAT_PRECISION))
    # This field needs to update every time users update a transaction
    updated_at = Column(Integer, nullable=False)

class LogRecordRow(Base):
    """
    ### Class models logrecords
    """
    # Dst table for all log records
    __tablename__ = "logs"
    # Logging datapoints
    internal_id = Column(Integer, primary_key=True)
    created = Column(Integer, nullable=False)
    user_id = Column(Integer) # Can be null in some cases
    message = Column(String(300), nullable=False)
    level = Column(String(30), nullable=False)
    func_name = Column(String(30), nullable=False)
