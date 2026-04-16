from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

Base = declarative_base()

class ScanResult(Base):
    __tablename__ = 'scan_results'
    id = Column(Integer, primary_key=True)
    student_id = Column(String, nullable=False, index=True)
    test_name = Column(String, nullable=False, index=True)
    grade = Column(String)  # 6, 7, or 8
    school = Column(String, index=True)
    session_name = Column(String, index=True)  # Session/event name for grouping scans
    score = Column(Float)
    correct_count = Column(Integer)
    incorrect_count = Column(Integer)
    tiebreaker_correct = Column(Integer, default=0)
    answers_json = Column(Text)  # Store all answers as JSON: {"1": "A", "2": "B", ...}
    answer_key_json = Column(Text)  # Store answer key as JSON
    scan_date = Column(DateTime, default=datetime.now)
    
    def set_answers(self, answers_dict):
        """Store answers dictionary as JSON"""
        self.answers_json = json.dumps(answers_dict)
    
    def get_answers(self):
        """Retrieve answers as dictionary"""
        if self.answers_json:
            return json.loads(self.answers_json)
        return {}
    
    def set_answer_key(self, key_dict):
        """Store answer key as JSON"""
        self.answer_key_json = json.dumps(key_dict)
    
    def get_answer_key(self):
        """Retrieve answer key as dictionary"""
        if self.answer_key_json:
            return json.loads(self.answer_key_json)
        return {}

# SQLite database file will be created in the project folder
db_url = 'sqlite:///bubble_scanner.db'
engine = create_engine(db_url, echo=True)
SessionLocal = sessionmaker(bind=engine)

# Create tables if they don't exist
def init_db():
    Base.metadata.create_all(engine)
