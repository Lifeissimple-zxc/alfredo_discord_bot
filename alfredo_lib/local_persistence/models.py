from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    Column,
    Integer,
    String
)

# This is an ORM that is responsible for all the operations with the local sqlite3 db.
# It needs to support the following functions:
# Add new row to users table
# Update data in users table
# Add transaction row to the table
# Drop row in the transaction table


# Define our tables
# First we need a base to access metadata about schema
Base = declarative_base()

# Table classes
class User(Base):
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

class LogRecordRow(Base):
    # Dst table for all log records
    __tablename__ = "logs"
    # Logging datapoints
    internal_id = Column(Integer, primary_key=True)
    created = Column(Integer, nullable=False)
    user_id = Column(Integer) # Can be null in some cases
    message = Column(String(300), nullable=False)
    level = Column(String(30), nullable=False)
    func_name = Column(String(30), nullable=False)
