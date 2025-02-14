from fasthtml.common import *
from models import users, feedback_process_tb, feedback_request_tb, FeedbackProcess, FeedbackRequest, Login

import re
import logging

# Password validation constants
MIN_PASSWORD_LENGTH = 6
PASSWORD_PATTERNS = {
    'lowercase': r'[a-z]',
    'uppercase': r'[A-Z]',
    'numbers': r'\d',
    'special': r'[!@#$%^&*(),.?":{}|<>]'
}

# Configure logging based on environment variable
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# ------------------------------
# FastHTML Beforeware for Auth
# ------------------------------

def auth_before(req, sess):
    """
    Beforeware function to inject 'auth' from session into request scope.
    """
    auth = req.scope["auth"] = sess.get("auth", None)
    if not auth:
        logger.debug("User not authenticated, redirecting")
        return RedirectResponse("/", status_code=303)


def validate_password_strength(password: str) -> tuple[int, list[str]]:
    """
    Validate password strength and return a score (0-100) and list of issues.
    """
    if not password:
        return 0, ["Password is required"]
    
    issues = []
    score = 0
    
    # Length check (up to 40 points)
    length_score = min(len(password) * 3, 40)
    score += length_score
    if len(password) < MIN_PASSWORD_LENGTH:
        issues.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    
    # Character type checks (15 points each)
    for pattern_name, pattern in PASSWORD_PATTERNS.items():
        if re.search(pattern, password):
            score += 15
        else:
            issues.append(f"Missing {pattern_name}")
    
    # Common patterns check
    common_patterns = [
        r'123', r'abc', r'qwerty', r'admin', r'password',
        r'([a-zA-Z0-9])\1{2,}'  # Three or more repeated characters
    ]
    for pattern in common_patterns:
        if re.search(pattern, password.lower()):
            score = max(0, score - 20)
            issues.append("Contains common pattern")
            break
    
    return score, issues

def validate_email_format(email: str) -> tuple[bool, str]:
    """
    Validate email format and return (is_valid, message).
    """
    if not email:
        return False, "Email is required"
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    return True, "Email format is valid"

def validate_passwords_match(password: str, confirm_password: str) -> tuple[bool, str]:
    """
    Validate that passwords match and return (match, message).
    """
    if not password or not confirm_password:
        return False, "Both passwords are required"
    
    if password != confirm_password:
        return False, "Passwords do not match"
    
    return True, "Passwords match"

beforeware = Beforeware(auth_before, skip=[r'/',
                                           r'^/validate-.*',  # Match all validate-* endpoints
                                           r'/login',
                                           r'/pricing',
                                           r'/privacy-policy',
                                        r'/get-started',
                                           r'/how-it-works',
                                           r'/faq',
                                           r'/register'
                                           r'/login-or-register',
                                           r'/confirm-email/.*',
                                           r'/login-form',
                                           r'/homepage',
                                            r'/registration-form',
                                            r'/login',
                                            r'/register',
                                            r'/register-new-user',
                                            r'/new-feedback-form/.*',
                                            r'/feedback-submitted',
                                            r'/forgot-password',
                                            r'/stripe-webhook',
                                            r'/send-reset-email',
                                            r'/reset-password/.*',
                                                  r'/static/.*'])
