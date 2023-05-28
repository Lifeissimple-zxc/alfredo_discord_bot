from pathlib import Path
from sqlalchemy.orm import sessionmaker, declarative_base
from const import DB_PATH
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String
)

db_path_obj = Path(DB_PATH)
# Create eng
engine = create_engine(f"sqlite:///{db_path_obj.absolute()}", echo=False)
# Create sesh
Session = sessionmaker(bind=engine)
sesh = Session()

# Table class definition
Base = declarative_base()

class Student(Base):
    # Tablename
    __tablename__ = "student"

    # Assign our attributes
    id = Column(Integer, primary_key=True)
    name = Column(String(50)) # Limit name at 50 chars len
    age = Column(Integer)
    grade = Column(String(50))

# # Migrate our table to the db
# Base.metadata.create_all(engine)

# # Instances (rows) of our students
# makarik = Student(name="Makarik", age=27, grade="First")
# glush = Student(name="Glush", age=26, grade="Fourth")
# # # Adding data to db (one by one)
# # sesh.add(makarik)
# # sesh.add(glush)
# # Adding all instances in bulk
# sesh.add_all([makarik, glush])
# # Commit data to db
# sesh.commit()