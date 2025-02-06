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

users = db.create(User, pk="email")  # Use email as primary key for simpler login

# FeedbackProcess table: tracks the overall feedback collection process
@dataclass
class FeedbackProcess:
    id: str
    user_id: str
    created_at: datetime
    min_required_peers: int
    min_required_supervisors: int
    min_required_reports: int
    qualities: List[str] # the list of qualities the feedback should cover
    feedback_count: int
    feedback_report: Optional[str] = None  # filled_when_report_generated

@patch
def __ft__(self: FeedbackProcess):
    link = A(f"Feedback Process {self.id}", hx_get= f'/feedback-process/{self.id}', hx_target="#main-content", id=f'process-{self.id}')   
    status_str = "Complete" if self.feedback_report else "In Progress"
    cts = (status_str, " - ", link)
    return Li(*cts, id=f'process-{self.id}')

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


feedback_request_tb = db.create(FeedbackRequest, pk="token")

# FeedbackSubmission table: stores completed feedback submissions in response to the request
class FeedbackSubmission:
    id: str
    requestor_id: str
    provider_id: str  # May be None for anonymous submissions
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
