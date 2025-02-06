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
MIN_PEERS = int(os.getenv("MIN_PEERS", "3"))
MIN_SUPERVISORS = int(os.getenv("MIN_SUPERVISORS", "1"))
MIN_REPORTS = int(os.getenv("MIN_REPORTS", "0"))

STARTING_CREDITS = int(os.getenv("STARTING_CREDITS", "5"))

MAGIC_LINK_EXPIRY_DAYS = int(os.getenv("MAGIC_LINK_EXPIRY_DAYS", "30"))
# Number of reports (people who report) defaults to 0
FEEDBACK_QUALITIES = os.getenv("FEEDBACK_QUALITIES", "Communication,Leadership,Technical Skills,Teamwork,Problem Solving").split(",")
