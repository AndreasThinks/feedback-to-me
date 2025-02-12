from fasthtml.common import *
from datetime import datetime, timedelta
from fastcore.basics import patch


# -------------------------
# Database and Schema Setup
# -------------------------
db = database("data/feedback.db")
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

users = db.create(User, pk="email")  # Use email as primary key for simpler login

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

feedback_process_tb = db.create(FeedbackProcess, pk="id")

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

feedback_request_tb = db.create(FeedbackRequest, pk="token")

# FeedbackSubmission table: stores completed feedback submissions in response to the request
class FeedbackSubmission:
    id: str
    request_id: str
    feedback_text: str
    ratings: dict     # Expected to be a JSON-like dict for quality ratings
    process_id: str    # UUID linking to FeedbackProcess table
    created_at: datetime

feedback_submission_tb = db.create(FeedbackSubmission, pk="id")

# FeedbackTheme table: stores extracted themes from feedback
@dataclass
class FeedbackTheme:
    id: str
    feedback_id: str
    theme: str
    sentiment: str  # 'positive', 'negative', or 'neutral'
    created_at: datetime

feedback_themes_tb = db.create(FeedbackTheme, pk="id")

@dataclass
class ConfirmToken:
    token: str
    email: str
    expiry: datetime
    is_used: bool = False

confirm_tokens_tb = db.create(ConfirmToken, pk="token")

# Other helper functions

@dataclass
class Login:
    email: str
    pwd: str
