from fasthtml.common import *
from datetime import datetime, timedelta
import secrets, os
import bcrypt

# ----------------------
# Configuration Settings
# ----------------------
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a .env file

# These configuration values are now sourced from environment variables with defaults given below.
# New approach: single minimum submissions requirement
MINIMUM_SUBMISSIONS_REQUIRED = int(os.getenv("MINIMUM_SUBMISSIONS_REQUIRED", "5"))

# Deprecated: old role-based minimums (kept for backward compatibility)
MIN_PEERS = int(os.getenv("MIN_PEERS", "0"))
MIN_SUPERVISORS = int(os.getenv("MIN_SUPERVISORS", "0"))
MIN_REPORTS = int(os.getenv("MIN_REPORTS", "0"))

STARTING_CREDITS = int(os.getenv("STARTING_CREDITS", "5"))
COST_PER_CREDIT_USD = int(os.getenv("COST_PER_CREDIT_USD", "3"))

MAGIC_LINK_EXPIRY_DAYS = int(os.getenv("MAGIC_LINK_EXPIRY_DAYS", "30"))
# Number of reports (people who report) defaults to 0
FEEDBACK_QUALITIES = os.getenv("FEEDBACK_QUALITIES", "Communication,Leadership,Technical Skills,Teamwork,Problem Solving").split(",")

BASE_URL =  os.getenv("BASE_URL", "feedback-to.me")
GEMINI_API_KEY=os.getenv("GEMINI_API_KEY", "gemini_key")

DB_URL = os.getenv("DATABASE_URL", "data/feedback.db")
