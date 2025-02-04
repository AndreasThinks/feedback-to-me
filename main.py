#!/usr/bin/env python
from fasthtml.common import *
from datetime import datetime, timedelta
import secrets, os

# ----------------------
# Configuration Settings
# ----------------------
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a .env file

# These configuration values are now sourced from environment variables with defaults given below.

MIN_PEERS = int(os.getenv("MIN_PEERS", "3"))
MIN_SUPERVISORS = int(os.getenv("MIN_SUPERVISORS", "1"))
MAGIC_LINK_EXPIRY_DAYS = int(os.getenv("MAGIC_LINK_EXPIRY_DAYS", "14"))
# Number of reports (people who report) defaults to 0
NUMBER_OF_REPORTS = int(os.getenv("NUMBER_OF_REPORTS", "0"))
FEEDBACK_QUALITIES = os.getenv("FEEDBACK_QUALITIES", "Communication,Leadership,Technical Skills,Teamwork,Problem Solving").split(",")

# -------------------------
# Database and Schema Setup
# -------------------------
db = database("data/feedback.db")
# Users table: using email as unique identifier
from dataclasses import dataclass
@dataclass
class User:
    id: str
    email: str
    role: str
    company: str
    team: str
    created_at: datetime

users = db.create(User, pk="id")

# Feedback table: stores feedback submissions
@dataclass
class Feedback:
    id: str
    requestor_id: str
    provider_id: str  # May be None for anonymous submissions
    feedback_text: str
    ratings: dict     # Expected to be a JSON-like dict for quality ratings
    created_at: datetime

feedback_tb = db.create(Feedback, pk="id")

# Magic links table: stores tokens for magic link authentication
@dataclass
class MagicLink:
    token: str
    email: str
    expiry: datetime

magic_links_tb = db.create(MagicLink, pk="token")

# ----------------------------------
# Utility Functions and Business Logic
# ----------------------------------
def generate_magic_link(email: str) -> str:
    """
    Generates a unique magic link token, stores it with expiry, and returns the link.
    """
    token = secrets.token_urlsafe()
    expiry = datetime.now() + timedelta(days=MAGIC_LINK_EXPIRY_DAYS)
    magic_links_tb.insert({
        "token": token,
        "email": email,
        "expiry": expiry
    })
    return f"/feedback/submit/{token}"

# ------------------------------
# FastHTML Beforeware for Auth
# ------------------------------
def auth_before(req, sess):
    """
    Beforeware function to inject 'auth' from session into request scope.
    Also attaches a filter on feedback_tbl based on requestor_id.
    """
    auth = req.scope["auth"] = sess.get("auth", None)
    if not auth:
        return RedirectResponse("/login", status_code=303)
    # Limit feedback visibility to the authenticated user
    feedback_tb.xtra(requestor_id=auth)

beforeware = Beforeware(auth_before, skip=[r'/login', r'/register', r'/magic/.*', r'/feedback/submit/.*', r'/static/.*'])

# --------------------
# FastHTML App Setup
# --------------------
app, rt = fast_app(
    before=beforeware,
    hdrs=(
        MarkdownJS(),  # Allows rendering markdown in feedback text, if needed.
        Style(f":root {{ --min-peers: {MIN_PEERS}; --min-supervisors: {MIN_SUPERVISORS}; }}")
    ),
    exception_handlers={HTTPException: lambda req, exc: Response(content="", status_code=exc.status_code, headers=exc.headers)}
)

# -----------------------
# Route: User Registration
# -----------------------
@rt("/register")
def post_register(email: str, role: str, company: str, team: str, sess):
    # Ensure a fresh registration by clearing any existing authentication.
    if "auth" in sess:
        del sess["auth"]
    user_data = {
        "id": secrets.token_hex(16),
        "email": email,
        "role": role,
        "company": company,
        "team": team,
        "created_at": datetime.now()
    }
    try:
        # If user already exists, retrieve them (this is simplified)
        u = users[email]
    except Exception:
        u = users.insert(user_data)
    # Set the user as authenticated in session
    sess["auth"] = u.id
    # Instead of returning RedirectResponse (which is auto-followed by TestClient),
    # raise an HTTPException to force a 303 response status.
    raise HTTPException(status_code=303, headers={"Location": f"/magic/link?email={email}"})

# -----------------------
# Route: Generate Magic Link
# -----------------------
@rt("/magic/link")
def get_magic(email: str):
    link = generate_magic_link(email)
    # In production, an email would be sent. Here we simply display the link.
    return Titled("Magic Link Generated",
                  P("Share this magic link with your feedback providers:"),
                  P(link))

# -------------------------------
# Route: Feedback Submission (GET)
# -------------------------------
@rt("/feedback/submit/{token}")
def get_feedback_submit(token: str):
    try:
        record = magic_links_tb[token]
    except Exception:
        record = None
    if record and record["expiry"] > datetime.now():
        # Return a feedback form component (using HTMX where possible)
        # For simplicity, we embed a basic feedback form using FT components.
        form = Form(
            Group(
                # In a complete implementation, rating inputs are generated per quality.
                *[Group(Label(q), Input(type="range", min=1, max=8, value=4, id=f"rating_{q.lower()}"))
                  for q in FEEDBACK_QUALITIES],
                Textarea(id="feedback_text", placeholder="Provide detailed feedback...", rows=5, required=True)
            ),
            Button("Submit Feedback", type="submit"),
            hx_post="/feedback/submit",
            hx_target="#feedback-status"
        )
        return Titled("Submit Feedback", form)
    else:
        return Titled("Invalid or Expired Link", P("This magic feedback link is invalid or has expired."))

# -------------------------------
# Route: Feedback Submission (POST)
# -------------------------------
@rt("/feedback/submit")
def post_feedback(feedback_text: str, sess):
    user_id = sess.get("auth")
    feedback_data = {
        "id": secrets.token_hex(16),
        "requestor_id": user_id,
        "provider_id": None,  # For anonymous submissions
        "feedback_text": feedback_text,
        "ratings": {},       # For demonstration; in a full app, extract ratings from form data.
        "created_at": datetime.now()
    }
    feedback_tb.insert(feedback_data)
    return Titled("Feedback Submitted", P("Thank you for your feedback!"))

# ------------------------------
# Route: Feedback Report Generation
# ------------------------------
@rt("/report/{user_id}")
def get_report(user_id: str, auth):
    if auth != user_id:
        return Titled("Access Denied", P("You are not allowed to view this report."))
    # Placeholder for report generation logic.
    # In a complete implementation, we would aggregate feedback, extract themes, and compute sentiments.
    return Titled("Feedback Report", P("Report contents would be generated here."))

# ------------------------------
# Basic Login and Logout Routes
# ------------------------------
@rt("/login")
def get_login():
    # Render a simple login form.
    form = Form(
        Group(
            Input(id="email", type="email", placeholder="Email", required=True),
            Input(id="pwd", type="password", placeholder="Password", required=True)
        ),
        Button("Login", type="submit"),
        action="/login", method="post",
        hx_post="/login", hx_target="#login-status"
    )
    return Titled("Login", form)

@dataclass
class Login:
    email: str
    pwd: str

@rt("/login")
def post_login(login: Login, sess):
    try:
        u = users[login.email]
    except Exception:
        return RedirectResponse("/login", status_code=303)
    # Use constant-time comparison for passwords (simplified here).
    if not compare_digest(u.pwd.encode("utf-8"), login.pwd.encode("utf-8")):
        return RedirectResponse("/login", status_code=303)
    sess["auth"] = u.id
    return RedirectResponse("/", status_code=303)

@rt("/logout")
def get_logout(sess):
    if "auth" in sess:
        del sess["auth"]
    return RedirectResponse("/login", status_code=303)

# ------------------------------
# Route: Home Dashboard
# ------------------------------
@rt("/")
def get_home(req):
    # If user is not authenticated, force a redirect by raising an HTTPException.
    if not req.scope.get("auth"):
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    # Create a top bar with a login/sign-up link
    top_bar = Div(
        A("Log in / Sign up", href="/login", cls="top-link"),
        cls="top-bar",
        style="padding: 1rem; background-color: #f0f0f0; text-align: right;"
    )
    # Main content with a title, description, and a big request feedback button
    main_content = Div(
        H1("Welcome to Feedback2Me", style="font-size: 2.5rem; margin-bottom: 1rem;"),
        P("Collect anonymous 360-degree feedback and get actionable insights to improve your professional growth.", style="font-size: 1.2rem; margin-bottom: 2rem;"),
        Button("Request Feedback", hx_get="/feedback/request", cls="big-button", style="font-size: 1.5rem; padding: 1rem 2rem;"),
        cls="main-content",
        style="text-align: center; padding: 2rem;"
    )
    # Combine top bar and main content into a container
    container = Container(top_bar, main_content)
    return Titled("Feedback2Me", container)

# -------------
# Start the App
# -------------
if __name__ == "__main__":
    serve()
