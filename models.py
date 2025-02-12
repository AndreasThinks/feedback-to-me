from fasthtml.common import *
from datetime import datetime, timedelta
from fastcore.basics import patch
from fastsql import Database, DBTable
import sqlalchemy as sa
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, MetaData
from config import DB_URL

metadata = MetaData()
# -------------------------
# Database and Schema Setup
# -------------------------
# Get database URL from environment variable, fallback to SQLite for development
import os
db_url = DB_URL
if db_url.startswith("postgresql://"):
    print('db ur is ')
    print(db_url)
    db = Database(db_url)
else:
    db = database(db_url)  # SQLiteFastSQL fallback
# Users table: using email as unique identifier
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class User:
    id: str
    first_name: str
    email: str
    role: Optional[str]
    company: Optional[str]
    team: Optional[str]
    created_at: datetime
    pwd: str
    is_confirmed: bool = False
    credits: int = 3  # New users start with 3 free credits

# SQLAlchemy Table definitions
users_table = Table(
    'users',
    metadata,
    Column('id', String, primary_key=True),  # Using id as primary key
    Column('first_name', String, nullable=False),
    Column('email', String, nullable=False, unique=True),  # Unique constraint on email
    Column('role', String),
    Column('company', String),
    Column('team', String),
    Column('created_at', DateTime, nullable=False),
    Column('pwd', String, nullable=False),
    Column('is_confirmed', Boolean, default=False),
    Column('credits', Integer, default=3)
)

users = DBTable(users_table, database=db, cls=User)

# FeedbackProcess table: tracks the overall feedback collection process

class FeedbackProcess:
    id: str
    process_title : str
    user_id: str
    created_at: datetime
    min_submissions_required: int
    qualities: List[str] # the list of qualities the feedback should cover
    feedback_count: int
    report_submission_prompt: Optional[str] = None  
    feedback_report: Optional[str] = None  # filled_when_report_generated

@patch
def __ft__(self: FeedbackProcess):
     # Convert the string datetime to a datetime object if necessary
    try:
        created_at_dt = datetime.fromisoformat(self.created_at)  # If stored in ISO format (e.g., "2025-02-07T14:30:00")
    except ValueError:
        created_at_dt = datetime.strptime(self.created_at, "%Y-%m-%d %H:%M:%S")  # Adjust format if needed

    # Format the datetime object into a human-readable string
    formatted_date = created_at_dt.strftime("%B %d, %Y %H:%M")  # Example: "February 07, 2025 14:30"
    link = AX(f"{self.process_title} - created on {formatted_date}", href= f'/feedback-process/{self.id}', id=f'process-{self.id}')   
    return Li(link, id=f'process-{self.id}')

# FeedbackProcess table definition
feedback_process_table = Table(
    'feedback_process',
    metadata,
    Column('id', String, primary_key=True),
    Column('process_title', String, nullable=False),
    Column('user_id', String, ForeignKey('users.id'), nullable=False),
    Column('created_at', DateTime, nullable=False),
    Column('min_submissions_required', Integer, nullable=False),
    Column('qualities', JSON, nullable=False),  # Store list as JSON
    Column('feedback_count', Integer, nullable=False),
    Column('report_submission_prompt', String),
    Column('feedback_report', String)
)

feedback_process_tb = DBTable(feedback_process_table, database=db, cls=FeedbackProcess)

# FeedbackRequest table: stores requests to individuals
@dataclass
class FeedbackRequest:
    token: str
    email: str
    user_type: str  # 'peer', 'supervisor', or 'report'
    process_id: str  # Link back to FeedbackProcess; may be None for standalone requests.
    expiry: datetime
    email_sent: Optional[datetime] = None
    completed_at: Optional[datetime] = None

# FeedbackRequest table definition
feedback_request_table = Table(
    'feedback_request',
    metadata,
    Column('token', String, primary_key=True),
    Column('email', String, nullable=False),
    Column('user_type', String, nullable=False),
    Column('process_id', String, ForeignKey('feedback_process.id'), nullable=False),
    Column('expiry', DateTime, nullable=False),
    Column('email_sent', DateTime),
    Column('completed_at', DateTime)
)

feedback_request_tb = DBTable(feedback_request_table, database=db, cls=FeedbackRequest)

# FeedbackSubmission table: stores completed feedback submissions in response to the request
class FeedbackSubmission:
    id: str
    request_id: str
    feedback_text: str
    ratings: dict     # Expected to be a JSON-like dict for quality ratings
    process_id: str    # UUID linking to FeedbackProcess table
    created_at: datetime

# FeedbackSubmission table definition
feedback_submission_table = Table(
    'feedback_submission',
    metadata,
    Column('id', String, primary_key=True),
    Column('request_id', String, ForeignKey('feedback_request.token'), nullable=False),
    Column('feedback_text', String, nullable=False),
    Column('ratings', JSON, nullable=False),  # Store dict as JSON
    Column('process_id', String, ForeignKey('feedback_process.id'), nullable=False),
    Column('created_at', DateTime, nullable=False)
)

feedback_submission_tb = DBTable(feedback_submission_table, database=db, cls=FeedbackSubmission)

# FeedbackTheme table: stores extracted themes from feedback
@dataclass
class FeedbackTheme:
    id: str
    feedback_id: str
    theme: str
    sentiment: str  # 'positive', 'negative', or 'neutral'
    created_at: datetime

# FeedbackTheme table definition
feedback_theme_table = Table(
    'feedback_theme',
    metadata,
    Column('id', String, primary_key=True),
    Column('feedback_id', String, ForeignKey('feedback_submission.id'), nullable=False),
    Column('theme', String, nullable=False),
    Column('sentiment', String, nullable=False),
    Column('created_at', DateTime, nullable=False)
)

feedback_themes_tb = DBTable(feedback_theme_table, database=db, cls=FeedbackTheme)

@dataclass
class ConfirmToken:
    token: str
    email: str
    expiry: datetime
    is_used: bool = False

# ConfirmToken table definition
confirm_token_table = Table(
    'confirm_token',
    metadata,
    Column('token', String, primary_key=True),
    Column('email', String, ForeignKey('users.email', ondelete='CASCADE'), nullable=False),
    Column('expiry', DateTime, nullable=False),
    Column('is_used', Boolean, default=False)
)

confirm_tokens_tb = DBTable(confirm_token_table, database=db, cls=ConfirmToken)

# Other helper functions

@dataclass
class Login:
    email: str
    pwd: str
