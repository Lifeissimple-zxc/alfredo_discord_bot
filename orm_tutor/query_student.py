from pathlib import Path
from sqlalchemy.orm import sessionmaker, declarative_base
from const import DB_PATH
from sqlalchemy import (
    or_,
    asc,
    desc,
    create_engine,
    Column,
    Integer,
    String
)

# Bolierplate to get access to orm objects
db_path_obj = Path(DB_PATH)
engine = create_engine(f"sqlite:///{db_path_obj.absolute()}", echo=False)
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

# Get data
print("\nSimple select")
students = sesh.query(Student)
for s in students:
    print(s.id, s.name, s.age, s.grade)

# Get ordered data
print("\nOrdered select")
students = sesh.query(Student).order_by(asc(Student.age))
for s in students:
    print(s.id, s.name, s.age, s.grade)
# Get filtered data
print("\nFileted select")
students = (sesh.
            query(Student).
            filter(or_(Student.name=="Makarik",
                       Student.age==26)).
            order_by(desc(Student.grade)))
for s in students:
    print(s.id, s.name, s.age, s.grade)
# Count result rows
print("\nCount rows in result")
# https://www.youtube.com/watch?v=9xkfCo5StAk&list=PL4iRawDSyRvVd1V7A45YtAGzDk6ljVPm1&index=4
students = (sesh.query(Student).filter(Student.name=="Glush")).count()
print(students)

# Update queries
# Get our data
# student = sesh.query(Student).filter(Student.name=="Glush").first()
# # Update part of the data
# student.name = "Jamie"
# sesh.commit()

# # Delete queries
# # Get the needed record
# student = sesh.query(Student).filter(Student.name=="Makarik").first()
# # Delete record
# sesh.delete(student)
# # Commit to db
# sesh.commit()