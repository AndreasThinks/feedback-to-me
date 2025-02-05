from fasthtml.common import *
from models import users, feedback_process_tb, feedback_request_tb, FeedbackProcess, FeedbackRequest, Login

import logging

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


beforeware = Beforeware(auth_before, skip=[r'/',
                                           r'/login',
                                           r'/login-or-register',
                                           r'/login-form',
                                           r'/homepage',
                                            r'/registration-form',
                                            r'/login',
                                            r'/register',
                                            r'/register-new-user',
                                            r'/new-feedback-form/.*',
                                            r'/feedback-submitted',
                                                  r'/static/.*'])
