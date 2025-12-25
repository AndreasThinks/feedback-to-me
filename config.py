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

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "your-openrouter-key")

# Primary LLM models (via OpenRouter)
LLM_MODEL_FAST = os.getenv("LLM_MODEL_FAST", "google/gemini-2.0-flash-001")
LLM_MODEL_REASONING = os.getenv("LLM_MODEL_REASONING", "google/gemini-2.0-flash-thinking-exp")

# Fallback models (used if primary fails)
LLM_MODEL_FAST_FALLBACK = os.getenv("LLM_MODEL_FAST_FALLBACK", "anthropic/claude-3-5-haiku-latest")
LLM_MODEL_REASONING_FALLBACK = os.getenv("LLM_MODEL_REASONING_FALLBACK", "anthropic/claude-sonnet-4-20250514")

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
