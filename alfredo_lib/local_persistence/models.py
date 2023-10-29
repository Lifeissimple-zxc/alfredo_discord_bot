"""
Module implements orm classes powering alfredo's db
"""
from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

from alfredo_lib import FLOAT_PRECISION

Base = declarative_base()


class User(Base):
    """
    ### Models user data powering alferdo
    """
    __tablename__ = "users"
    # User Attributes
    user_id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    discord_id = Column(Integer, unique=True, nullable=False)
    timezone = Column(String(50))
    created = Column(Integer, nullable=False)
    currency = Column(String(10))
    spreadsheet = Column(String(50))
    transactions = relationship("Transaction", back_populates="user")


class Transaction(Base):
    """
    ### Models transaction rows
    """
    __tablename__ = "transactions"
    transaction_id = Column(Integer, primary_key=True)
    created = Column(Integer, nullable=False)
    # user_id as FK
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False
    )
    amount = Column(Float(precision=FLOAT_PRECISION), nullable=False)
    # Making it three here because of ISO 4217
    # Ideally, I should model currencies as a separate table :)
    # For comment text is the only option
    currency = Column(String(3), nullable=False)
    category_id = Column(Integer,
                         ForeignKey("categories.category_id"),
                         nullable=False)
    comment = Column(String(100))
    split_percent = Column(Float(precision=FLOAT_PRECISION))
    # This field needs to update every time users update a transaction
    updated_at = Column(Integer, nullable=False)
    category = relationship("Category", back_populates="transactions")
    user = relationship("User", back_populates="transactions")


class Category(Base):
    """
    ### Models transaction categories
    """
    __tablename__ = "categories"
    category_id = Column(Integer, primary_key=True)
    created = Column(Integer, nullable=False)
    category_name = Column(String(100), nullable=False, unique=True)
    transactions = relationship("Transaction", back_populates="category")


class LogRecord(Base):
    """
    ### Models logrecords
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